#!/usr/bin/env python
"""Background worker: periodically refits TF-IDF + embedding indexes."""

from __future__ import annotations

import time

from app.database import SessionLocal
from app.models import Anime
from app.services.embeddings import embedding_index
from app.services.recommender import recommender


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


def main() -> None:
    while True:
        try:
            refit_once()
        except Exception as exc:
            print(f"worker error: {exc}")
        time.sleep(300)


if __name__ == "__main__":
    main()
