import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.services.recommender import HybridRecommender, same_franchise


def test_recommender_instantiates():
    engine = HybridRecommender()
    assert engine._ready is False


def test_app_imports_and_mounts_every_router():
    from app.main import app

    assert app.title == "Kura Anime Vault"
    paths = {route.path for route in app.routes}
    for path in (
        "/api/health",
        "/api/stats",
        "/api/watch/heartbeat",
        "/api/signals/impressions",
        "/api/discover/rail",
        "/api/collections",
        "/api/insights/vault",
        "/api/me/preferences",
        "/api/social/feed",
        "/api/admin/overview",
        "/api/vault/export",
    ):
        assert path in paths, f"{path} is not mounted"


def test_franchise_prefix_matching():
    assert same_franchise("gantz", "gantz stage")
    assert same_franchise("attack on titan", "attack on titan")
    assert not same_franchise("one piece", "one punch man")
    assert not same_franchise("", "gantz")
