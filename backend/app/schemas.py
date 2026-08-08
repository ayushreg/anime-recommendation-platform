from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnimeOut(BaseModel):
    id: int
    mal_id: int | None = None
    title: str
    title_english: str | None = None
    synopsis: str | None = None
    genres: str
    themes: str = ""
    studios: str = ""
    score: float | None = None
    scored_by: int = 0
    episodes: int | None = None
    status: str | None = None
    year: int | None = None
    image_url: str | None = None
    type: str | None = None
    popularity: int = 0
    season: str | None = None
    duration_minutes: int | None = None
    franchise_key: str | None = None

    model_config = {"from_attributes": True}


class AnimeListOut(BaseModel):
    total: int
    items: list[AnimeOut]
    # Extra vocabulary the semantic mode pulled in, shown as chips in the UI.
    expanded_terms: list[str] = Field(default_factory=list)


class SuggestItemOut(BaseModel):
    id: int
    title: str
    year: int | None = None
    type: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class SuggestOut(BaseModel):
    items: list[SuggestItemOut]


class GenresOut(BaseModel):
    genres: list[str]


class RatingIn(BaseModel):
    anime_id: int
    score: float = Field(ge=1, le=10)


class RatingOut(BaseModel):
    anime_id: int
    score: float
    anime: AnimeOut | None = None

    model_config = {"from_attributes": True}


class RecommendationOut(BaseModel):
    anime: AnimeOut
    reason: str
    score: float
    method: str
    seed_title: str | None = None
    shared_tags: list[str] = Field(default_factory=list)


class RecommendationsResponse(BaseModel):
    user_id: int | None
    cached: bool
    variant: str = "hybrid"
    diversity: float = 0.35
    recommendations: list[RecommendationOut]


class StatsOut(BaseModel):
    anime_count: int
    user_count: int
    rating_count: int
    cache_backend: str
    watch_hours: float = 0.0
    impression_count: int = 0


WATCH_STATUSES = ("plan_to_watch", "watching", "completed", "on_hold", "dropped")


class LibraryEntryIn(BaseModel):
    status: str = Field(default="plan_to_watch")
    progress: int | None = Field(default=None, ge=0, le=5000)

    def normalized_status(self) -> str:
        status = (self.status or "plan_to_watch").strip().lower().replace(" ", "_")
        if status not in WATCH_STATUSES:
            raise ValueError(f"status must be one of {WATCH_STATUSES}")
        return status


class LibraryEntryOut(BaseModel):
    anime_id: int
    status: str
    progress: int
    watch_seconds: int = 0
    rewatches: int = 0
    is_rewatching: bool = False
    completed_at: datetime | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None
    anime: AnimeOut | None = None

    model_config = {"from_attributes": True}


class ProgressBumpOut(BaseModel):
    anime_id: int
    status: str
    progress: int
    rewatches: int = 0
    is_rewatching: bool = False
    anime: AnimeOut | None = None


# --------------------------------------------------------------- telemetry


class SessionStartIn(BaseModel):
    anime_id: int
    device_id: str = Field(default="web", max_length=64)
    device_label: str | None = Field(default=None, max_length=80)
    source: Literal["timer", "manual", "demo"] = "timer"


class HeartbeatIn(BaseModel):
    session_id: int
    # Seconds of genuinely active attention since the previous beat.
    active_seconds: int = Field(ge=0, le=600)
    idle: bool = False


class WatchSessionOut(BaseModel):
    id: int
    anime_id: int
    device_id: str
    device_label: str | None = None
    active_seconds: int
    episodes_ticked: int
    carry_seconds: int
    source: str
    started_at: datetime | None = None
    last_beat_at: datetime | None = None
    ended_at: datetime | None = None
    anime: AnimeOut | None = None

    model_config = {"from_attributes": True}


class HeartbeatOut(BaseModel):
    session: WatchSessionOut
    ticked: int = 0
    progress: int = 0
    status: str = "watching"
    episode_seconds: int = 1440
    seconds_to_next: int = 0
    prompt: str | None = None
    conflict: bool = False


class WatchDayOut(BaseModel):
    day: date
    seconds: int
    episodes: int


class StreakOut(BaseModel):
    current_streak: int
    longest_streak: int
    total_hours: float
    week_hours: float
    days: list[WatchDayOut]


class MarkerIn(BaseModel):
    intro_start_s: int = Field(default=0, ge=0, le=7200)
    intro_end_s: int = Field(default=90, ge=0, le=7200)
    outro_start_s: int = Field(default=1320, ge=0, le=7200)


class MarkerOut(MarkerIn):
    anime_id: int

    model_config = {"from_attributes": True}


# ------------------------------------------------------------- impressions


class ImpressionIn(BaseModel):
    anime_id: int
    surface: str = Field(default="discover", max_length=32)
    kind: Literal["view", "hover", "click", "dismiss"] = "view"
    dwell_ms: int = Field(default=0, ge=0, le=3_600_000)
    position: int = Field(default=0, ge=0, le=10000)


