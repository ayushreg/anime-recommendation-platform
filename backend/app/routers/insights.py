"""Read-only views over your own vault: taste shape, backlog health, neighbors."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import Anime, Rating, User, WatchlistItem
from app.schemas import (
    AnimeOut,
    RecommendationOut,
    SimilarUserOut,
    TasteSliceOut,
    VaultHealthOut,
)
from app.services.attention import _split as split_tags, genre_affinity
from app.services.library import episode_seconds_for, get_preferences
from app.services.recommender import recommender

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/taste", response_model=list[TasteSliceOut])
def taste_dna(
    limit: int = Query(10, ge=3, le=24),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """The radar chart on the Insights page. Ratings and watch time, not clicks."""
    affinity = genre_affinity(db, user.id)

    counts: Counter[str] = Counter()
    rows = (
        db.query(Anime.genres, Anime.themes)
        .join(WatchlistItem, WatchlistItem.anime_id == Anime.id)
        .filter(WatchlistItem.user_id == user.id)
        .all()
    )
    for genres, themes in rows:
        for tag in split_tags(genres) + split_tags(themes):
            counts[tag] += 1

    ranked = sorted(affinity.items(), key=lambda kv: -kv[1])[:limit]
    return [
        TasteSliceOut(tag=tag, weight=round(max(0.0, weight), 4), titles=counts.get(tag, 0))
        for tag, weight in ranked
    ]


@router.get("/vault", response_model=VaultHealthOut)
def vault_health(user: User = Depends(require_user), db: Session = Depends(get_db)):
    prefs = get_preferences(db, user.id)
    db.commit()

    rows = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
    buckets = Counter(r.status or "plan_to_watch" for r in rows)

    started = buckets["watching"] + buckets["completed"] + buckets["dropped"] + buckets["on_hold"]
    abandoned = buckets["dropped"] + buckets["on_hold"]

    average = (
        db.query(func.coalesce(func.avg(Rating.score), 0))
        .filter(Rating.user_id == user.id)
        .scalar()
        or 0
    )

    episodes = sum(int(r.progress or 0) for r in rows)
    seconds = sum(int(r.watch_seconds or 0) for r in rows)

    backlog_seconds = 0
    longest_title = None
    longest_seconds = 0
    for item in rows:
        if (item.status or "") not in ("plan_to_watch", "on_hold", "watching"):
            continue
        anime = db.get(Anime, item.anime_id)
        if not anime:
            continue
        left = max(0, (anime.episodes or 1) - int(item.progress or 0))
        needed = left * episode_seconds_for(anime, prefs)
        backlog_seconds += needed
        if needed > longest_seconds:
            longest_seconds = needed
            longest_title = anime.title

    return VaultHealthOut(
        backlog=buckets["plan_to_watch"],
        watching=buckets["watching"],
        completed=buckets["completed"],
        dropped=buckets["dropped"],
        on_hold=buckets["on_hold"],
        average_score=round(float(average), 2),
        abandonment_rate=round(abandoned / started, 3) if started else 0.0,
        episodes_watched=episodes,
        hours_watched=round(seconds / 3600, 2),
        backlog_hours=round(backlog_seconds / 3600, 1),
        longest_backlog_title=longest_title,
    )


@router.get("/similar-users", response_model=list[SimilarUserOut])
def similar_users(
    limit: int = Query(6, ge=1, le=20),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Accounts on this instance whose scores correlate with yours."""
    my_ratings = {
        r.anime_id: r.score for r in db.query(Rating).filter(Rating.user_id == user.id).all()
    }
    weights = recommender.neighbor_weights(db, user.id, my_ratings)
    if not weights:
        return []

    top = sorted(weights.items(), key=lambda kv: -kv[1])[:limit]
    users = {
        u.id: u for u in db.query(User).filter(User.id.in_([uid for uid, _ in top])).all()
    }

    out: list[SimilarUserOut] = []
    for uid, affinity in top:
        neighbor = users.get(uid)
        if not neighbor:
            continue
        their = (
            db.query(Rating)
            .filter(Rating.user_id == uid, Rating.score >= 8)
            .order_by(Rating.score.desc())
            .limit(20)
            .all()
        )
        shared = sum(1 for r in their if r.anime_id in my_ratings)
        picks_ids = [r.anime_id for r in their if r.anime_id not in my_ratings][:4]
        picks = db.query(Anime).filter(Anime.id.in_(picks_ids)).all() if picks_ids else []
        out.append(
            SimilarUserOut(
                user_id=uid,
                username=neighbor.username,
                affinity=round(float(affinity), 3),
                shared_titles=shared,
                picks=[AnimeOut.model_validate(a) for a in picks],
            )
        )
    return out


@router.get("/next-up", response_model=list[RecommendationOut])
def next_up(
    limit: int = Query(8, ge=1, le=24),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Sequence model: what people on this instance finished right after your last watch."""
    scored = recommender.next_title_markov(db, user.id, limit=limit)
    return [
        RecommendationOut(
            anime=AnimeOut.model_validate(s.anime),
            reason=s.reason,
            score=round(s.score, 4),
            method=s.method,
            seed_title=s.seed_title,
            shared_tags=s.shared_tags or [],
        )
        for s in scored
    ]
