from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
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

    ratings: Mapped[list["Rating"]] = relationship(back_populates="anime")


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_anime_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="watchlist")
    anime: Mapped[Anime] = relationship()
