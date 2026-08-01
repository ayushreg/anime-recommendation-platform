from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import Anime, Rating, User, WatchlistItem
from app.schemas import AnimeOut, RatingIn, RatingOut, RecommendationOut, RecommendationsResponse
from app.services.cache import cache_delete_pattern
from app.services.recommender import recommender

router = APIRouter(prefix="/api", tags=["recommendations"])


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


@router.post("/watchlist/{anime_id}", response_model=AnimeOut)
def add_watchlist(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    anime = db.get(Anime, anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.anime_id == anime_id)
        .first()
    )
    if not existing:
        db.add(WatchlistItem(user_id=user.id, anime_id=anime_id))
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
    rows = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
    return [db.get(Anime, r.anime_id) for r in rows if db.get(Anime, r.anime_id)]
