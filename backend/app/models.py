from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    friend_code: Mapped[str | None] = mapped_column(String(16), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ratings: Mapped[list["Rating"]] = relationship(back_populates="user")
    watchlist: Mapped[list["WatchlistItem"]] = relationship(back_populates="user")


class Anime(Base):
    __tablename__ = "anime"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mal_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    title_english: Mapped[str | None] = mapped_column(String(512), nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    genres: Mapped[str] = mapped_column(String(512), default="")
    themes: Mapped[str] = mapped_column(String(512), default="")
    studios: Mapped[str] = mapped_column(String(512), default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    scored_by: Mapped[int] = mapped_column(Integer, default=0)
    episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    popularity: Mapped[int] = mapped_column(Integer, default=0)
    # winter | spring | summer | fall, from the Manami animeSeason block
    season: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    # Average runtime of a single episode, used by the watch timer and smart filters.
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Normalized franchise slug so sequels and movies group together.
    franchise_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)

    ratings: Mapped[list["Rating"]] = relationship(back_populates="anime")


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_anime_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="ratings")
    anime: Mapped[Anime] = relationship(back_populates="ratings")


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_anime_watch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    # plan_to_watch | watching | completed | on_hold | dropped
    status: Mapped[str] = mapped_column(String(32), default="plan_to_watch", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # episodes watched
    # Total attention time this account has spent on the title, in seconds.
    watch_seconds: Mapped[int] = mapped_column(Integer, default=0)
    rewatches: Mapped[int] = mapped_column(Integer, default=0)
    # Rewatch mode keeps the original completion date intact while progress moves again.
    is_rewatching: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="watchlist")
    anime: Mapped[Anime] = relationship()


class UserPreference(Base):
    """Per-account tuning for ranking, playback estimates, and UI chrome."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    # 0.0 = play it safe, 1.0 = throw me anything
    diversity: Mapped[float] = mapped_column(Float, default=0.35)
    # hybrid | content | collaborative | popularity
    ranking_variant: Mapped[str] = mapped_column(String(24), default="hybrid")
    episode_minutes_tv: Mapped[int] = mapped_column(Integer, default=24)
    episode_minutes_movie: Mapped[int] = mapped_column(Integer, default=100)
    idle_timeout_seconds: Mapped[int] = mapped_column(Integer, default=180)
    auto_tick: Mapped[bool] = mapped_column(Boolean, default=True)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    poster_tint: Mapped[bool] = mapped_column(Boolean, default=True)
    share_activity: Mapped[bool] = mapped_column(Boolean, default=True)
    quiz_done: Mapped[bool] = mapped_column(Boolean, default=False)
    # JSON blob of genre weights produced by the cold-start quiz
    taste_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WatchSession(Base):
    """One focused stretch of watching, measured by client heartbeats."""

    __tablename__ = "watch_sessions"
    __table_args__ = (Index("ix_watch_sessions_user_started", "user_id", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(String(64), default="web")
    device_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0)
    episodes_ticked: Mapped[int] = mapped_column(Integer, default=0)
    # seconds carried past the last auto tick, so partial episodes are not lost
    carry_seconds: Mapped[int] = mapped_column(Integer, default=0)
    # timer | manual | import | demo
    source: Mapped[str] = mapped_column(String(24), default="timer")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_beat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WatchDay(Base):
    """Daily rollup that powers the streak calendar without scanning every session."""

    __tablename__ = "watch_days"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_user_watch_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    episodes: Mapped[int] = mapped_column(Integer, default=0)


class Impression(Base):
    """Poster render, hover, and click telemetry. Stays on this instance."""

    __tablename__ = "impressions"
    __table_args__ = (Index("ix_impressions_user_anime", "user_id", "anime_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    # discover | for_you | detail | similar | collection | search
    surface: Mapped[str] = mapped_column(String(32), default="discover", index=True)
    # view | hover | click | dismiss
    kind: Mapped[str] = mapped_column(String(16), default="view", index=True)
    dwell_ms: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class TitleFeedback(Base):
    """Explicit negative signal, with the reason the user gave."""

    __tablename__ = "title_feedback"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_anime_feedback"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    # not_interested | seen_it | wrong_vibe | too_long | hide
    reason: Mapped[str] = mapped_column(String(32), default="not_interested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Collection(Base):
    """A user-made shelf that lives beside the status buckets."""

    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_user_collection_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), index=True)
    emoji: Mapped[str] = mapped_column(String(8), default="*")
    description: Mapped[str | None] = mapped_column(String(400), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "anime_id", name="uq_collection_anime"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    note: Mapped[str | None] = mapped_column(String(400), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Note(Base):
    """Private-by-default scratchpad attached to a title."""

    __tablename__ = "notes"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_anime_note"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EpisodeMarker(Base):
    """User-editable intro and outro timestamps for skip estimates."""

    __tablename__ = "episode_markers"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_anime_marker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    intro_start_s: Mapped[int] = mapped_column(Integer, default=0)
    intro_end_s: Mapped[int] = mapped_column(Integer, default=90)
    outro_start_s: Mapped[int] = mapped_column(Integer, default=1320)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Friendship(Base):
    """Follow edge between two accounts on the same instance."""

    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="uq_friend_edge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    friend_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActivityEvent(Base):
    """Feed row: rated, completed, started, recommended."""

    __tablename__ = "activity_events"
    __table_args__ = (Index("ix_activity_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int | None] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), index=True, nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # Set when a user recommends a title to a specific friend.
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SearchQueryLog(Base):
    """Aggregated query counter for the admin dashboard."""

    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
