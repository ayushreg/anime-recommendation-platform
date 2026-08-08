"""Airing schedules and the upcoming grid.

Fetching and reading are separate on purpose. A refresh writes into Postgres;
the read routes only ever query Postgres. That keeps every page render fast and
keeps Kura well clear of AniList's rate limits, since forty people opening the
page costs zero upstream requests. `stale` says how old the copy is.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_user
from app.config import settings
from app.database import get_db
from app.models import AiringEntry, Anime, User, WatchlistItem
from app.schemas import (
    AiringListOut,
    AiringOut,
    AnimeOut,
    LiveRefreshOut,
    LiveStatusOut,
)
from app.services import events, ingest, live
from app.services.flags import enabled
from app.services.ordering import safe_filter

router = APIRouter(prefix="/api/live", tags=["live"])

# Past this age the UI says "last checked N ago" instead of presenting the grid
# as current.
STALE_AFTER = timedelta(hours=24)


def _require_flag() -> None:
    """Live data is on by default; the flag exists as a kill switch."""
    if not enabled("live_data", default=True):
        raise HTTPException(
            status_code=404,
            detail="Live data is switched off on this instance.",
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; Postgres does not. Normalize both."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _last_refresh(db: Session) -> datetime | None:
    return _aware(db.query(func.max(AiringEntry.refreshed_at)).scalar())


def _rows_to_out(
    db: Session,
    rows: list[tuple[AiringEntry, Anime]],
    user: User | None,
    reasons: dict[int, str] | None = None,
) -> list[AiringOut]:
    library: dict[int, str] = {}
    if user:
        library = {
            item.anime_id: item.status
            for item in db.query(WatchlistItem)
            .filter(
                WatchlistItem.user_id == user.id,
                WatchlistItem.anime_id.in_([a.id for _, a in rows] or [0]),
            )
            .all()
        }

    now = _now()
    out: list[AiringOut] = []
    for entry, anime in rows:
        airs_at = _aware(entry.next_episode_at)
        seconds = None
        if airs_at:
            seconds = max(0, int((airs_at - now).total_seconds()))
        out.append(
            AiringOut(
                anime=AnimeOut.model_validate(anime),
                airing_status=entry.airing_status,
                next_episode=entry.next_episode,
                next_episode_at=airs_at,
                seconds_until=seconds,
                start_date=entry.start_date,
                episodes_total=entry.episodes_total,
                in_library=anime.id in library,
                library_status=library.get(anime.id),
                why=(reasons or {}).get(anime.id),
            )
        )
    return out


def _query(db: Session, airing_status: str):
    return (
        safe_filter(db.query(AiringEntry, Anime).join(Anime, Anime.id == AiringEntry.anime_id))
        .filter(AiringEntry.airing_status == airing_status)
    )


@router.get("/status", response_model=LiveStatusOut)
def live_status(probe: bool = Query(False), db: Session = Depends(get_db)):
    """What the instance knows, and optionally whether it can reach the source.

    Answers 200 even when the feature is switched off, so the settings page can
    say so rather than showing a broken panel.
    """
    on = enabled("live_data", default=True)
    counts = dict(
        db.query(AiringEntry.airing_status, func.count(AiringEntry.id))
        .group_by(AiringEntry.airing_status)
        .all()
    )
    reachable: bool | None = None
    detail: str | None = None
    if on and probe:
        probed = live.reachability()
        reachable, detail = probed["reachable"], probed["detail"]

    return LiveStatusOut(
        enabled=on,
        reachable=reachable,
        detail=detail,
        releasing=int(counts.get("releasing", 0)),
        upcoming=int(counts.get("upcoming", 0)),
        live_titles=db.query(func.count(Anime.id))
        .filter(Anime.catalog_source == "live")
        .scalar()
        or 0,
        refreshed_at=_last_refresh(db),
    )


@router.post("/refresh", response_model=LiveRefreshOut)
def refresh(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Pull both statuses from AniList and write them into Postgres."""
    _require_flag()
    limit = max(50, settings.live_ingest_limit // 2)

    try:
        releasing = live.fetch_airing("RELEASING", limit=limit, use_cache=False)
        upcoming = live.fetch_airing("NOT_YET_RELEASED", limit=limit, use_cache=False)
    except live.LiveUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    releasing_stats = ingest.ingest(db, releasing, "releasing")
    upcoming_stats = ingest.ingest(db, upcoming, "upcoming")
    pruned = ingest.prune_stale(
        db, {r["mal_id"] for r in releasing}, "releasing"
    ) + ingest.prune_stale(db, {r["mal_id"] for r in upcoming}, "upcoming")
    db.commit()

    events.record(
        db,
        user_id=user.id,
        kind="live_refresh",
        detail=(
            f"{releasing_stats['seen']} airing, {upcoming_stats['seen']} upcoming, "
            f"{releasing_stats['created'] + upcoming_stats['created']} new titles"
        ),
        persist=False,
    )
    db.commit()

    return LiveRefreshOut(
        releasing=releasing_stats,
        upcoming=upcoming_stats,
        pruned=pruned,
        refreshed_at=_last_refresh(db) or _now(),
    )


@router.get("/upcoming", response_model=AiringListOut)
def upcoming(
    limit: int = Query(48, ge=1, le=120),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Announced but not yet aired, soonest first, undated titles last."""
    _require_flag()
    rows = (
        _query(db, "upcoming")
        .order_by(
            AiringEntry.start_date.asc().nullslast(),
            AiringEntry.source_popularity.desc(),
        )
        .limit(limit)
        .all()
    )
    refreshed = _last_refresh(db)
    return AiringListOut(
        total=len(rows),
        items=_rows_to_out(db, rows, user),
        refreshed_at=refreshed,
        stale=bool(refreshed and _now() - refreshed > STALE_AFTER),
    )


@router.get("/schedule", response_model=AiringListOut)
def schedule(
    days: int = Query(7, ge=1, le=28),
    limit: int = Query(60, ge=1, le=200),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Episodes landing in the next `days`, in the order they will land."""
    _require_flag()
    horizon = _now() + timedelta(days=days)
    rows = (
        _query(db, "releasing")
        .filter(
            AiringEntry.next_episode_at.isnot(None),
            AiringEntry.next_episode_at <= horizon,
        )
        .order_by(AiringEntry.next_episode_at.asc())
        .limit(limit)
        .all()
    )
    refreshed = _last_refresh(db)
    return AiringListOut(
        total=len(rows),
        items=_rows_to_out(db, rows, user),
        refreshed_at=refreshed,
        stale=bool(refreshed and _now() - refreshed > STALE_AFTER),
    )


@router.get("/radar", response_model=AiringListOut)
def radar(
    limit: int = Query(30, ge=1, le=80),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """The point of the whole feature: what is coming that *you* care about.

    Three reasons a title earns a slot, strongest first:

    1. it is on your shelf and airing right now
    2. it is a new entry in a franchise you have already finished
    3. its genres line up with what you rate highly

    Everything is decided from rows this instance already owns, exactly like the
    Discover rail, so the ranking stays explainable.
    """
    _require_flag()

    library = (
        db.query(WatchlistItem, Anime)
        .join(Anime, Anime.id == WatchlistItem.anime_id)
        .filter(WatchlistItem.user_id == user.id)
        .all()
    )
    tracked_ids = {a.id for _, a in library}
    finished_keys = {
        a.franchise_key
        for item, a in library
        if item.status in ("completed", "watching") and a.franchise_key
    }

    liked_tags: set[str] = set()
    for item, anime in library:
        if item.status != "completed":
            continue
        for tag in (anime.genres or "").split(","):
            tag = tag.strip().lower()
            if tag:
                liked_tags.add(tag)

    rows = (
        safe_filter(db.query(AiringEntry, Anime).join(Anime, Anime.id == AiringEntry.anime_id))
        .order_by(
            AiringEntry.next_episode_at.asc().nullsfirst(),
            AiringEntry.source_popularity.desc(),
        )
        .limit(600)
        .all()
    )

    scored: list[tuple[float, tuple[AiringEntry, Anime], str]] = []
    for entry, anime in rows:
        if anime.id in tracked_ids and entry.airing_status == "releasing":
            scored.append((3.0, (entry, anime), "on your shelf and airing now"))
            continue
        if anime.id in tracked_ids:
            scored.append((2.5, (entry, anime), "on your shelf, not aired yet"))
            continue
        if anime.franchise_key and anime.franchise_key in finished_keys:
            scored.append((2.0, (entry, anime), "new entry in a franchise you follow"))
            continue
        tags = {t.strip().lower() for t in (anime.genres or "").split(",") if t.strip()}
        overlap = tags & liked_tags
        if overlap:
            share = len(overlap) / max(len(tags), 1)
            label = ", ".join(sorted(overlap)[:2])
            scored.append((1.0 + share, (entry, anime), f"matches your {label} streak"))

    scored.sort(key=lambda s: -s[0])
    picked = scored[:limit]
    reasons = {anime.id: why for _, (_, anime), why in picked}
    refreshed = _last_refresh(db)

    return AiringListOut(
        total=len(picked),
        items=_rows_to_out(db, [pair for _, pair, _ in picked], user, reasons),
        refreshed_at=refreshed,
        stale=bool(refreshed and _now() - refreshed > STALE_AFTER),
    )