class ImpressionBatchIn(BaseModel):
    events: list[ImpressionIn] = Field(default_factory=list, max_length=200)


class FeedbackIn(BaseModel):
    anime_id: int
    reason: Literal["not_interested", "seen_it", "wrong_vibe", "too_long", "hide"] = (
        "not_interested"
    )


class AttentionRowOut(BaseModel):
    anime_id: int
    title: str | None = None
    image_url: str | None = None
    score: float
    views: int
    clicks: int
    dwell_ms: int
    watch_seconds: int


# ------------------------------------------------------------- preferences


class PreferencesIn(BaseModel):
    diversity: float | None = Field(default=None, ge=0, le=1)
    ranking_variant: Literal["hybrid", "content", "collaborative", "popularity"] | None = None
    episode_minutes_tv: int | None = Field(default=None, ge=3, le=180)
    episode_minutes_movie: int | None = Field(default=None, ge=10, le=400)
    idle_timeout_seconds: int | None = Field(default=None, ge=30, le=1800)
    auto_tick: bool | None = None
    sound_enabled: bool | None = None
    poster_tint: bool | None = None
    share_activity: bool | None = None


class PreferencesOut(BaseModel):
    diversity: float
    ranking_variant: str
    episode_minutes_tv: int
    episode_minutes_movie: int
    idle_timeout_seconds: int
    auto_tick: bool
    sound_enabled: bool
    poster_tint: bool
    share_activity: bool
    quiz_done: bool
    taste: dict[str, float] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class QuizAnswerIn(BaseModel):
    question_id: str
    choice: str


class QuizSubmitIn(BaseModel):
    answers: list[QuizAnswerIn] = Field(default_factory=list, max_length=40)


class QuizQuestionOut(BaseModel):
    id: str
    prompt: str
    choices: list[dict[str, str]]


# ------------------------------------------------------------- collections


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    emoji: str = Field(default="*", max_length=8)
    description: str | None = Field(default=None, max_length=400)
    is_public: bool = False


class CollectionOut(BaseModel):
    id: int
    name: str
    slug: str
    emoji: str
    description: str | None = None
    is_public: bool = False
    count: int = 0
    covers: list[str] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CollectionDetailOut(CollectionOut):
    items: list[AnimeOut] = Field(default_factory=list)


class CollectionItemIn(BaseModel):
    anime_id: int
    note: str | None = Field(default=None, max_length=400)


class NoteIn(BaseModel):
    body: str = Field(default="", max_length=8000)
    is_shared: bool = False


class NoteOut(BaseModel):
    anime_id: int
    body: str
    is_shared: bool
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- insights


class TasteSliceOut(BaseModel):
    tag: str
    weight: float
    titles: int


class VaultHealthOut(BaseModel):
    backlog: int
    watching: int
    completed: int
    dropped: int
    on_hold: int
    average_score: float
    abandonment_rate: float
    episodes_watched: int
    hours_watched: float
    backlog_hours: float
    longest_backlog_title: str | None = None


class SimilarUserOut(BaseModel):
    user_id: int
    username: str
    affinity: float
    shared_titles: int
    picks: list[AnimeOut] = Field(default_factory=list)


class SeasonBucketOut(BaseModel):
    year: int
    season: str
    count: int


class SeasonListOut(BaseModel):
    buckets: list[SeasonBucketOut]


class FranchiseOut(BaseModel):
    key: str
    title: str
    entries: list[AnimeOut]


# ------------------------------------------------------------------ social


class FriendOut(BaseModel):
    user_id: int
    username: str
    friend_code: str | None = None
    hours_this_week: float = 0.0
    completed: int = 0


class FollowIn(BaseModel):
    friend_code: str = Field(min_length=4, max_length=32)


class ActivityOut(BaseModel):
    id: int
    username: str
    kind: str
    detail: str | None = None
    anime: AnimeOut | None = None
    created_at: datetime | None = None


class RecommendToFriendIn(BaseModel):
    friend_user_id: int
    anime_id: int
    note: str | None = Field(default=None, max_length=280)


# ------------------------------------------------------------------- admin


class AdminOverviewOut(BaseModel):
    anime_count: int
    user_count: int
    rating_count: int
    impression_count: int
    session_count: int
    active_sessions: int
    watch_hours: float
    cache: dict[str, Any]
    embeddings: dict[str, Any]
    flags: dict[str, bool]
    top_queries: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]


class FlagIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    enabled: bool


# ------------------------------------------------------------------- vault


class VaultExportOut(BaseModel):
    version: int
    exported_at: datetime
    username: str
    ratings: list[dict[str, Any]]
    library: list[dict[str, Any]]
    collections: list[dict[str, Any]]
    notes: list[dict[str, Any]]


class ImportResultOut(BaseModel):
    matched: int
    ratings_imported: int
    library_imported: int
    skipped: int
    notes: list[str] = Field(default_factory=list)
