"""Discovery surfaces that read attention signals.

The rail is the one place where impressions visibly change what you see: titles
you keep scrolling past sink, tags you have barely touched float up, and the
diversity slider decides how hard each of those pulls.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Anime, Impression, User, WatchlistItem
from app.schemas import (
    AnimeListOut,
    AnimeOut,
    FranchiseOut,
    SeasonBucketOut,
    SeasonListOut,
)
from app.services.attention import dismissed_genres, hidden_ids, rerank, view_counts
from app.services.flags import enabled
from app.services.library import episode_seconds_for, get_preferences
from app.services.ordering import best_first, safe_filter
from app.services.taste import blended_affinity

router = APIRouter(prefix="/api/discover", tags=["discover"])

SEASON_ORDER = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}


def _base_scores(items: list[Anime]) -> dict[int, float]:
    """Normalize catalog score into 0..1 so the boosts stay comparable."""
    scored = [a.score for a in items if a.score is not None]
    if not scored:
        return {a.id: 0.5 for a in items}
    low, high = min(scored), max(scored)
    span = (high - low) or 1.0
    return {
        a.id: ((a.score - low) / span) if a.score is not None else 0.35 for a in items
    }


@router.get("/rail")
def personal_rail(
    limit: int = Query(24, ge=1, le=60),
    diversity: float | None = Query(None, ge=0, le=1),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pool = (
        safe_filter(db.query(Anime))
        .filter(Anime.image_url.isnot(None), Anime.image_url != "")
        .order_by(*best_first())
        .limit(max(limit * 8, 200))
        .all()
    )
    if not user or not enabled("explore_boost"):
        return {
            "personalized": False,
            "diversity": diversity if diversity is not None else 0.35,
            "items": [
                {"anime": AnimeOut.model_validate(a), "score": 0.0, "why": "Top of the vault"}
                for a in pool[:limit]
            ],
        }

    prefs = get_preferences(db, user.id)
    db.commit()
    strength = diversity if diversity is not None else float(prefs.diversity or 0.35)

    blocked = hidden_ids(db, user.id)
    already = {
        row.anime_id
        for row in db.query(WatchlistItem)
        .filter(
            WatchlistItem.user_id == user.id,
            WatchlistItem.status.in_(("completed", "dropped")),
        )
        .all()
    }
    candidates = [a for a in pool if a.id not in blocked and a.id not in already]

    ranked = rerank(
        candidates,
        base_scores=_base_scores(candidates),
        affinity=blended_affinity(db, user.id, prefs),
        views=view_counts(db, user.id),
        penalties=dismissed_genres(db, user.id),
        diversity=strength,
    )
    return {
        "personalized": True,
        "diversity": round(strength, 2),
        "items": [
            {"anime": AnimeOut.model_validate(a), "score": s, "why": why}
            for a, s, why in ranked[:limit]
        ],
    }


@router.get("/almost")
def almost_clicked(
    limit: int = Query(12, ge=1, le=30),
    days: int = Query(7, ge=1, le=60),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Titles you lingered on and then scrolled past. Second chances."""
    if not user:
        return {"items": []}
    since = datetime.now(timezone.utc) - timedelta(days=days)

    hovered = dict(
        db.query(Impression.anime_id, func.coalesce(func.sum(Impression.dwell_ms), 0))
        .filter(
            Impression.user_id == user.id,
            Impression.kind.in_(("hover", "view")),
            Impression.created_at >= since,
            Impression.dwell_ms > 700,
        )
        .group_by(Impression.anime_id)
        .all()
    )
    if not hovered:
        return {"items": []}

    clicked = {
        aid
        for (aid,) in db.query(Impression.anime_id)
        .filter(
            Impression.user_id == user.id,
            Impression.kind == "click",
            Impression.created_at >= since,
        )
        .distinct()
        .all()
    }
    in_library = {
        row.anime_id
        for row in db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
    }
    blocked = hidden_ids(db, user.id) | clicked | in_library

    ranked = sorted(
        ((aid, ms) for aid, ms in hovered.items() if aid not in blocked),
        key=lambda kv: -kv[1],
    )[:limit]
    if not ranked:
        return {"items": []}

    by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_([a for a, _ in ranked])).all()}
    return {
        "items": [
            {
                "anime": AnimeOut.model_validate(by_id[aid]),
                "dwell_ms": int(ms),
                "why": f"You stared at this for {round(int(ms) / 1000, 1)}s and moved on",
            }
            for aid, ms in ranked
            if aid in by_id
        ]
    }


