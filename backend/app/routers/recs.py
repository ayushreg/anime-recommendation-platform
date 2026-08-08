import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import Anime, Rating, User, WatchlistItem
from app.schemas import (
    AnimeOut,
    LibraryEntryIn,
    LibraryEntryOut,
    ProgressBumpOut,
    RatingIn,
    RatingOut,
    RecommendationOut,
    RecommendationsResponse,
    WATCH_STATUSES,
)
from app.services import events
from app.services.attention import hidden_ids
from app.services.cache import cache_delete_pattern
from app.services.library import (
    advance_episode,
    get_preferences,
    library_out,
    now,
    upsert_library,
)
from app.services.metrics import EPISODES_TICKED, RANKING_LATENCY, RANKING_REQUESTS
from app.services.recommender import recommender

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.get("/recommendations", response_model=RecommendationsResponse)
def recommendations(
    limit: int = Query(12, ge=1, le=50),
    variant: str | None = Query(None, pattern="^(hybrid|content|collaborative|popularity)$"),
    diversity: float | None = Query(None, ge=0, le=1),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    prefs = get_preferences(db, user.id)
    db.commit()
    use_variant = variant or prefs.ranking_variant or "hybrid"
    use_diversity = diversity if diversity is not None else float(prefs.diversity or 0.35)

    started = time.perf_counter()
    scored, cached = recommender.recommend_for_user(
        db,
        user.id,
        limit=limit,
        variant=use_variant,
        diversity=use_diversity,
        exclude_ids=hidden_ids(db, user.id),
    )
    RANKING_LATENCY.observe(time.perf_counter() - started)
    RANKING_REQUESTS.labels(variant=use_variant, cached=str(bool(cached)).lower()).inc()

    return RecommendationsResponse(
        user_id=user.id,
        cached=cached,
        variant=use_variant,
        diversity=round(use_diversity, 2),
        recommendations=[
            RecommendationOut(
                anime=AnimeOut.model_validate(s.anime),
                reason=s.reason,
                score=round(s.score, 4),
                method=s.method,
                seed_title=s.seed_title,
                shared_tags=s.shared_tags or [],
            )
            for s in scored
        ],
    )


@router.post("/ratings", response_model=RatingOut)
def upsert_rating(
    payload: RatingIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    anime = db.get(Anime, payload.anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")

    rating = (
        db.query(Rating)
        .filter(Rating.user_id == user.id, Rating.anime_id == payload.anime_id)
        .first()
    )
    if rating:
        rating.score = payload.score
        rating.updated_at = now()
    else:
        rating = Rating(user_id=user.id, anime_id=payload.anime_id, score=payload.score)
        db.add(rating)

    # Auto-track: rating a show marks it completed (and fills episode progress when known).
    progress = anime.episodes if anime.episodes and anime.episodes > 0 else None
    item = upsert_library(db, user.id, anime.id, status_value="completed", progress=progress)
    if progress is None and (item.progress or 0) == 0:
        item.progress = 1

    events.record(
        db,
        user_id=user.id,
        kind="rated",
        anime_id=anime.id,
        detail=f"{anime.title} scored {payload.score:g}",
    )
    db.commit()
    cache_delete_pattern(f"recs:user:{user.id}:*")
    return RatingOut(anime_id=rating.anime_id, score=rating.score, anime=anime)


@router.get("/ratings/me", response_model=list[RatingOut])
def my_ratings(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.query(Rating).filter(Rating.user_id == user.id).all()
    return [
        RatingOut(anime_id=r.anime_id, score=r.score, anime=db.get(Anime, r.anime_id))
        for r in rows
    ]


@router.put("/library/{anime_id}", response_model=LibraryEntryOut)
def upsert_library_entry(
    anime_id: int,
    payload: LibraryEntryIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    anime = db.get(Anime, anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    try:
        status_value = payload.normalized_status()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    progress = payload.progress
    if progress is None:
        existing = (
            db.query(WatchlistItem)
            .filter(WatchlistItem.user_id == user.id, WatchlistItem.anime_id == anime_id)
            .first()
        )
        progress = existing.progress if existing else 0

    if anime.episodes and progress > anime.episodes:
        progress = anime.episodes

    # Completing via progress auto-flips status.
    if anime.episodes and progress >= anime.episodes and status_value == "watching":
        status_value = "completed"

    item = upsert_library(
        db, user.id, anime_id, status_value=status_value, progress=int(progress or 0)
    )
    if status_value in ("watching", "completed"):
        events.record(
            db,
            user_id=user.id,
            kind="completed" if status_value == "completed" else "watch_started",
            anime_id=anime.id,
            detail=anime.title,
        )
    db.commit()
    db.refresh(item)
    return library_out(item, anime)


@router.post("/library/{anime_id}/tick", response_model=ProgressBumpOut)
def tick_episode(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """+1 episode watched. Auto-starts Watching and auto-completes at the end."""
    anime = db.get(Anime, anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")

    item, finished = advance_episode(db, user.id, anime)
    EPISODES_TICKED.labels(mode="manual").inc()
    if finished:
        events.record(
            db, user_id=user.id, kind="completed", anime_id=anime.id, detail=anime.title
        )
    db.commit()
    db.refresh(item)
    return ProgressBumpOut(
        anime_id=anime_id,
        status=item.status,
        progress=item.progress,
        rewatches=int(item.rewatches or 0),
        is_rewatching=bool(item.is_rewatching),
        anime=AnimeOut.model_validate(anime),
    )


@router.get("/library", response_model=list[LibraryEntryOut])
def list_library(
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    query = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id)
    if status_filter:
        key = status_filter.strip().lower().replace(" ", "_")
        if key not in WATCH_STATUSES:
            raise HTTPException(status_code=400, detail=f"status must be one of {WATCH_STATUSES}")
        query = query.filter(WatchlistItem.status == key)
    rows = query.order_by(WatchlistItem.updated_at.desc().nullslast(), WatchlistItem.id.desc()).all()
    out: list[LibraryEntryOut] = []
    for row in rows:
        anime = db.get(Anime, row.anime_id)
        if anime:
            out.append(library_out(row, anime))
    return out


@router.get("/library/continue", response_model=list[LibraryEntryOut])
def continue_watching(
    limit: int = Query(12, ge=1, le=40),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.status == "watching")
        .order_by(WatchlistItem.updated_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [library_out(r, db.get(Anime, r.anime_id)) for r in rows if db.get(Anime, r.anime_id)]


@router.post("/watchlist/{anime_id}", response_model=AnimeOut)
def add_watchlist(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    anime = db.get(Anime, anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    upsert_library(db, user.id, anime_id, status_value="plan_to_watch")
    db.commit()
    return anime


@router.delete("/watchlist/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_watchlist(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.anime_id == anime_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/watchlist", response_model=list[AnimeOut])
def get_watchlist(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.updated_at.desc().nullslast())
        .all()
    )
    return [db.get(Anime, r.anime_id) for r in rows if db.get(Anime, r.anime_id)]
