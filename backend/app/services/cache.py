import json
from typing import Any

import redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    global _client
    if _client is not None:
        return _client
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _client = client
        return _client
    except Exception:
        return None


def _bump(result: str) -> None:
    """Count hits and misses in Redis so every worker shares one tally."""
    client = get_redis()
    if not client:
        return
    try:
        client.incr(f"stats:cache:{result}")
    except Exception:
        pass
    try:
        from app.services.metrics import CACHE_EVENTS

        CACHE_EVENTS.labels(result=result).inc()
    except Exception:
        pass


def cache_stats() -> dict[str, int | float]:
    client = get_redis()
    if not client:
        return {"hits": 0, "misses": 0, "hit_rate": 0.0}
    try:
        hits = int(client.get("stats:cache:hit") or 0)
        misses = int(client.get("stats:cache:miss") or 0)
    except Exception:
        hits, misses = 0, 0
    total = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hits / total, 4) if total else 0.0,
    }


def cache_get(key: str) -> Any | None:
    client = get_redis()
    if not client:
        return None
    raw = client.get(key)
    if raw is None:
        _bump("miss")
        return None
    _bump("hit")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def cache_set(key: str, value: Any, ttl: int | None = None) -> bool:
    client = get_redis()
    if not client:
        return False
    client.setex(key, ttl or settings.cache_ttl_seconds, json.dumps(value))
    return True


def cache_delete_pattern(pattern: str) -> None:
    client = get_redis()
    if not client:
        return
    for key in client.scan_iter(match=pattern, count=200):
        client.delete(key)