@router.get("/surprise")
def surprise_me(
    max_episodes: int | None = Query(None, ge=1, le=2000),
    min_score: float = Query(7.0, ge=0, le=10),
    genre: str | None = None,
    type: str | None = None,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Roulette with guardrails. Never lands on something you already finished."""
    if not enabled("surprise_me"):
        raise HTTPException(status_code=404, detail="Surprise is switched off on this instance")

    query = safe_filter(db.query(Anime)).filter(
        Anime.image_url.isnot(None), Anime.image_url != ""
    )
    if min_score:
        query = query.filter(or_(Anime.score >= min_score, Anime.score.is_(None)))
    if max_episodes:
        query = query.filter(Anime.episodes.isnot(None), Anime.episodes <= max_episodes)
    if genre:
        query = query.filter(Anime.genres.ilike(f"%{genre}%"))
    if type:
        query = query.filter(Anime.type == type)

    if user:
        seen = {
            row.anime_id
            for row in db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
        } | hidden_ids(db, user.id)
        if seen:
            query = query.filter(~Anime.id.in_(list(seen)))

    pool = query.order_by(*best_first()).limit(300).all()
    if not pool:
        raise HTTPException(status_code=404, detail="Nothing matches those constraints")

    pick = random.choice(pool)
    return {
        "anime": AnimeOut.model_validate(pick),
        "pool_size": len(pool),
        "why": "Rolled from titles that fit your constraints and are not on your shelf",
    }


@router.get("/smart", response_model=AnimeListOut)
def smart_filter(
    filter: str = Query("airing"),
    minutes: int = Query(180, ge=20, le=1440),
    limit: int = Query(24, ge=1, le=60),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Filters phrased the way people actually decide what to watch."""
    query = safe_filter(db.query(Anime)).filter(
        Anime.image_url.isnot(None), Anime.image_url != ""
    )
    key = (filter or "").strip().lower()

    if key == "airing":
        query = query.filter(Anime.status.ilike("%airing%"))
    elif key == "movies_under":
        query = query.filter(
            Anime.type == "Movie",
            or_(Anime.duration_minutes.is_(None), Anime.duration_minutes <= minutes),
        )
    elif key == "one_sitting":
        prefs = get_preferences(db, user.id) if user else None
        db.commit()
        pool = (
            query.filter(Anime.episodes.isnot(None), Anime.episodes <= 26)
            .order_by(*best_first())
            .limit(limit * 6)
            .all()
        )
        budget = minutes * 60
        picked = [
            a
            for a in pool
            if (a.episodes or 1) * episode_seconds_for(a, prefs) <= budget
        ][:limit]
        return AnimeListOut(total=len(picked), items=picked)
    elif key == "short":
        query = query.filter(Anime.episodes.isnot(None), Anime.episodes <= 13)
    elif key == "classics":
        query = query.filter(Anime.year.isnot(None), Anime.year <= 2005, Anime.score >= 7.5)
    elif key == "hidden_gems":
        query = query.filter(Anime.score >= 7.8, Anime.scored_by <= 60000)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown smart filter: {filter}")

    items = query.order_by(*best_first()).limit(limit).all()
    return AnimeListOut(total=len(items), items=items)


@router.get("/seasons", response_model=SeasonListOut)
def season_buckets(
    since_year: int = Query(2010, ge=1960, le=2100),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Anime.year, Anime.season, func.count(Anime.id))
        .filter(Anime.year.isnot(None), Anime.year >= since_year, Anime.season.isnot(None))
        .group_by(Anime.year, Anime.season)
        .all()
    )
    buckets = [
        SeasonBucketOut(year=int(year), season=str(season).lower(), count=int(count))
        for year, season, count in rows
        if season
    ]
    buckets.sort(key=lambda b: (-b.year, SEASON_ORDER.get(b.season, 9)))
    return SeasonListOut(buckets=buckets)


@router.get("/season/{year}/{season}", response_model=AnimeListOut)
def season_titles(
    year: int,
    season: str,
    limit: int = Query(48, ge=1, le=120),
    db: Session = Depends(get_db),
):
    items = (
        safe_filter(db.query(Anime))
        .filter(Anime.year == year, func.lower(Anime.season) == season.lower())
        .order_by(*best_first())
        .limit(limit)
        .all()
    )
    return AnimeListOut(total=len(items), items=items)


@router.get("/franchise/{anime_id}", response_model=FranchiseOut)
def franchise(anime_id: int, db: Session = Depends(get_db)):
    """Group the TV run, the movies, and the OVAs that share one franchise key."""
    anime = db.get(Anime, anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    key = anime.franchise_key or anime.title.lower()
    entries = (
        db.query(Anime)
        .filter(Anime.franchise_key == key)
        .order_by(Anime.year.asc().nullslast(), Anime.id.asc())
        .limit(30)
        .all()
    )
    if not entries:
        entries = [anime]
    return FranchiseOut(key=key, title=anime.title, entries=entries)
