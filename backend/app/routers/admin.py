"""Operator view of the instance.

Any signed-in account can open this: it is your machine, and hiding the cache
hit rate from the person running the container helps nobody.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import SessionLocal, get_db
from app.models import (
    Anime,
    Impression,
    Rating,
    SearchQueryLog,
    User,
    WatchDay,
    WatchSession,
)
from app.schemas import AdminOverviewOut, FlagIn
from app.services import events, flags
from app.services.cache import cache_stats
from app.services.embeddings import embedding_index
from app.services.library import now
from app.services.metrics import ACTIVE_SESSIONS
from app.services.recommender import recommender

router = APIRouter(prefix="/api/admin", tags=["admin"])


def log_query(query: str, results: int) -> None:
    """Fire and forget counter for the top-searches panel."""
    text = (query or "").strip().lower()[:200]
    if not text:
        return
    db = SessionLocal()
    try:
        row = db.query(SearchQueryLog).filter(SearchQueryLog.query == text).first()
        if row:
            row.hits = int(row.hits or 0) + 1
            row.results = results
        else:
            db.add(SearchQueryLog(query=text, hits=1, results=results))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@router.get("/overview", response_model=AdminOverviewOut)
def overview(user: User = Depends(require_user), db: Session = Depends(get_db)):
    live_cutoff = now() - timedelta(minutes=2)
    active = (
        db.query(func.count(WatchSession.id))
        .filter(WatchSession.ended_at.is_(None), WatchSession.last_beat_at >= live_cutoff)
        .scalar()
        or 0
    )
    ACTIVE_SESSIONS.set(active)

    watch_seconds = db.query(func.coalesce(func.sum(WatchDay.seconds), 0)).scalar() or 0

    top = (
        db.query(SearchQueryLog)
        .order_by(SearchQueryLog.hits.desc())
        .limit(12)
        .all()
    )

    return AdminOverviewOut(
        anime_count=db.query(func.count(Anime.id)).scalar() or 0,
        user_count=db.query(func.count(User.id)).scalar() or 0,
        rating_count=db.query(func.count(Rating.id)).scalar() or 0,
        impression_count=db.query(func.count(Impression.id)).scalar() or 0,
        session_count=db.query(func.count(WatchSession.id)).scalar() or 0,
        active_sessions=int(active),
        watch_hours=round(watch_seconds / 3600, 2),
        cache=cache_stats(),
        embeddings=embedding_index.stats(),
        flags=flags.load(),
        top_queries=[
            {"query": row.query, "hits": int(row.hits or 0), "results": int(row.results or 0)}
            for row in top
        ],
        recent_events=events.tail(20),
    )


@router.get("/impressions/timeline")
def impression_timeline(
    days: int = Query(14, ge=1, le=90),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    since = now() - timedelta(days=days)
    rows = (
        db.query(
            func.date(Impression.created_at).label("day"),
            Impression.kind,
            func.count(Impression.id),
        )
        .filter(Impression.created_at >= since)
        .group_by("day", Impression.kind)
        .all()
    )
    buckets: dict[str, dict[str, int]] = {}
    for day, kind, count in rows:
        key = str(day)
        buckets.setdefault(key, {})[kind] = int(count)
    return {
        "days": [
            {"day": day, **counts} for day, counts in sorted(buckets.items())
        ]
    }


@router.post("/flags")
def toggle_flag(payload: FlagIn, user: User = Depends(require_user)):
    return flags.set_flag(payload.name, payload.enabled)


@router.post("/refit")
def refit(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Force a model rebuild instead of waiting for the worker's next pass."""
    recommender.fit(db)
    embedding_index.fit(db)
    return {"refit": True, "embeddings": embedding_index.stats()}


@router.post("/events/trim")
def trim_events(user: User = Depends(require_user)):
    events.trim()
    return {"trimmed": True, "path": str(events.EVENT_LOG)}
