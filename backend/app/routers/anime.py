from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Anime
from app.schemas import AnimeListOut, AnimeOut
from app.services.embeddings import embedding_index
from app.services.recommender import recommender

router = APIRouter(prefix="/api/anime", tags=["anime"])


@router.get("/search", response_model=AnimeListOut)
def search_anime(
    q: str = Query("", min_length=0),
    limit: int = Query(24, ge=1, le=100),
    mode: str = Query("hybrid", pattern="^(hybrid|semantic|lexical)$"),
    db: Session = Depends(get_db),
):
    if q.strip():
        if mode == "semantic":
            items = embedding_index.semantic_search(db, q, limit=limit)
        else:
            items = recommender.search(db, q, limit=limit)
    else:
        items = (
            db.query(Anime)
            .order_by(Anime.score.desc().nullslast(), Anime.popularity.asc())
            .limit(limit)
            .all()
        )
    return AnimeListOut(total=len(items), items=items)


@router.get("/browse", response_model=AnimeListOut)
def browse(
    genre: str | None = None,
    year: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Anime)
    if genre:
        query = query.filter(Anime.genres.ilike(f"%{genre}%"))
    if year:
        query = query.filter(Anime.year == year)
    total = query.count()
    items = (
        query.order_by(Anime.score.desc().nullslast(), Anime.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AnimeListOut(total=total, items=items)


@router.get("/{anime_id}", response_model=AnimeOut)
def get_anime(anime_id: int, db: Session = Depends(get_db)):
    anime = db.get(Anime, anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    return anime


@router.get("/{anime_id}/similar", response_model=list[AnimeOut])
def similar(anime_id: int, limit: int = 12, db: Session = Depends(get_db)):
    if not db.get(Anime, anime_id):
        raise HTTPException(status_code=404, detail="Anime not found")
    scored = recommender.similar_to(db, anime_id, limit=limit)
    return [s.anime for s in scored]
