"""Turning somebody else's list into rows in this vault.

Shared by every import path: the JSON restore, the MyAnimeList XML upload, and
the live account sync. They all arrive as the same list-of-dicts shape, so the
matching and writing lives here once instead of three times.
"""

from __future__ import annotations

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Anime, Rating
from app.schemas import ImportResultOut
from app.services.cache import cache_delete_pattern
from app.services.library import upsert_library


def normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def match_anime(db: Session, mal_id: int | None, title: str | None) -> Anime | None:
    """MAL id first, then exact title, then a loose contains match.

    The id is the only match we fully trust. Title matching is a fallback for
    rows that predate a MAL id, and it deliberately prefers the highest scored
    candidate so a common prefix lands on the title somebody actually meant.
    """
    if mal_id:
        row = db.query(Anime).filter(Anime.mal_id == mal_id).first()
        if row:
            return row
    if not title:
        return None
    row = db.query(Anime).filter(func.lower(Anime.title) == title.lower()).first()
    if row:
        return row
    row = db.query(Anime).filter(func.lower(Anime.title_english) == title.lower()).first()
    if row:
        return row
    if len(normalize_title(title)) < 4:
        return None
    return (
        db.query(Anime)
        .filter(Anime.title.ilike(f"%{title[:60]}%"))
        .order_by(Anime.score.desc().nullslast())
        .first()
    )


def apply_entries(
    db: Session,
    user_id: int,
    entries: list[dict],
    *,
    overwrite: bool,
) -> ImportResultOut:
    matched = 0
    ratings_imported = 0
    library_imported = 0
    skipped = 0
    notes: list[str] = []

    for entry in entries:
        anime = match_anime(db, entry.get("mal_id"), entry.get("title"))
        if not anime:
            skipped += 1
            if len(notes) < 12 and entry.get("title"):
                notes.append(f"No catalog match for {entry['title']}")
            continue
        matched += 1

        status_value = entry.get("status")
        progress = entry.get("progress")
        if status_value:
            item = upsert_library(
                db,
                user_id,
                anime.id,
                status_value=status_value,
                progress=int(progress or 0) if progress is not None else None,
            )
            if entry.get("rewatches"):
                item.rewatches = int(entry["rewatches"])
            if entry.get("watch_seconds"):
                item.watch_seconds = int(entry["watch_seconds"])
            library_imported += 1

        score = entry.get("score")
        if score:
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = None
        if score and 1 <= score <= 10:
            existing = (
                db.query(Rating)
                .filter(Rating.user_id == user_id, Rating.anime_id == anime.id)
                .first()
            )
            if existing and not overwrite:
                continue
            if existing:
                existing.score = score
            else:
                db.add(Rating(user_id=user_id, anime_id=anime.id, score=score))
            ratings_imported += 1

    db.commit()
    cache_delete_pattern(f"recs:user:{user_id}:*")
    return ImportResultOut(
        matched=matched,
        ratings_imported=ratings_imported,
        library_imported=library_imported,
        skipped=skipped,
        notes=notes,
    )
