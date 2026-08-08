from collections import Counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Anime
from app.schemas import AnimeListOut, AnimeOut, GenresOut, SuggestItemOut, SuggestOut
from app.services.embeddings import embedding_index
from app.services.ordering import best_first, safe_filter
from app.services.recommender import recommender

router = APIRouter(prefix="/api/anime", tags=["anime"])


@router.get("/search", response_model=AnimeListOut)
def search_anime(
    background: BackgroundTasks,
    q: str = Query("", min_length=0),
    limit: int = Query(24, ge=1, le=100),
    mode: str = Query("hybrid", pattern="^(hybrid|semantic|lexical)$"),
    expand: bool = Query(True),
    db: Session = Depends(get_db),
):
    expanded_terms: list[str] = []
    if q.strip():
        if mode == "semantic":
            if expand:
                _, expanded_terms = embedding_index.expand_query(q)
            items = embedding_index.semantic_search(db, q, limit=limit, expand=expand)
        elif mode == "lexical":
            items = recommender.search(db, q, limit=limit, lexical_only=True)
        else:
            items = recommender.search(db, q, limit=limit)

        from app.routers.admin import log_query

        background.add_task(log_query, q, len(items))
    else:
        items = (
            safe_filter(db.query(Anime))
            .order_by(*best_first())
            .limit(limit)
            .all()
        )
    response = AnimeListOut(total=len(items), items=items)
    if expanded_terms:
        # Surfaced in the UI so people can see what the semantic mode added.
        response.expanded_terms = expanded_terms
    return response


@router.get("/browse", response_model=AnimeListOut)
def browse(
    genre: str | None = None,
    year: int | None = None,
    type: str | None = None,
    studio: str | None = None,
    year_min: int | None = Query(None, ge=1900, le=2100),
    year_max: int | None = Query(None, ge=1900, le=2100),
    min_score: float | None = Query(None, ge=0, le=10),
    max_episodes: int | None = Query(None, ge=1, le=5000),
    sort: str = Query("score", pattern="^(score|year|episodes|title|popularity)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = safe_filter(db.query(Anime))
    if genre:
        query = query.filter(Anime.genres.ilike(f"%{genre}%"))
    if year:
        query = query.filter(Anime.year == year)
    if year_min:
        query = query.filter(Anime.year >= year_min)
    if year_max:
        query = query.filter(Anime.year <= year_max)
    if type:
        query = query.filter(Anime.type == type)
    if studio:
        query = query.filter(Anime.studios.ilike(f"%{studio}%"))
    if min_score is not None:
        query = query.filter(Anime.score >= min_score)
    if max_episodes:
        query = query.filter(Anime.episodes.isnot(None), Anime.episodes <= max_episodes)

    total = query.count()

    order = {
        "score": best_first(),
        "year": (Anime.year.desc().nullslast(), Anime.id.asc()),
        "episodes": (Anime.episodes.desc().nullslast(), Anime.id.asc()),
        "title": (Anime.title.asc(), Anime.id.asc()),
        "popularity": (Anime.scored_by.desc().nullslast(), Anime.id.asc()),
    }[sort]

    items = (
        query.order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AnimeListOut(total=total, items=items)


# The offline catalog tags everything: "based on a manga", "asia", "cg animation".
# Useful metadata, terrible filter chips. This is the vocabulary people actually
# browse by, matched case-insensitively against whatever the dump calls it.
GENRE_VOCABULARY = [
    "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror", "Mystery",
    "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Thriller",
    "Mecha", "Music", "Psychological", "School", "Historical", "Military",
    "Isekai", "Martial Arts", "Space", "Vampire", "Samurai", "Magic",
    "Superhero", "Detective", "Post-Apocalyptic", "Time Travel", "Idols",
]

ALIASES = {
    "sci fi": "Sci-Fi",
    "science fiction": "Sci-Fi",
    "slice-of-life": "Slice of Life",
    "post apocalyptic": "Post-Apocalyptic",
    "martial-arts": "Martial Arts",
    "shounen": "Action",
}


@router.get("/genres", response_model=GenresOut)
def list_genres(db: Session = Depends(get_db)):
    """Browsable genres, ordered by how much of the catalog each one covers."""
    lookup = {g.lower(): g for g in GENRE_VOCABULARY}
    lookup.update({k: v for k, v in ALIASES.items()})

    rows = db.query(Anime.genres, Anime.themes).filter(
        Anime.genres.isnot(None), Anime.genres != ""
    ).all()
    counts: Counter[str] = Counter()
    for genres, themes in rows:
        seen: set[str] = set()
        for part in f"{genres or ''},{themes or ''}".split(","):
            canonical = lookup.get(part.strip().lower())
            if canonical and canonical not in seen:
                counts[canonical] += 1
                seen.add(canonical)

    ranked = [name for name, _ in counts.most_common(24)]
    # A brand new or synthetic catalog may not match anything. Show the
    # vocabulary rather than an empty filter row.
    return GenresOut(genres=ranked or GENRE_VOCABULARY[:16])


@router.get("/studios")
def list_studios(limit: int = Query(30, ge=1, le=120), db: Session = Depends(get_db)):
    rows = db.query(Anime.studios).filter(Anime.studios.isnot(None), Anime.studios != "").all()
    counts: Counter[str] = Counter()
    for (raw,) in rows:
        for part in (raw or "").split(","):
            name = part.strip()
            if name:
                counts[name] += 1
    return {"studios": [{"name": n, "titles": c} for n, c in counts.most_common(limit)]}


@router.get("/suggest", response_model=SuggestOut)
def suggest_anime(
    q: str = Query("", min_length=0),
    db: Session = Depends(get_db),
):
    q = q.strip()
    if not q:
        return SuggestOut(items=[])
    pattern = f"%{q}%"
    rows = (
        safe_filter(db.query(Anime))
        .filter(or_(Anime.title.ilike(pattern), Anime.title_english.ilike(pattern)))
        .order_by(Anime.score.desc().nullslast())
        .limit(8)
        .all()
    )
    return SuggestOut(
        items=[
            SuggestItemOut(
                id=a.id,
                title=a.title,
                year=a.year,
                type=a.type,
                image_url=a.image_url,
            )
            for a in rows
        ]
    )


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
