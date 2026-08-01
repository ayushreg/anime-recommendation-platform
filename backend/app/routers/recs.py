from datetime import datetime, timezone

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
from app.services.cache import cache_delete_pattern
from app.services.recommender import recommender

router = APIRouter(prefix="/api", tags=["recommendations"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _library_out(item: WatchlistItem, anime: Anime | None = None) -> LibraryEntryOut:
    return LibraryEntryOut(
        anime_id=item.anime_id,
        status=item.status or "plan_to_watch",
        progress=int(item.progress or 0),
        updated_at=item.updated_at,
        created_at=item.created_at,
        anime=AnimeOut.model_validate(anime) if anime else None,
    )


def _upsert_library(
    db: Session,
    user_id: int,
    anime_id: int,
    *,
    status_value: str | None = None,
    progress: int | None = None,
) -> WatchlistItem:
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user_id, WatchlistItem.anime_id == anime_id)
        .first()
    )
    if not item:
        item = WatchlistItem(
            user_id=user_id,
            anime_id=anime_id,
            status=status_value or "plan_to_watch",
            progress=progress if progress is not None else 0,
            updated_at=_now(),
        )
        db.add(item)
    else:
        if status_value is not None:
            item.status = status_value
        if progress is not None:
            item.progress = progress
        item.updated_at = _now()
    return item


@router.get("/recommendations", response_model=RecommendationsResponse)
def recommendations(
    limit: int = Query(12, ge=1, le=50),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    scored, cached = recommender.recommend_for_user(db, user.id, limit=limit)
    return RecommendationsResponse(
        user_id=user.id,
        cached=cached,
        recommendations=[
            RecommendationOut(
                anime=AnimeOut.model_validate(s.anime),
                reason=s.reason,
                score=round(s.score, 4),
                method=s.method,
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
    else:
        rating = Rating(user_id=user.id, anime_id=payload.anime_id, score=payload.score)
        db.add(rating)

    # Auto-track: rating a show marks it completed (and fills episode progress when known).
    progress = anime.episodes if anime.episodes and anime.episodes > 0 else None
    item = _upsert_library(db, user.id, anime.id, status_value="completed", progress=progress)
    if progress is None and (item.progress or 0) == 0:
        item.progress = 1

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

    item = _upsert_library(
        db, user.id, anime_id, status_value=status_value, progress=int(progress or 0)
    )
    db.commit()
    db.refresh(item)
    return _library_out(item, anime)


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

    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.anime_id == anime_id)
        .first()
    )
    current = int(item.progress or 0) if item else 0
    nxt = current + 1
    status_value = "watching"
    if anime.episodes and nxt >= anime.episodes:
        nxt = anime.episodes
        status_value = "completed"

    item = _upsert_library(db, user.id, anime_id, status_value=status_value, progress=nxt)
    db.commit()
    db.refresh(item)
    return ProgressBumpOut(
        anime_id=anime_id,
        status=item.status,
        progress=item.progress,
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
            out.append(_library_out(row, anime))
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
    return [_library_out(r, db.get(Anime, r.anime_id)) for r in rows if db.get(Anime, r.anime_id)]


@router.post("/watchlist/{anime_id}", response_model=AnimeOut)
def add_watchlist(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    anime = db.get(Anime, anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    _upsert_library(db, user.id, anime_id, status_value="plan_to_watch")
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
