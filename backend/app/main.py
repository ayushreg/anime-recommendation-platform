from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.middleware.rate_limit import RedisRateLimitMiddleware
from app.models import Anime, Rating, User
from app.routers import anime, auth, recs
from app.schemas import StatsOut
from app.services.cache import get_redis
from app.services.embeddings import embedding_index
from app.services.recommender import recommender

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Anime Recommendation Platform",
    description=(
        "Production-style hybrid recommender: TF-IDF content ranking, collaborative filtering, "
        "TruncatedSVD semantic embeddings, Redis caching, JWT auth, and Prometheus metrics."
    ),
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RedisRateLimitMiddleware, limit=180, window=60)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(auth.router)
app.include_router(anime.router)
app.include_router(recs.router)


@app.on_event("startup")
def startup_fit_model() -> None:
    db = SessionLocal()
    try:
        if db.query(Anime).count() > 0:
            recommender.fit(db)
            embedding_index.fit(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    from sqlalchemy import text

    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception:
        db_ok = False
    redis_ok = get_redis() is not None
    status = "ok" if db_ok and redis_ok else "degraded"
    return {
        "status": status,
        "postgres": db_ok,
        "redis": redis_ok,
        "embeddings": embedding_index.stats(),
        "recommender_ready": recommender._ready,
    }


@app.get("/api/stats", response_model=StatsOut)
def stats():
    db = SessionLocal()
    try:
        return StatsOut(
            anime_count=db.query(func.count(Anime.id)).scalar() or 0,
            user_count=db.query(func.count(User.id)).scalar() or 0,
            rating_count=db.query(func.count(Rating.id)).scalar() or 0,
            cache_backend="redis" if get_redis() else "disabled",
        )
    finally:
        db.close()
