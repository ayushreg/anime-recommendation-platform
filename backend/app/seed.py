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

# High unique mal_id range reserved for demo/famous title upserts.
DEMO_MAL_ID_BASE = 900000

FAMOUS_ANIME: list[dict] = [
    {
        "title": "One Piece",
        "title_english": "One Piece",
        "genres": "Action, Adventure, Comedy, Fantasy",
        "themes": "Friendship, Coming of Age",
        "synopsis": "Monkey D. Luffy sets sail to become King of the Pirates.",
        "score": 9.2,
        "year": 1999,
        "type": "TV",
        "episodes": 1000,
        "studios": "Toei Animation",
        "status": "Currently Airing",
    },
    {
        "title": "Naruto",
        "title_english": "Naruto",
        "genres": "Action, Adventure, Fantasy",
        "themes": "Martial Arts, Friendship, Coming of Age",
        "synopsis": "A young ninja seeks recognition and dreams of becoming Hokage.",
        "score": 8.4,
        "year": 2002,
        "type": "TV",
        "episodes": 220,
        "studios": "Pierrot",
        "status": "Finished Airing",
    },
    {
        "title": "Attack on Titan",
        "title_english": "Attack on Titan",
        "genres": "Action, Drama, Fantasy, Horror",
        "themes": "Military, Revenge, Politics",
        "synopsis": "Humanity fights for survival against giant humanoid Titans.",
        "score": 9.1,
        "year": 2013,
        "type": "TV",
        "episodes": 25,
        "studios": "Wit Studio",
        "status": "Finished Airing",
    },
    {
        "title": "Death Note",
        "title_english": "Death Note",
        "genres": "Mystery, Psychological, Thriller, Supernatural",
        "themes": "Revenge, Politics",
        "synopsis": "A student finds a notebook that kills anyone whose name is written in it.",
        "score": 8.6,
        "year": 2006,
        "type": "TV",
        "episodes": 37,
        "studios": "Madhouse",
        "status": "Finished Airing",
    },
    {
        "title": "Fullmetal Alchemist: Brotherhood",
        "title_english": "Fullmetal Alchemist: Brotherhood",
        "genres": "Action, Adventure, Drama, Fantasy",
        "themes": "Military, Coming of Age",
        "synopsis": "Two brothers seek the Philosopher's Stone to restore their bodies.",
        "score": 9.5,
        "year": 2009,
        "type": "TV",
        "episodes": 64,
        "studios": "Bones",
        "status": "Finished Airing",
    },
    {
        "title": "Spy x Family",
        "title_english": "Spy x Family",
        "genres": "Action, Comedy, Slice of Life",
        "themes": "Friendship, Coming of Age",
        "synopsis": "A spy, an assassin, and a telepath form an unlikely fake family.",
        "score": 8.5,
        "year": 2022,
        "type": "TV",
        "episodes": 25,
        "studios": "Wit Studio",
        "status": "Finished Airing",
    },
    {
        "title": "Jujutsu Kaisen",
        "title_english": "Jujutsu Kaisen",
        "genres": "Action, Fantasy, Supernatural, School",
        "themes": "Martial Arts, Friendship",
        "synopsis": "A student joins a secret society of Jujutsu Sorcerers to fight curses.",
        "score": 8.7,
        "year": 2020,
        "type": "TV",
        "episodes": 24,
        "studios": "MAPPA",
        "status": "Finished Airing",
    },
    {
        "title": "Demon Slayer",
        "title_english": "Demon Slayer: Kimetsu no Yaiba",
        "genres": "Action, Adventure, Fantasy, Supernatural",
        "themes": "Martial Arts, Revenge, Historical",
        "synopsis": "Tanjiro becomes a demon slayer to save his sister and avenge his family.",
        "score": 8.7,
        "year": 2019,
        "type": "TV",
        "episodes": 26,
        "studios": "Ufotable",
        "status": "Finished Airing",
    },
    {
        "title": "Cowboy Bebop",
        "title_english": "Cowboy Bebop",
        "genres": "Action, Adventure, Drama, Sci-Fi",
        "themes": "Space, Coming of Age",
        "synopsis": "Bounty hunters drift through space chasing the next payday.",
        "score": 8.8,
        "year": 1998,
        "type": "TV",
        "episodes": 26,
        "studios": "Sunrise",
        "status": "Finished Airing",
    },
    {
        "title": "Steins;Gate",
        "title_english": "Steins;Gate",
        "genres": "Drama, Sci-Fi, Thriller",
        "themes": "Time Travel",
        "synopsis": "A self-proclaimed mad scientist discovers a way to send messages to the past.",
        "score": 9.1,
        "year": 2011,
        "type": "TV",
        "episodes": 24,
        "studios": "White Fox",
        "status": "Finished Airing",
    },
    {
        "title": "Your Name",
        "title_english": "Your Name.",
        "genres": "Drama, Romance, Supernatural",
        "themes": "Coming of Age, Time Travel",
        "synopsis": "Two teenagers mysteriously begin swapping bodies across time and place.",
        "score": 8.9,
        "year": 2016,
        "type": "Movie",
        "episodes": 1,
        "studios": "CoMix Wave Films",
        "status": "Finished Airing",
    },
    {
        "title": "Spirited Away",
        "title_english": "Spirited Away",
        "genres": "Adventure, Drama, Fantasy, Supernatural",
        "themes": "Coming of Age",
        "synopsis": "A girl enters a spirit world and must find her way home.",
        "score": 9.0,
        "year": 2001,
        "type": "Movie",
        "episodes": 1,
        "studios": "Studio Ghibli",
        "status": "Finished Airing",
    },
    {
        "title": "Hunter x Hunter",
        "title_english": "Hunter x Hunter",
        "genres": "Action, Adventure, Fantasy",
        "themes": "Friendship, Coming of Age",
        "synopsis": "Gon Freecss sets out to become a Hunter and find his father.",
        "score": 9.0,
        "year": 2011,
        "type": "TV",
        "episodes": 148,
        "studios": "Madhouse",
        "status": "Finished Airing",
    },
    {
        "title": "Bleach",
        "title_english": "Bleach",
        "genres": "Action, Adventure, Supernatural",
        "themes": "Martial Arts, Friendship",
        "synopsis": "A teenager gains Soul Reaper powers and protects the living from Hollows.",
        "score": 8.2,
        "year": 2004,
        "type": "TV",
        "episodes": 366,
        "studios": "Pierrot",
        "status": "Finished Airing",
    },
    {
        "title": "My Hero Academia",
        "title_english": "My Hero Academia",
        "genres": "Action, Comedy, School",
        "themes": "Friendship, Coming of Age",
        "synopsis": "A quirkless boy inherits a legendary power and enrolls in a hero academy.",
        "score": 8.3,
        "year": 2016,
        "type": "TV",
        "episodes": 13,
        "studios": "Bones",
        "status": "Finished Airing",
    },
    {
        "title": "Vinland Saga",
        "title_english": "Vinland Saga",
        "genres": "Action, Adventure, Drama, Historical",
        "themes": "Revenge, Politics, Coming of Age",
        "synopsis": "A young Viking seeks revenge and a path beyond endless war.",
        "score": 8.8,
        "year": 2019,
        "type": "TV",
        "episodes": 24,
        "studios": "Wit Studio",
        "status": "Finished Airing",
    },
    {
        "title": "Mob Psycho 100",
        "title_english": "Mob Psycho 100",
        "genres": "Action, Comedy, Supernatural",
        "themes": "Coming of Age, Friendship",
        "synopsis": "A powerful esper tries to live a normal life while controlling his emotions.",
        "score": 8.7,
        "year": 2016,
        "type": "TV",
        "episodes": 12,
        "studios": "Bones",
        "status": "Finished Airing",
    },
    {
        "title": "Neon Genesis Evangelion",
        "title_english": "Neon Genesis Evangelion",
        "genres": "Action, Drama, Mecha, Psychological, Sci-Fi",
        "themes": "Coming of Age",
        "synopsis": "Teenagers pilot giant mechs against mysterious Angels threatening Earth.",
        "score": 8.4,
        "year": 1995,
        "type": "TV",
        "episodes": 26,
        "studios": "Gainax",
        "status": "Finished Airing",
    },
    {
        "title": "Code Geass",
        "title_english": "Code Geass: Lelouch of the Rebellion",
        "genres": "Action, Drama, Mecha, Military, Sci-Fi",
        "themes": "Politics, Revenge",
        "synopsis": "An exiled prince gains a power of absolute obedience and leads a rebellion.",
        "score": 8.7,
        "year": 2006,
        "type": "TV",
        "episodes": 25,
        "studios": "Sunrise",
        "status": "Finished Airing",
    },
    {
        "title": "Haikyuu!!",
        "title_english": "Haikyu!!",
        "genres": "Comedy, Drama, Sports, School",
        "themes": "Friendship, Coming of Age",
        "synopsis": "A short volleyball player aims for the top with his rival-turned-teammate.",
        "score": 8.7,
        "year": 2014,
        "type": "TV",
        "episodes": 25,
        "studios": "Production I.G",
        "status": "Finished Airing",
    },
    {
        "title": "Chainsaw Man",
        "title_english": "Chainsaw Man",
        "genres": "Action, Fantasy, Horror, Supernatural",
        "themes": "Revenge",
        "synopsis": "A devil hunter merges with his pet devil to become Chainsaw Man.",
        "score": 8.5,
        "year": 2022,
        "type": "TV",
        "episodes": 12,
        "studios": "MAPPA",
        "status": "Finished Airing",
    },
    {
        "title": "Tokyo Ghoul",
        "title_english": "Tokyo Ghoul",
        "genres": "Action, Drama, Horror, Supernatural",
        "themes": "Coming of Age",
        "synopsis": "A college student becomes a half-ghoul after a deadly encounter.",
        "score": 8.0,
        "year": 2014,
        "type": "TV",
        "episodes": 12,
        "studios": "Pierrot",
        "status": "Finished Airing",
    },
    {
        "title": "Sword Art Online",
        "title_english": "Sword Art Online",
        "genres": "Action, Adventure, Fantasy, Romance",
        "themes": "Isekai, Friendship",
        "synopsis": "Players trapped in a VRMMORPG must clear the game to survive.",
        "score": 8.1,
        "year": 2012,
        "type": "TV",
        "episodes": 25,
        "studios": "A-1 Pictures",
        "status": "Finished Airing",
    },
    {
        "title": "Fairy Tail",
        "title_english": "Fairy Tail",
        "genres": "Action, Adventure, Comedy, Fantasy",
        "themes": "Friendship, Martial Arts",
        "synopsis": "A wizard guild's adventures of friendship, magic, and loyalty.",
        "score": 8.0,
        "year": 2009,
        "type": "TV",
        "episodes": 175,
        "studios": "A-1 Pictures",
        "status": "Finished Airing",
    },
    {
        "title": "Dragon Ball Z",
        "title_english": "Dragon Ball Z",
        "genres": "Action, Adventure, Fantasy, Comedy",
        "themes": "Martial Arts, Friendship",
        "synopsis": "Goku and friends defend Earth against increasingly powerful foes.",
        "score": 8.5,
        "year": 1989,
        "type": "TV",
        "episodes": 291,
        "studios": "Toei Animation",
        "status": "Finished Airing",
    },
]


