"""Seed PostgreSQL with ~12k anime titles, demo users, and ratings."""

from __future__ import annotations

import json
import random
import sys

import httpx
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Anime, Rating, User
from app.services.recommender import recommender

GENRES = [
    "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror", "Mystery",
    "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Thriller",
    "Mecha", "Music", "Psychological", "School", "Historical", "Military",
]
THEMES = [
    "Isekai", "Martial Arts", "Vampire", "Samurai", "Space", "Time Travel",
    "Coming of Age", "Friendship", "Revenge", "Politics",
]
TYPES = ["TV", "Movie", "OVA", "ONA", "Special"]
STATUSES = ["Finished Airing", "Currently Airing", "Not yet aired"]

MANAMI_URL = (
    "https://raw.githubusercontent.com/manami-project/anime-offline-database/"
    "master/anime-offline-database-minified.json"
)


def _genres_from_tags(tags: list) -> tuple[str, str]:
    genre_set = set()
    theme_set = set()
    for t in tags or []:
        name = t if isinstance(t, str) else str(t)
        if name in GENRES:
            genre_set.add(name)
        elif name in THEMES:
            theme_set.add(name)
        else:
            genre_set.add(name)
    return ", ".join(sorted(genre_set)[:8]), ", ".join(sorted(theme_set)[:6])


def load_from_manami(limit: int = 12000) -> list[dict]:
    print(f"Downloading anime catalog from Manami offline database...")
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        resp = client.get(MANAMI_URL)
        resp.raise_for_status()
        payload = resp.json()
    data = payload.get("data", payload if isinstance(payload, list) else [])
    rows: list[dict] = []
    for item in data:
        if len(rows) >= limit:
            break
        title = item.get("title") or ""
        if not title:
            continue
        tags = item.get("tags") or []
        genres, themes = _genres_from_tags(tags)
        sources = item.get("sources") or []
        mal_id = None
        for src in sources:
            if "myanimelist.net/anime/" in str(src):
                try:
                    mal_id = int(str(src).rstrip("/").split("/")[-1])
                except ValueError:
                    pass
        picture = item.get("picture") or item.get("thumbnail")
        rows.append(
            {
                "mal_id": mal_id,
                "title": title[:512],
                "title_english": (item.get("synonyms") or [None])[0],
                "synopsis": f"{title} — tagged: {genres or 'General'}.",
                "genres": genres,
                "themes": themes,
                "studios": ", ".join((item.get("studios") or [])[:4]),
                "score": None,
                "scored_by": 0,
                "episodes": item.get("episodes"),
                "status": item.get("status"),
                "year": (item.get("animeSeason") or {}).get("year"),
                "image_url": picture,
                "type": item.get("type"),
                "popularity": 0,
            }
        )
    print(f"Parsed {len(rows)} titles from Manami.")
    return rows


def generate_synthetic(limit: int = 12000) -> list[dict]:
    print(f"Generating synthetic catalog ({limit} titles) as fallback...")
    random.seed(42)
    rows = []
    prefixes = ["Shadow", "Crystal", "Neon", "Eternal", "Silent", "Azure", "Crimson", "Quantum"]
    nouns = ["Samurai", "Academy", "Chronicle", "Protocol", "Garden", "Frontier", "Legacy", "Oath"]
    for i in range(limit):
        g = random.sample(GENRES, k=random.randint(1, 3))
        t = random.sample(THEMES, k=random.randint(0, 2))
        title = f"{random.choice(prefixes)} {random.choice(nouns)} {i + 1}"
        rows.append(
            {
                "mal_id": 100000 + i,
                "title": title,
                "title_english": title,
                "synopsis": f"A {g[0].lower()} story involving {', '.join(t) or 'adventure'}.",
                "genres": ", ".join(g),
                "themes": ", ".join(t),
                "studios": random.choice(["MAPPA", "Bones", "Kyoto Animation", "Ufotable", "Wit Studio"]),
                "score": round(random.uniform(5.5, 9.4), 2),
                "scored_by": random.randint(100, 500000),
                "episodes": random.choice([12, 13, 24, 25, 26, 1, 48]),
                "status": random.choice(STATUSES),
                "year": random.randint(1985, 2025),
                "image_url": None,
                "type": random.choice(TYPES),
                "popularity": random.randint(1, 20000),
            }
        )
    return rows


def seed_anime(db: Session, target: int = 12000) -> int:
    existing = db.query(Anime).count()
    if existing >= min(target, 1000):
        print(f"Anime already seeded ({existing} rows). Skipping download.")
        return existing

    try:
        rows = load_from_manami(limit=target)
    except Exception as exc:
        print(f"Manami download failed ({exc}). Falling back to synthetic data.")
        rows = generate_synthetic(limit=target)

    if existing:
        db.query(Anime).delete()
        db.commit()

    batch: list[Anime] = []
    for i, row in enumerate(rows, start=1):
        batch.append(Anime(**row))
        if len(batch) >= 500:
            db.add_all(batch)
            db.commit()
            batch.clear()
            print(f"  inserted {i}/{len(rows)}")
    if batch:
        db.add_all(batch)
        db.commit()
    return db.query(Anime).count()


def seed_users_and_ratings(db: Session) -> None:
    if db.query(User).filter(User.email == "demo@anime.app").first():
        print("Demo users already exist.")
        return

    demo = User(
        email="demo@anime.app",
        username="demo",
        hashed_password=hash_password("demo1234"),
    )
    alice = User(
        email="alice@anime.app",
        username="alice",
        hashed_password=hash_password("demo1234"),
    )
    bob = User(
        email="bob@anime.app",
        username="bob",
        hashed_password=hash_password("demo1234"),
    )
    db.add_all([demo, alice, bob])
    db.commit()

    anime_ids = [a.id for a in db.query(Anime.id).order_by(Anime.id).limit(800).all()]
    if not anime_ids:
        return

    random.seed(7)
    ratings: list[Rating] = []
    for user in (demo, alice, bob):
        sample = random.sample(anime_ids, k=min(40, len(anime_ids)))
        for aid in sample:
            ratings.append(
                Rating(user_id=user.id, anime_id=aid, score=float(random.randint(5, 10)))
            )
    db.add_all(ratings)
    db.commit()
    print(f"Created demo users + {len(ratings)} ratings.")


def main() -> None:
    print("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        count = seed_anime(db, target=12000)
        seed_users_and_ratings(db)
        print("Fitting recommendation model...")
        recommender.fit(db)
        print(f"Seed complete. Anime rows: {count}")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise
