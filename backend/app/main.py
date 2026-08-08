from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.middleware.rate_limit import RedisRateLimitMiddleware
from app.migrate import ensure_schema
from app.models import Anime, Impression, Rating, User, WatchDay
from app.routers import (
    admin,
    anime,
    auth,
    collections,
    discovery,
    insights,
    prefs,
    recs,
    signals,
    social,
    vault,
    watch,
)
from app.schemas import StatsOut
from app.services import flags
from app.services.cache import cache_stats, get_redis
from app.services.embeddings import embedding_index
from app.services.recommender import recommender

Base.metadata.create_all(bind=engine)
ensure_schema(engine)

app = FastAPI(
    title="Kura Anime Vault",
    description=(
        "Local-first anime vault: hybrid search and recommendations, watch-time "
        "telemetry from your own tab, impression-aware ranking, collections, "
        "insights, and a JSONL event log for your own automation."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# This is a single household on one machine, not a public API. The limiter is
# here to stop a runaway client loop, so the ceiling is generous enough that
# heartbeats, impression batches, and normal browsing never brush against it.
app.add_middleware(RedisRateLimitMiddleware, limit=1800, window=60)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(auth.router)
app.include_router(anime.router)
app.include_router(recs.router)
app.include_router(watch.router)
app.include_router(signals.router)
app.include_router(discovery.router)
app.include_router(collections.router)
app.include_router(collections.notes_router)
app.include_router(insights.router)
app.include_router(prefs.router)
app.include_router(prefs.flags_router)
app.include_router(social.router)
app.include_router(admin.router)
app.include_router(vault.router)


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
        "cache": cache_stats(),
        "flags": flags.load(),
    }


@app.get("/api/stats", response_model=StatsOut)
def stats():
    db = SessionLocal()
    try:
        watch_seconds = db.query(func.coalesce(func.sum(WatchDay.seconds), 0)).scalar() or 0
        return StatsOut(
            anime_count=db.query(func.count(Anime.id)).scalar() or 0,
            user_count=db.query(func.count(User.id)).scalar() or 0,
            rating_count=db.query(func.count(Rating.id)).scalar() or 0,
            cache_backend="redis" if get_redis() else "disabled",
            watch_hours=round(watch_seconds / 3600, 2),
            impression_count=db.query(func.count(Impression.id)).scalar() or 0,
        )
    finally:
        db.close()
