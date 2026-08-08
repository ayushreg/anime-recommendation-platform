"""One shared idea of what "top of the vault" means.

The Manami dump carries no scores, so ordering by score alone leaves roughly
twelve thousand rows tied at NULL and the tiebreak lands wherever the table
happens to sit. A low MyAnimeList id is the honest signal we do have: ids were
handed out in registration order, so anything under a few thousand is an older
title that stayed on the site long enough to be catalogued early. That plus the
scores we do have gives every "best first" list something sensible to say.
"""

from __future__ import annotations

from sqlalchemy import not_, or_

from app.models import Anime

# Titles most people would recognize by name tend to sit under this id.
RECOGNIZABLE_MAL_ID = 45000

# The Manami dump includes adult catalogue entries. Kura is a shelf you might
# open in front of other people, so these stay out of every browse, rail, and
# recommendation unless somebody searches for them by name.
ADULT_TAGS = (
    "hentai",
    "erotica",
    "adult audience only",
    "explicit sex",
    "pornography",
    "borderline porn",
    "sexual content",
    "nudity",
)


def is_adult(anime: Anime) -> bool:
    haystack = f"{anime.genres or ''},{anime.themes or ''}".lower()
    return any(tag in haystack for tag in ADULT_TAGS)


def safe_filter(query):
    """Drop adult-tagged rows from a query."""
    clauses = []
    for tag in ADULT_TAGS:
        pattern = f"%{tag}%"
        clauses.append(
            or_(Anime.genres.ilike(pattern), Anime.themes.ilike(pattern))
        )
    return query.filter(not_(or_(*clauses)))


def best_first():
    """Ordering tuple for any "show me the good stuff" query."""
    return (
        Anime.score.desc().nullslast(),
        Anime.scored_by.desc(),
        Anime.mal_id.asc().nullslast(),
        Anime.id.asc(),
    )


def marquee_filter(query):
    """Narrow a query to full-length titles a person is likely to have heard of."""
    return safe_filter(
        query.filter(
            Anime.image_url.isnot(None),
            Anime.image_url != "",
            Anime.mal_id.isnot(None),
            Anime.mal_id <= RECOGNIZABLE_MAL_ID,
            Anime.type.in_(("TV", "Movie", "ONA")),
        )
    )
