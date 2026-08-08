from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://anime:anime@localhost:5432/anime_recs"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    cache_ttl_seconds: int = 600
    seed_target_count: int = 12000

    # --- live data (opt-in, off unless the live_data flag is on) -------------
    # AniList is the primary source: it is a real API rather than a scraper, it
    # hands back exact per-episode airing timestamps, and every row carries an
    # idMal so it joins straight onto the offline catalog.
    anilist_url: str = "https://graphql.anilist.co"
    # MyAnimeList's own list endpoint, the one its list page calls. No app
    # registration and no token, but it does expect a browser-shaped request.
    mal_list_url: str = "https://myanimelist.net/animelist"
    mal_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    # Jikan proxies MyAnimeList by scraping it, so it is only a fallback for the
    # MAL list link.
    jikan_base_url: str = "https://api.jikan.moe/v4"
    live_timeout_seconds: float = 20.0
    # Airing data moves once a day at most, so a long TTL keeps us well clear of
    # both services' rate limits.
    live_cache_ttl_seconds: int = 6 * 3600
    live_refresh_interval_seconds: int = 6 * 3600
    # Ceiling on how many live titles one refresh will write into the catalog.
    live_ingest_limit: int = 300

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
