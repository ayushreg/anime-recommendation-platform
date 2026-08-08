"""Impression and feedback capture.

The client batches poster renders, hovers, clicks, and dwell into one beacon so
scrolling a grid does not turn into a request per tile. All of it stays in this
instance's Postgres and only ever ranks that same account's shelves.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_user
from app.database import get_db
from app.models import Anime, Impression, TitleFeedback, User
from app.schemas import (
    AttentionRowOut,
    FeedbackIn,
    ImpressionBatchIn,
)
from app.services import events
from app.services.attention import attention_rows, dismissed_genres, hidden_ids
from app.services.flags import enabled
from app.services.metrics import IMPRESSIONS

router = APIRouter(prefix="/api/signals", tags=["signals"])

# Cap how much history one account can pile up before we prune the oldest rows.
MAX_ROWS_PER_USER = 20000


@router.post("/impressions", status_code=status.HTTP_202_ACCEPTED)
def log_impressions(
    payload: ImpressionBatchIn,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not enabled("impressions"):
        return {"accepted": 0, "disabled": True}
    if not payload.events:
        return {"accepted": 0}

    valid_ids = {
        row_id
        for (row_id,) in db.query(Anime.id)
        .filter(Anime.id.in_({e.anime_id for e in payload.events}))
        .all()
    }

    accepted = 0
    for event in payload.events:
        if event.anime_id not in valid_ids:
            continue
        db.add(
            Impression(
                user_id=user.id if user else None,
                anime_id=event.anime_id,
                surface=event.surface[:32],
                kind=event.kind,
                dwell_ms=event.dwell_ms,
                position=event.position,
            )
        )
        IMPRESSIONS.labels(surface=event.surface[:32], kind=event.kind).inc()
        accepted += 1

    db.commit()

    if user and accepted:
        _prune(db, user.id)
    return {"accepted": accepted}


def _prune(db: Session, user_id: int) -> None:
    total = db.query(func.count(Impression.id)).filter(Impression.user_id == user_id).scalar() or 0
    if total <= MAX_ROWS_PER_USER:
        return
    cutoff_id = (
        db.query(Impression.id)
        .filter(Impression.user_id == user_id)
        .order_by(Impression.id.desc())
        .offset(MAX_ROWS_PER_USER)
        .limit(1)
        .scalar()
    )
    if cutoff_id:
        db.query(Impression).filter(
            Impression.user_id == user_id, Impression.id <= cutoff_id
        ).delete(synchronize_session=False)
        db.commit()


@router.post("/feedback")
def give_feedback(
    payload: FeedbackIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    anime = db.get(Anime, payload.anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")

    row = (
        db.query(TitleFeedback)
        .filter(TitleFeedback.user_id == user.id, TitleFeedback.anime_id == anime.id)
        .first()
    )
    if row:
        row.reason = payload.reason
    else:
        db.add(TitleFeedback(user_id=user.id, anime_id=anime.id, reason=payload.reason))

    db.add(
        Impression(
            user_id=user.id,
            anime_id=anime.id,
            surface="feedback",
            kind="dismiss",
        )
    )
    events.record(
        db,
        user_id=user.id,
        kind="not_interested",
        anime_id=anime.id,
        detail=f"{anime.title}: {payload.reason}",
        persist=False,
    )
    db.commit()
    from app.services.cache import cache_delete_pattern

    cache_delete_pattern(f"recs:user:{user.id}:*")
    return {"anime_id": anime.id, "reason": payload.reason, "hidden": True}


@router.delete("/feedback/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def undo_feedback(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    db.query(TitleFeedback).filter(
        TitleFeedback.user_id == user.id, TitleFeedback.anime_id == anime_id
    ).delete(synchronize_session=False)
    db.commit()
    from app.services.cache import cache_delete_pattern

    cache_delete_pattern(f"recs:user:{user.id}:*")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/hidden")
def list_hidden(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = (
        db.query(TitleFeedback, Anime)
        .join(Anime, Anime.id == TitleFeedback.anime_id)
        .filter(TitleFeedback.user_id == user.id)
        .order_by(TitleFeedback.created_at.desc())
        .all()
    )
    return [
        {
            "anime_id": anime.id,
            "title": anime.title,
            "image_url": anime.image_url,
            "reason": fb.reason,
        }
        for fb, anime in rows
    ]


@router.get("/attention", response_model=list[AttentionRowOut])
def attention(
    limit: int = Query(24, ge=1, le=60),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    rows = attention_rows(db, user.id, limit=limit)
    by_id = {
        a.id: a
        for a in db.query(Anime).filter(Anime.id.in_([r.anime_id for r in rows])).all()
    }
    out: list[AttentionRowOut] = []
    for row in rows:
        anime = by_id.get(row.anime_id)
        out.append(
            AttentionRowOut(
                anime_id=row.anime_id,
                title=anime.title if anime else None,
                image_url=anime.image_url if anime else None,
                score=row.score,
                views=row.views,
                clicks=row.clicks,
                dwell_ms=row.dwell_ms,
                watch_seconds=row.watch_seconds,
            )
        )
    return out


@router.get("/summary")
def summary(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Numbers behind the ranking, shown in the metrics panel."""
    since = datetime.now(timezone.utc) - timedelta(days=30)
    counts = dict(
        db.query(Impression.kind, func.count(Impression.id))
        .filter(Impression.user_id == user.id, Impression.created_at >= since)
        .group_by(Impression.kind)
        .all()
    )
    views = int(counts.get("view", 0))
    clicks = int(counts.get("click", 0))
    dwell = (
        db.query(func.coalesce(func.avg(Impression.dwell_ms), 0))
        .filter(Impression.user_id == user.id, Impression.dwell_ms > 0)
        .scalar()
        or 0
    )
    surfaces = dict(
        db.query(Impression.surface, func.count(Impression.id))
        .filter(Impression.user_id == user.id, Impression.created_at >= since)
        .group_by(Impression.surface)
        .all()
    )
    return {
        "views": views,
        "hovers": int(counts.get("hover", 0)),
        "clicks": clicks,
        "dismissals": int(counts.get("dismiss", 0)),
        "click_through_rate": round(clicks / views, 4) if views else 0.0,
        "average_dwell_ms": int(dwell),
        "surfaces": {k: int(v) for k, v in surfaces.items()},
        "hidden_titles": len(hidden_ids(db, user.id)),
        "dampened_genres": dict(
            sorted(dismissed_genres(db, user.id).items(), key=lambda kv: -kv[1])[:8]
        ),
    }
