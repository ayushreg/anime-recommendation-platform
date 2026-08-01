from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.services.cache import get_redis


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple fixed-window rate limiter backed by Redis (falls back to allow-all)."""

    def __init__(self, app, limit: int = 120, window: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client = get_redis()
        if client is None:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        bucket = int(time.time() // self.window)
        key = f"rl:{ip}:{bucket}"
        try:
            count = client.incr(key)
            if count == 1:
                client.expire(key, self.window + 1)
            remaining = max(0, self.limit - int(count))
            if count > self.limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again shortly."},
                    headers={
                        "X-RateLimit-Limit": str(self.limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(self.window),
                    },
                )
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response
        except Exception:
            return await call_next(request)
