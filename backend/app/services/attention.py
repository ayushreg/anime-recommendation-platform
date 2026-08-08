"""Attention signals: what you looked at, how long, and what you skipped.

Everything here is derived from rows this instance already owns (impressions,
ratings, library progress, watch seconds). Nothing leaves the machine.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Anime, Impression, Rating, TitleFeedback, WatchlistItem

# How much a single repeated render dampens a title in the rail.
FATIGUE_PER_VIEW = 0.055
MAX_FATIGUE = 0.55


SMALL_WORDS = {"of", "the", "a", "an", "and", "in", "on", "to"}


def pretty_tag(tag: str) -> str:
    """The dump mixes 'Action' and 'action'. Pick one spelling and stick to it."""
    words = tag.strip().split()
    out: list[str] = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i > 0 and lower in SMALL_WORDS:
            out.append(lower)
        elif "-" in word:
            out.append("-".join(part.capitalize() for part in word.split("-")))
        else:
            out.append(word[:1].upper() + word[1:].lower())
    return " ".join(out)


def _split(raw: str | None) -> list[str]:
    """Tags, deduplicated and normalized so casing never splits a genre in two."""
    seen: dict[str, str] = {}
    for part in (raw or "").split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        seen.setdefault(cleaned.lower(), pretty_tag(cleaned))
    return list(seen.values())


@dataclass
class AttentionRow:
    anime_id: int
    views: int
    hovers: int
    clicks: int
    dwell_ms: int
    watch_seconds: int
    progress: int
    rating: float | None
    completed: bool

    @property
    def score(self) -> float:
        """A single 0..1-ish number blending every signal we have for a title."""
        click_rate = self.clicks / self.views if self.views else 0.0
        dwell = math.log1p(self.dwell_ms / 1000.0) / 6.0
        watch = math.log1p(self.watch_seconds / 60.0) / 8.0
        rating = ((self.rating or 0) / 10.0) if self.rating else 0.0
        finish = 0.25 if self.completed else 0.0
        raw = 0.9 * click_rate + 0.8 * dwell + 1.2 * watch + 1.4 * rating + finish
        return round(min(1.0, raw / 3.0), 4)


def attention_rows(db: Session, user_id: int, limit: int = 60) -> list[AttentionRow]:
    counters: dict[int, dict[str, int]] = defaultdict(
        lambda: {"view": 0, "hover": 0, "click": 0, "dwell": 0}
    )
    rows = (
        db.query(
            Impression.anime_id,
            Impression.kind,
            func.count(Impression.id),
            func.coalesce(func.sum(Impression.dwell_ms), 0),
        )
        .filter(Impression.user_id == user_id)
        .group_by(Impression.anime_id, Impression.kind)
        .all()
    )
    for anime_id, kind, count, dwell in rows:
        bucket = counters[anime_id]
        if kind in bucket:
            bucket[kind] += int(count)
        bucket["dwell"] += int(dwell or 0)

    library = {
        item.anime_id: item
        for item in db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id).all()
    }
    ratings = {
        r.anime_id: r.score for r in db.query(Rating).filter(Rating.user_id == user_id).all()
    }

    ids = set(counters) | set(library) | set(ratings)
    out: list[AttentionRow] = []
    for anime_id in ids:
        c = counters.get(anime_id, {"view": 0, "hover": 0, "click": 0, "dwell": 0})
        item = library.get(anime_id)
        out.append(
            AttentionRow(
                anime_id=anime_id,
                views=c["view"],
                hovers=c["hover"],
                clicks=c["click"],
                dwell_ms=c["dwell"],
                watch_seconds=int(getattr(item, "watch_seconds", 0) or 0),
                progress=int(getattr(item, "progress", 0) or 0),
                rating=ratings.get(anime_id),
                completed=bool(item and item.status == "completed"),
            )
        )
    out.sort(key=lambda r: -r.score)
    return out[:limit]


def view_counts(db: Session, user_id: int, since_days: int = 14) -> dict[int, int]:
    """How many times each poster has been rendered for this user lately."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    rows = (
        db.query(Impression.anime_id, func.count(Impression.id))
        .filter(
            Impression.user_id == user_id,
            Impression.kind == "view",
            Impression.created_at >= cutoff,
        )
        .group_by(Impression.anime_id)
        .all()
    )
    return {int(a): int(c) for a, c in rows}


