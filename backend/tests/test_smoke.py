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
        "/api/live/upcoming",
        "/api/live/schedule",
        "/api/live/radar",
        "/api/connect/accounts",
    ):
        assert path in paths, f"{path} is not mounted"


def test_live_routes_are_gated_and_status_still_answers(monkeypatch):
    """With the flag off the grids 404, but /status explains itself with a 200.

    The flag is forced through the env var rather than read from disk: a
    developer who has switched live data on for their own instance leaves a
    feature_flags.local.json behind, and this test must not depend on it.
    """
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import flags

    monkeypatch.setenv("KURA_FLAGS", "live_data=off")
    flags.load(force=True)
    try:
        assert flags.enabled("live_data", default=False) is False

        client = TestClient(app)
        for path in ("/api/live/upcoming", "/api/live/schedule"):
            assert client.get(path).status_code == 404

        body = client.get("/api/live/status").json()
        assert body["enabled"] is False
    finally:
        # Leave the shared flag cache the way we found it.
        monkeypatch.undo()
        flags.load(force=True)


def test_franchise_prefix_matching():
    assert same_franchise("gantz", "gantz stage")
    assert same_franchise("attack on titan", "attack on titan")
    assert not same_franchise("one piece", "one punch man")
    assert not same_franchise("", "gantz")
