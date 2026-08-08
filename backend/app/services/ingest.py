"""Writing live rows into a catalog that was built offline.

The delicate part is not fetching, it is not wrecking what already works. Two
rules hold this together:

1. **A live refresh never overwrites a score.** The README's third challenge was
   getting "top of the vault" to mean something without any ratings in the dump,
   and that ordering leans on `score`, `scored_by`, and `mal_id`. A nightly job
   quietly rewriting those would undo it, so live data fills blanks only.
2. **Unreleased titles start with no score at all.** A show that has not aired
   cannot have earned a position in Discover, and leaving `score` null keeps it
   out of every "best first" query for free.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.migrate import franchise_key_for
from app.models import AiringEntry, Anime

# Columns a live refresh is allowed to write onto a row that already exists, and
# only when the existing value is empty. Everything not listed here, above all
# the ranking columns, is left exactly as the offline seed left it.
FILLABLE = (
    "title_english",
    "synopsis",
    "genres",
    "studios",
    "episodes",
    "duration_minutes",
    "image_url",
    "season",
    "year",
    "type",
)


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def upsert_anime(db: Session, row: dict) -> tuple[Anime, bool]:
    """Find this title by MAL id or create it. Returns (row, created)."""
    anime = db.query(Anime).filter(Anime.mal_id == row["mal_id"]).first()
    if anime:
        for field in FILLABLE:
            incoming = row.get(field)
            if incoming not in (None, "") and _blank(getattr(anime, field, None)):
                setattr(anime, field, incoming)
        if _blank(anime.franchise_key):
            anime.franchise_key = franchise_key_for(anime.title)
        return anime, False

    anime = Anime(
        mal_id=row["mal_id"],
        title=row["title"],
        title_english=row.get("title_english"),
        synopsis=row.get("synopsis"),
        genres=row.get("genres") or "",
        themes="",
        studios=row.get("studios") or "",
        # Deliberately no score: nothing unaired has earned one, and a null keeps
        # it out of every best-first ordering without a special case.
        score=None,
        scored_by=0,
        episodes=row.get("episodes"),
        status="upcoming",
        year=row.get("year"),
        image_url=row.get("image_url"),
        type=row.get("type") or "TV",
        popularity=0,
        season=row.get("season"),
        duration_minutes=row.get("duration_minutes"),
        franchise_key=franchise_key_for(row["title"]),
        catalog_source="live",
    )
    db.add(anime)
    db.flush()
    return anime, True


def upsert_airing(db: Session, anime_id: int, row: dict, airing_status: str) -> None:
    entry = db.query(AiringEntry).filter(AiringEntry.anime_id == anime_id).first()
    if not entry:
        entry = AiringEntry(anime_id=anime_id)
        db.add(entry)
    entry.airing_status = airing_status
    entry.next_episode = row.get("next_episode")
    entry.next_episode_at = row.get("next_episode_at")
    entry.start_date = row.get("start_date")
    entry.end_date = row.get("end_date")
    entry.episodes_total = row.get("episodes")
    entry.source_popularity = int(row.get("source_popularity") or 0)
    entry.source = "anilist"
    entry.refreshed_at = datetime.now(timezone.utc)


def ingest(db: Session, rows: list[dict], airing_status: str) -> dict[str, int]:
    """Write one batch of normalized live rows. Caller owns the commit."""
    created = 0
    for row in rows:
        anime, was_created = upsert_anime(db, row)
        created += int(was_created)
        upsert_airing(db, anime.id, row, airing_status)
    return {"seen": len(rows), "created": created}


def backfill_missing(db: Session, mal_ids: list[int], *, limit: int = 400) -> int:
    """Pull titles an import referenced but this catalog has never seen.

    The Manami dump is a subset, so anybody's real tracker list contains shows
    that are simply absent here, and dropping them makes a sync look broken:
    "33 of your 58 titles matched" reads as a bug even when it is honest. The
    list already told us the exact MyAnimeList ids, so we ask for precisely
    those. Returns how many new catalog rows were written.

    Airing state is deliberately not touched: these come back through a lookup
    by id, not a scan of what is currently on air, so nothing here should claim
    a slot on the Upcoming grid.
    """
    from app.services import live

    known = {
        row[0]
        for row in db.query(Anime.mal_id).filter(Anime.mal_id.in_(mal_ids or [0])).all()
        if row[0]
    }
    missing = [i for i in dict.fromkeys(mal_ids) if i and i not in known][:limit]
    if not missing:
        return 0

    created = 0
    for row in live.fetch_media_by_mal_ids(missing):
        _, was_created = upsert_anime(db, row)
        created += int(was_created)
    db.commit()
    return created


def prune_stale(db: Session, keep_mal_ids: set[int], airing_status: str) -> int:
    """Drop airing rows the source no longer reports for this status.

    A show that finished its run should stop claiming a countdown, and the
    cheapest way to be sure is to delete anything the latest refresh did not
    mention. Only the airing row goes; the catalog entry stays put.
    """
    if not keep_mal_ids:
        return 0
    stale = (
        db.query(AiringEntry)
        .join(Anime, Anime.id == AiringEntry.anime_id)
        .filter(
            AiringEntry.airing_status == airing_status,
            Anime.mal_id.notin_(keep_mal_ids),
        )
        .all()
    )
    for entry in stale:
        db.delete(entry)
    return len(stale)
