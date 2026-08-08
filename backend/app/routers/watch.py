"""Watch-time telemetry from local signals only.

The browser owns the clock: it counts seconds while the tab is visible, focused,
and the user is not idle, then posts what it counted. Nothing here streams,
scrapes, or touches anyone else's video. Every second in this table came from a
tab you had open on your own machine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import Anime, EpisodeMarker, User, WatchDay, WatchlistItem, WatchSession
from app.schemas import (
    AnimeOut,
    HeartbeatIn,
    HeartbeatOut,
    MarkerIn,
    MarkerOut,
    SessionStartIn,
    StreakOut,
    WatchDayOut,
    WatchSessionOut,
)
from app.services import events
from app.services.library import (
    advance_episode,
    episode_seconds_for,
    get_preferences,
    now,
    start_rewatch,
    upsert_library,
)
from app.services.metrics import ACTIVE_SESSIONS, EPISODES_TICKED, WATCH_SECONDS

router = APIRouter(prefix="/api/watch", tags=["watch"])

# A session with no beat for this long is treated as abandoned.
STALE_AFTER = timedelta(minutes=10)
# Another device counts as live if it beat within this window.
LIVE_WINDOW = timedelta(minutes=2)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _session_out(session: WatchSession, anime: Anime | None = None) -> WatchSessionOut:
    return WatchSessionOut(
        id=session.id,
        anime_id=session.anime_id,
        device_id=session.device_id,
        device_label=session.device_label,
        active_seconds=int(session.active_seconds or 0),
        episodes_ticked=int(session.episodes_ticked or 0),
        carry_seconds=int(session.carry_seconds or 0),
        source=session.source,
        started_at=session.started_at,
        last_beat_at=session.last_beat_at,
        ended_at=session.ended_at,
        anime=AnimeOut.model_validate(anime) if anime else None,
    )


def _roll_day(db: Session, user_id: int, seconds: int, episodes: int) -> None:
    today = now().date()
    row = (
        db.query(WatchDay)
        .filter(WatchDay.user_id == user_id, WatchDay.day == today)
        .first()
    )
    if not row:
        row = WatchDay(user_id=user_id, day=today, seconds=0, episodes=0)
        db.add(row)
    row.seconds = int(row.seconds or 0) + max(0, seconds)
    row.episodes = int(row.episodes or 0) + max(0, episodes)


@router.post("/session", response_model=HeartbeatOut)
def start_session(
    payload: SessionStartIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    anime = db.get(Anime, payload.anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")

    prefs = get_preferences(db, user.id)
    cutoff = now() - STALE_AFTER

    # Reuse an open session on this device so a refresh does not fork the timer.
    session = (
        db.query(WatchSession)
        .filter(
            WatchSession.user_id == user.id,
            WatchSession.anime_id == anime.id,
            WatchSession.device_id == payload.device_id,
            WatchSession.ended_at.is_(None),
        )
        .order_by(WatchSession.id.desc())
        .first()
    )
    if session and _aware(session.last_beat_at) and _aware(session.last_beat_at) < cutoff:
        session.ended_at = now()
        session = None

    if not session:
        session = WatchSession(
            user_id=user.id,
            anime_id=anime.id,
            device_id=payload.device_id,
            device_label=payload.device_label,
            source=payload.source,
            started_at=now(),
            last_beat_at=now(),
        )
        db.add(session)

    item = upsert_library(db, user.id, anime.id, status_value="watching")
    events.record(
        db,
        user_id=user.id,
        kind="watch_started",
        anime_id=anime.id,
        detail=f"{anime.title} on {payload.device_id}",
    )
    db.commit()
    db.refresh(session)

    conflict = _has_live_conflict(db, user.id, anime.id, payload.device_id)
    ep_seconds = episode_seconds_for(anime, prefs)
    return HeartbeatOut(
        session=_session_out(session, anime),
        progress=int(item.progress or 0),
        status=item.status,
        episode_seconds=ep_seconds,
        seconds_to_next=max(0, ep_seconds - int(session.carry_seconds or 0)),
        conflict=conflict,
    )


def _has_live_conflict(db: Session, user_id: int, anime_id: int, device_id: str) -> bool:
    cutoff = now() - LIVE_WINDOW
    return (
        db.query(WatchSession)
        .filter(
            WatchSession.user_id == user_id,
            WatchSession.anime_id == anime_id,
            WatchSession.device_id != device_id,
            WatchSession.ended_at.is_(None),
            WatchSession.last_beat_at >= cutoff,
        )
        .count()
        > 0
    )


@router.post("/heartbeat", response_model=HeartbeatOut)
def heartbeat(
    payload: HeartbeatIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(WatchSession, payload.session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.ended_at is not None:
        raise HTTPException(status_code=409, detail="Session already closed")

    anime = db.get(Anime, session.anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")

    prefs = get_preferences(db, user.id)
    ep_seconds = episode_seconds_for(anime, prefs)

    gained = 0 if payload.idle else int(payload.active_seconds or 0)
    session.active_seconds = int(session.active_seconds or 0) + gained
    session.carry_seconds = int(session.carry_seconds or 0) + gained
    session.last_beat_at = now()

    item = upsert_library(db, user.id, anime.id, status_value=None)
    item.watch_seconds = int(item.watch_seconds or 0) + gained

    ticked = 0
    prompt = None
    if prefs.auto_tick:
        while session.carry_seconds >= ep_seconds:
            session.carry_seconds -= ep_seconds
            item, finished = advance_episode(db, user.id, anime)
            ticked += 1
            EPISODES_TICKED.labels(mode="auto").inc()
            if finished:
                session.carry_seconds = 0
                break
    elif session.carry_seconds >= int(ep_seconds * 0.92):
        prompt = f"Looks like you finished episode {int(item.progress or 0) + 1}. Mark it?"

    if gained:
        WATCH_SECONDS.labels(source=session.source).inc(gained)
    if ticked:
        session.episodes_ticked = int(session.episodes_ticked or 0) + ticked
        events.record(
            db,
            user_id=user.id,
            kind="episode_auto_ticked",
            anime_id=anime.id,
            detail=f"{anime.title} to episode {item.progress}",
        )
    _roll_day(db, user.id, gained, ticked)
    db.commit()
    db.refresh(session)
    db.refresh(item)

    return HeartbeatOut(
        session=_session_out(session, anime),
        ticked=ticked,
        progress=int(item.progress or 0),
        status=item.status,
        episode_seconds=ep_seconds,
        seconds_to_next=max(0, ep_seconds - int(session.carry_seconds or 0)),
        prompt=prompt,
        conflict=_has_live_conflict(db, user.id, anime.id, session.device_id),
    )


@router.post("/session/{session_id}/stop", response_model=WatchSessionOut)
def stop_session(
    session_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(WatchSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.ended_at is None:
        session.ended_at = now()
        events.record(
            db,
            user_id=user.id,
            kind="watch_stopped",
            anime_id=session.anime_id,
            detail=f"{int(session.active_seconds or 0)}s of attention",
        )
        db.commit()
        db.refresh(session)
    return _session_out(session, db.get(Anime, session.anime_id))


@router.get("/active", response_model=list[WatchSessionOut])
def active_sessions(user: User = Depends(require_user), db: Session = Depends(get_db)):
    cutoff = now() - STALE_AFTER
    rows = (
        db.query(WatchSession)
        .filter(
            WatchSession.user_id == user.id,
            WatchSession.ended_at.is_(None),
            WatchSession.last_beat_at >= cutoff,
        )
        .order_by(WatchSession.last_beat_at.desc())
        .all()
    )
    ACTIVE_SESSIONS.set(len(rows))
    return [_session_out(r, db.get(Anime, r.anime_id)) for r in rows]


@router.get("/streak", response_model=StreakOut)
def streak(
    days: int = Query(182, ge=14, le=400),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    start = now().date() - timedelta(days=days)
    rows = (
        db.query(WatchDay)
        .filter(WatchDay.user_id == user.id, WatchDay.day >= start)
        .order_by(WatchDay.day)
        .all()
    )
    by_day = {r.day: r for r in rows}

    today = now().date()
    current = 0
    cursor = today
    # A gap on today alone should not break a streak that is still live.
    if cursor not in by_day:
        cursor -= timedelta(days=1)
    while cursor in by_day and by_day[cursor].seconds > 0:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    previous = None
    for day in sorted(by_day):
        if previous is not None and (day - previous).days == 1:
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        previous = day

    total_seconds = (
        db.query(func.coalesce(func.sum(WatchDay.seconds), 0))
        .filter(WatchDay.user_id == user.id)
        .scalar()
        or 0
    )
    week_start = today - timedelta(days=6)
    week_seconds = sum(r.seconds for d, r in by_day.items() if d >= week_start)

    return StreakOut(
        current_streak=current,
        longest_streak=longest,
        total_hours=round(total_seconds / 3600, 2),
        week_hours=round(week_seconds / 3600, 2),
        days=[
            WatchDayOut(day=r.day, seconds=int(r.seconds or 0), episodes=int(r.episodes or 0))
            for r in rows
        ],
    )


@router.post("/rewatch/{anime_id}")
def begin_rewatch(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    anime = db.get(Anime, anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    item = start_rewatch(db, user.id, anime)
    events.record(
        db, user_id=user.id, kind="rewatch_started", anime_id=anime.id, detail=anime.title
    )
    db.commit()
    return {
        "anime_id": anime_id,
        "status": item.status,
        "progress": item.progress,
        "rewatches": int(item.rewatches or 0),
        "is_rewatching": True,
    }


@router.get("/markers/{anime_id}", response_model=MarkerOut)
def get_markers(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(EpisodeMarker)
        .filter(EpisodeMarker.user_id == user.id, EpisodeMarker.anime_id == anime_id)
        .first()
    )
    if not row:
        anime = db.get(Anime, anime_id)
        if not anime:
            raise HTTPException(status_code=404, detail="Anime not found")
        runtime = episode_seconds_for(anime, get_preferences(db, user.id))
        return MarkerOut(
            anime_id=anime_id,
            intro_start_s=0,
            intro_end_s=90,
            outro_start_s=max(0, runtime - 90),
        )
    return MarkerOut(
        anime_id=anime_id,
        intro_start_s=row.intro_start_s,
        intro_end_s=row.intro_end_s,
        outro_start_s=row.outro_start_s,
    )


@router.put("/markers/{anime_id}", response_model=MarkerOut)
def set_markers(
    anime_id: int,
    payload: MarkerIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not db.get(Anime, anime_id):
        raise HTTPException(status_code=404, detail="Anime not found")
    row = (
        db.query(EpisodeMarker)
        .filter(EpisodeMarker.user_id == user.id, EpisodeMarker.anime_id == anime_id)
        .first()
    )
    if not row:
        row = EpisodeMarker(user_id=user.id, anime_id=anime_id)
        db.add(row)
    row.intro_start_s = payload.intro_start_s
    row.intro_end_s = max(payload.intro_start_s, payload.intro_end_s)
    row.outro_start_s = payload.outro_start_s
    db.commit()
    return MarkerOut(
        anime_id=anime_id,
        intro_start_s=row.intro_start_s,
        intro_end_s=row.intro_end_s,
        outro_start_s=row.outro_start_s,
    )


@router.get("/history", response_model=list[WatchSessionOut])
def history(
    limit: int = Query(25, ge=1, le=100),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(WatchSession)
        .filter(WatchSession.user_id == user.id)
        .order_by(WatchSession.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_session_out(r, db.get(Anime, r.anime_id)) for r in rows]


@router.get("/tonight")
def finishable_tonight(
    minutes: int = Query(180, ge=20, le=1440),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """What is actually closable in the time you have left this evening."""
    prefs = get_preferences(db, user.id)
    budget = minutes * 60
    rows = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.user_id == user.id,
            WatchlistItem.status.in_(("watching", "plan_to_watch", "on_hold")),
        )
        .all()
    )
    out = []
    for item in rows:
        anime = db.get(Anime, item.anime_id)
        if not anime:
            continue
        ep_seconds = episode_seconds_for(anime, prefs)
        left = (anime.episodes or 1) - int(item.progress or 0)
        if left <= 0:
            continue
        needed = left * ep_seconds
        if needed <= budget:
            out.append(
                {
                    "anime": AnimeOut.model_validate(anime),
                    "episodes_left": left,
                    "minutes_left": round(needed / 60),
                    "status": item.status,
                    "progress": int(item.progress or 0),
                }
            )
    out.sort(key=lambda row: row["minutes_left"])
    return {"budget_minutes": minutes, "items": out[:24]}