def _famous_row(entry: dict, mal_id: int) -> dict:
    return {
        "mal_id": mal_id,
        "title": entry["title"],
        "title_english": entry.get("title_english"),
        "synopsis": entry.get("synopsis"),
        "genres": entry.get("genres", ""),
        "themes": entry.get("themes", ""),
        "studios": entry.get("studios", ""),
        "score": entry.get("score"),
        "scored_by": entry.get("scored_by", 100000),
        "episodes": entry.get("episodes"),
        "status": entry.get("status", "Finished Airing"),
        "year": entry.get("year"),
        "image_url": entry.get("image_url"),
        "type": entry.get("type", "TV"),
        "popularity": entry.get("popularity", 100),
    }


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
    rows: list[dict] = []
    for i, entry in enumerate(FAMOUS_ANIME):
        if len(rows) >= limit:
            break
        rows.append(_famous_row(entry, DEMO_MAL_ID_BASE + i))

    prefixes = ["Shadow", "Crystal", "Neon", "Eternal", "Silent", "Azure", "Crimson", "Quantum"]
    nouns = ["Samurai", "Academy", "Chronicle", "Protocol", "Garden", "Frontier", "Legacy", "Oath"]
    start = len(rows)
    for i in range(start, limit):
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


def ensure_demo_titles(db: Session) -> int:
    """Insert any missing well-known titles so existing synthetic DBs work offline."""
    existing_titles = {
        (t or "").strip().lower()
        for (t,) in db.query(Anime.title).all()
    }
    inserted = 0
    for i, entry in enumerate(FAMOUS_ANIME):
        key = entry["title"].strip().lower()
        if key in existing_titles:
            continue
        mal_id = DEMO_MAL_ID_BASE + i
        # Avoid unique mal_id collisions if that slot is already taken.
        while db.query(Anime).filter(Anime.mal_id == mal_id).first():
            mal_id += len(FAMOUS_ANIME)
        db.add(Anime(**_famous_row(entry, mal_id)))
        existing_titles.add(key)
        inserted += 1
    if inserted:
        db.commit()
        print(f"Inserted {inserted} missing demo titles.")
    else:
        print("All demo titles already present.")
    return inserted


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
        ensure_demo_titles(db)
        count = db.query(Anime).count()
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
