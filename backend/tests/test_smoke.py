import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.services.recommender import HybridRecommender


def test_recommender_instantiates():
    engine = HybridRecommender()
    assert engine._ready is False


def test_health_module_imports():
    from app.main import app

    assert app.title.startswith("Anime")
