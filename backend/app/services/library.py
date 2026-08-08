"""Shared library writes so routers do not each grow their own copy."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Anime, UserPreference, WatchlistItem
from app.schemas import AnimeOut, LibraryEntryOut

DEFAULT_EPISODE_MINUTES = {
    "TV": 24,
    "ONA": 24,
    "OVA": 26,
    "Special": 25,
    "Movie": 100,
    "Music": 5,
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_preferences(db: Session, user_id: int) -> UserPreference:
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not prefs:
        prefs = UserPreference(user_id=user_id)
        db.add(prefs)
        db.flush()
    return prefs


def episode_seconds_for(anime: Anime, prefs: UserPreference | None) -> int:
    """How long one unit of progress takes for this title, in seconds."""
    kind = (anime.type or "TV").strip()
    if anime.duration_minutes and anime.duration_minutes > 0:
        minutes = anime.duration_minutes
    elif prefs and kind == "Movie":
        minutes = prefs.episode_minutes_movie
    elif prefs and kind in ("TV", "ONA"):
        minutes = prefs.episode_minutes_tv
    else:
        minutes = DEFAULT_EPISODE_MINUTES.get(kind, 24)
    return max(60, int(minutes) * 60)


def library_out(item: WatchlistItem, anime: Anime | None = None) -> LibraryEntryOut:
    return LibraryEntryOut(
        anime_id=item.anime_id,
        status=item.status or "plan_to_watch",
        progress=int(item.progress or 0),
        watch_seconds=int(item.watch_seconds or 0),
        rewatches=int(item.rewatches or 0),
        is_rewatching=bool(item.is_rewatching),
        completed_at=item.completed_at,
        updated_at=item.updated_at,
        created_at=item.created_at,
        anime=AnimeOut.model_validate(anime) if anime else None,
    )


def upsert_library(
    db: Session,
    user_id: int,
    anime_id: int,
    *,
    status_value: str | None = None,
    progress: int | None = None,
) -> WatchlistItem:
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user_id, WatchlistItem.anime_id == anime_id)
        .first()
    )
    if not item:
        item = WatchlistItem(
            user_id=user_id,
            anime_id=anime_id,
            status=status_value or "plan_to_watch",
            progress=progress if progress is not None else 0,
            updated_at=now(),
        )
        db.add(item)
    else:
        if status_value is not None:
            item.status = status_value
        if progress is not None:
            item.progress = progress
        item.updated_at = now()

    if item.status == "completed" and item.completed_at is None:
        item.completed_at = now()
    return item


def advance_episode(
    db: Session, user_id: int, anime: Anime, *, steps: int = 1
) -> tuple[WatchlistItem, bool]:
    """+N episodes. Returns the row and whether this advance finished the title.

    In rewatch mode the original completion date is preserved and finishing the
    run bumps the rewatch counter instead of rewriting history.
    """
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user_id, WatchlistItem.anime_id == anime.id)
        .first()
    )
    current = int(item.progress or 0) if item else 0
    rewatching = bool(item.is_rewatching) if item else False

    nxt = current + max(1, steps)
    finished = False
    status_value = "watching"
    if anime.episodes and nxt >= anime.episodes:
        nxt = anime.episodes
        finished = True
        status_value = "completed"

    item = upsert_library(db, user_id, anime.id, status_value=status_value, progress=nxt)

    if finished and rewatching:
        item.rewatches = int(item.rewatches or 0) + 1
        item.is_rewatching = False
        item.progress = anime.episodes or nxt
        # completed_at stays on the first finish so the original date survives.
    return item, finished


def start_rewatch(db: Session, user_id: int, anime: Anime) -> WatchlistItem:
    item = upsert_library(db, user_id, anime.id, status_value="watching", progress=0)
    item.is_rewatching = True
    return item
