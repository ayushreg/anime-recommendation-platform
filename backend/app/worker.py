#!/usr/bin/env python
"""Background worker: refits TF-IDF + embedding indexes, and refreshes live data.

The refit runs every cycle. The live refresh only runs when the `live_data` flag
is on and its own longer interval has elapsed, so a machine with the flag off
never opens a socket to anybody.
"""

from __future__ import annotations

import time

from app.config import settings
from app.database import SessionLocal
from app.models import Anime, LinkedAccount
from app.services import ingest, live
from app.services.embeddings import embedding_index
from app.services.flags import enabled
from app.services.recommender import recommender

REFIT_INTERVAL_SECONDS = 300


def refit_once() -> None:
    db = SessionLocal()
    try:
        count = db.query(Anime).count()
        if count == 0:
            print("worker: no anime rows yet")
            return
        print(f"worker: refitting models on {count} titles...")
        recommender.fit(db)
        embedding_index.fit(db)
        print("worker: refit complete", embedding_index.stats())
    finally:
        db.close()


def refresh_live_once() -> None:
    """Pull airing data, then re-sync every account that opted into auto sync."""
    if not enabled("live_data", default=False):
        return

    db = SessionLocal()
    try:
        limit = max(50, settings.live_ingest_limit // 2)
        for anilist_status, local_status in (
            ("RELEASING", "releasing"),
            ("NOT_YET_RELEASED", "upcoming"),
        ):
            rows = live.fetch_airing(anilist_status, limit=limit, use_cache=False)
            stats = ingest.ingest(db, rows, local_status)
            ingest.prune_stale(db, {r["mal_id"] for r in rows}, local_status)
            db.commit()
            print(
                f"worker: live {local_status} -> {stats['seen']} seen, "
                f"{stats['created']} new titles"
            )

        for account in db.query(LinkedAccount).filter(LinkedAccount.auto_sync.is_(True)).all():
            # Imported here to avoid a circular import at module load: the
            # router imports the services this module already pulled in.
            from app.routers.connect import sync_account

            try:
                result = sync_account(db, account)
                print(
                    f"worker: synced {account.provider}/{account.external_username} "
                    f"-> {result.matched} matched"
                )
            except Exception as exc:
                # sync_account has already written the reason onto the account,
                # so the settings page can explain it. Keep the loop alive.
                print(f"worker: sync failed for {account.provider}: {exc}")
    except live.LiveUnavailable as exc:
        print(f"worker: live refresh skipped, {exc}")
    finally:
        db.close()


def main() -> None:
    last_live = 0.0
    while True:
        try:
            refit_once()
        except Exception as exc:
            print(f"worker error: {exc}")

        now = time.monotonic()
        if now - last_live >= settings.live_refresh_interval_seconds:
            last_live = now
            try:
                refresh_live_once()
            except Exception as exc:
                print(f"worker live error: {exc}")

        time.sleep(REFIT_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