def hidden_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(TitleFeedback.anime_id).filter(TitleFeedback.user_id == user_id).all()
    return {int(a) for (a,) in rows}


def genre_affinity(db: Session, user_id: int) -> dict[str, float]:
    """Normalized taste weights per genre, from ratings plus watch time."""
    weights: dict[str, float] = defaultdict(float)

    rated = (
        db.query(Anime.genres, Anime.themes, Rating.score)
        .join(Rating, Rating.anime_id == Anime.id)
        .filter(Rating.user_id == user_id)
        .all()
    )
    for genres, themes, score in rated:
        weight = (float(score) - 5.5) / 4.5  # negative below 5.5, positive above
        for tag in _split(genres) + _split(themes):
            weights[tag] += weight

    watched = (
        db.query(Anime.genres, Anime.themes, WatchlistItem.watch_seconds, WatchlistItem.progress)
        .join(WatchlistItem, WatchlistItem.anime_id == Anime.id)
        .filter(WatchlistItem.user_id == user_id)
        .all()
    )
    for genres, themes, seconds, progress in watched:
        weight = math.log1p((int(seconds or 0) / 600.0) + int(progress or 0)) / 3.0
        for tag in _split(genres) + _split(themes):
            weights[tag] += weight

    if not weights:
        return {}
    peak = max(abs(v) for v in weights.values()) or 1.0
    return {k: round(v / peak, 4) for k, v in weights.items()}


def dismissed_genres(db: Session, user_id: int) -> dict[str, int]:
    """Genres the user keeps saying no to. Used to dampen, never to hard filter."""
    rows = (
        db.query(Anime.genres)
        .join(TitleFeedback, TitleFeedback.anime_id == Anime.id)
        .filter(TitleFeedback.user_id == user_id)
        .all()
    )
    counts: dict[str, int] = defaultdict(int)
    for (genres,) in rows:
        for tag in _split(genres):
            counts[tag] += 1
    return dict(counts)


def rerank(
    items: list[Anime],
    *,
    base_scores: dict[int, float],
    affinity: dict[str, float],
    views: dict[int, int],
    penalties: dict[str, int],
    diversity: float = 0.35,
) -> list[tuple[Anime, float, str]]:
    """Explore versus exploit.

    Exploit pushes titles whose tags match your taste. Explore pays a bonus for
    tags you have barely touched, scaled by the diversity slider. Repeated
    renders get a fatigue discount so the same five posters stop hogging the top.
    """
    seen_tags = {tag for tag, weight in affinity.items() if abs(weight) > 0.12}
    ranked: list[tuple[Anime, float, str]] = []

    for anime in items:
        tags = _split(anime.genres) + _split(anime.themes)
        base = base_scores.get(anime.id, 0.0)

        exploit = sum(affinity.get(tag, 0.0) for tag in tags) / (len(tags) or 1)
        fresh = [t for t in tags if t not in seen_tags]
        explore = len(fresh) / (len(tags) or 1)
        penalty = sum(penalties.get(tag, 0) for tag in tags) * 0.04

        fatigue = min(MAX_FATIGUE, views.get(anime.id, 0) * FATIGUE_PER_VIEW)

        score = (
            base
            + (1.0 - diversity) * exploit * 0.8
            + diversity * explore * 0.6
            - penalty
            - fatigue
        )

        if fatigue > 0.2:
            why = "Dampened, you have scrolled past this a lot"
        elif fresh and diversity >= 0.5:
            why = f"Something new for you: {fresh[0]}"
        elif exploit > 0.25:
            top = max(tags, key=lambda t: affinity.get(t, 0.0), default="")
            why = f"Matches your {top} streak" if top else "Matches your taste profile"
        else:
            why = "Well rated in the vault"

        ranked.append((anime, round(score, 4), why))

    ranked.sort(key=lambda row: -row[1])
    return ranked
