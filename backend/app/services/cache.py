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


def cache_get(key: str) -> Any | None:
    client = get_redis()
    if not client:
        return None
    raw = client.get(key)
    if raw is None:
        return None
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
