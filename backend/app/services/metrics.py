"""Custom Prometheus series on top of the default FastAPI instrumentation."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

WATCH_SECONDS = Counter(
    "kura_watch_seconds_total",
    "Attention seconds accumulated from client heartbeats",
    ["source"],
)

EPISODES_TICKED = Counter(
    "kura_episodes_ticked_total",
    "Episodes marked watched",
    ["mode"],  # manual | auto
)

IMPRESSIONS = Counter(
    "kura_impressions_total",
    "Poster impressions logged",
    ["surface", "kind"],
)

RANKING_REQUESTS = Counter(
    "kura_ranking_requests_total",
    "Recommendation requests by ranking variant",
    ["variant", "cached"],
)

CACHE_EVENTS = Counter(
    "kura_cache_events_total",
    "Redis cache hits and misses",
    ["result"],
)

ACTIVE_SESSIONS = Gauge(
    "kura_active_watch_sessions",
    "Watch sessions with a heartbeat in the last two minutes",
)

RANKING_LATENCY = Histogram(
    "kura_ranking_seconds",
    "Time spent scoring a recommendation request",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
