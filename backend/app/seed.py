"""Seed PostgreSQL with ~12k anime titles, demo users, and ratings."""

from __future__ import annotations

import random
import re
import sys
import time

import httpx
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Anime, Rating, User, WatchlistItem
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
    "https://github.com/manami-project/anime-offline-database/releases/latest/"
    "download/anime-offline-database-minified.json"
)

# High unique mal_id range reserved for demo/famous title upserts.
DEMO_MAL_ID_BASE = 900000

FAMOUS_ANIME: list[dict] = [
    {
        "title": "One Piece",
        "title_english": "One Piece",
        "mal_id": 21,
        "image_url": "https://cdn.myanimelist.net/images/anime/1244/138851l.jpg",
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
        "mal_id": 20,
        "image_url": "https://cdn.myanimelist.net/images/anime/1141/142503l.jpg",
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
        "mal_id": 16498,
        "image_url": "https://cdn.myanimelist.net/images/anime/10/47347l.jpg",
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
        "mal_id": 1535,
        "image_url": "https://cdn.myanimelist.net/images/anime/1079/138100l.jpg",
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
        "mal_id": 5114,
        "image_url": "https://cdn.myanimelist.net/images/anime/1208/94745l.jpg",
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
        "mal_id": 50265,
        "image_url": "https://cdn.myanimelist.net/images/anime/1441/122795l.jpg",
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
        "mal_id": 40748,
        "image_url": "https://cdn.myanimelist.net/images/anime/1171/109222l.jpg",
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
        "mal_id": 38000,
        "image_url": "https://cdn.myanimelist.net/images/anime/1286/99889l.jpg",
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
        "mal_id": 1,
        "image_url": "https://cdn.myanimelist.net/images/anime/4/19644l.jpg",
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
        "mal_id": 9253,
        "image_url": "https://cdn.myanimelist.net/images/anime/1935/127974l.jpg",
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
        "mal_id": 32281,
        "image_url": "https://cdn.myanimelist.net/images/anime/5/87048l.jpg",
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
        "mal_id": 199,
        "image_url": "https://cdn.myanimelist.net/images/anime/6/79597l.jpg",
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
        "mal_id": 11061,
        "image_url": "https://cdn.myanimelist.net/images/anime/1337/99013l.jpg",
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
        "mal_id": 269,
        "image_url": "https://cdn.myanimelist.net/images/anime/1541/147774l.jpg",
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
        "mal_id": 31964,
        "image_url": "https://cdn.myanimelist.net/images/anime/10/78745l.jpg",
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
        "mal_id": 37521,
        "image_url": "https://cdn.myanimelist.net/images/anime/1500/103005l.jpg",
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
        "mal_id": 32182,
        "image_url": "https://cdn.myanimelist.net/images/anime/8/80356l.jpg",
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
        "mal_id": 30,
        "image_url": "https://cdn.myanimelist.net/images/anime/1314/108941l.jpg",
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
        "mal_id": 1575,
        "image_url": "https://cdn.myanimelist.net/images/anime/1032/135088l.jpg",
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
        "mal_id": 20583,
        "image_url": "https://cdn.myanimelist.net/images/anime/7/76014l.jpg",
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
        "mal_id": 44511,
        "image_url": "https://cdn.myanimelist.net/images/anime/1806/126216l.jpg",
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
        "mal_id": 22319,
        "image_url": "https://cdn.myanimelist.net/images/anime/1498/134443l.jpg",
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
        "mal_id": 11757,
        "image_url": "https://cdn.myanimelist.net/images/anime/11/39717l.jpg",
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
        "mal_id": 6702,
        "image_url": "https://cdn.myanimelist.net/images/anime/5/18179l.jpg",
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
        "mal_id": 813,
        "image_url": "https://cdn.myanimelist.net/images/anime/1277/142022l.jpg",
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


def _norm_title(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _famous_row(entry: dict, mal_id: int | None = None) -> dict:
    mid = mal_id if mal_id is not None else entry.get("mal_id")
    return {
        "mal_id": mid,
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
    print("Downloading anime catalog from Manami offline database...")
    with httpx.Client(timeout=180.0, follow_redirects=True) as client:
        resp = client.get(MANAMI_URL)
        resp.raise_for_status()
        payload = resp.json()
    data = payload.get("data", payload if isinstance(payload, list) else [])
    rows: list[dict] = []
    seen_mal: set[int] = set()
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
        if mal_id is not None and mal_id in seen_mal:
            mal_id = None
        if mal_id is not None:
            seen_mal.add(mal_id)
        picture = item.get("picture") or item.get("thumbnail")
        rows.append(
            {
                "mal_id": mal_id,
                "title": title[:512],
                "title_english": (item.get("synonyms") or [None])[0],
                "synopsis": f"{title}. Tagged: {genres or 'General'}.",
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
    used_mal: set[int] = set()
    for i, entry in enumerate(FAMOUS_ANIME):
        if len(rows) >= limit:
            break
        mal_id = entry.get("mal_id") or (DEMO_MAL_ID_BASE + i)
        if mal_id in used_mal:
            mal_id = DEMO_MAL_ID_BASE + i
        used_mal.add(mal_id)
        rows.append(_famous_row(entry, mal_id))

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


def _find_famous_row(db: Session, entry: dict) -> Anime | None:
    key = entry["title"].strip().lower()
    row = db.query(Anime).filter(func.lower(Anime.title) == key).first()
    if row:
        return row
    english = (entry.get("title_english") or "").strip().lower()
    if english:
        row = (
            db.query(Anime)
            .filter(
                or_(
                    func.lower(Anime.title) == english,
                    func.lower(Anime.title_english) == english,
                    func.lower(Anime.title_english) == key,
                )
            )
            .first()
        )
        if row:
            return row
    mal_id = entry.get("mal_id")
    if mal_id:
        return db.query(Anime).filter(Anime.mal_id == mal_id).first()
    return None


def ensure_demo_titles(db: Session) -> int:
    """Insert or repair well-known titles so catalogs always include famous posters."""
    inserted = 0
    updated = 0
    for i, entry in enumerate(FAMOUS_ANIME):
        row = _find_famous_row(db, entry)
        mal_id = entry.get("mal_id")

        if row is None:
            use_mal = mal_id or (DEMO_MAL_ID_BASE + i)
            if use_mal is not None:
                conflict = db.query(Anime).filter(Anime.mal_id == use_mal).first()
                if conflict:
                    row = conflict
                else:
                    db.add(Anime(**_famous_row(entry, use_mal)))
                    inserted += 1
                    continue
            else:
                db.add(Anime(**_famous_row(entry, DEMO_MAL_ID_BASE + i)))
                inserted += 1
                continue

        needs_update = (
            not (row.image_url or "").strip()
            or (row.mal_id is not None and row.mal_id >= DEMO_MAL_ID_BASE)
        )
        if not needs_update:
            continue

        if mal_id and row.mal_id != mal_id:
            conflict = (
                db.query(Anime)
                .filter(Anime.mal_id == mal_id, Anime.id != row.id)
                .first()
            )
            if not conflict:
                row.mal_id = mal_id

        if entry.get("image_url"):
            row.image_url = entry["image_url"]
        if entry.get("score") is not None:
            row.score = entry["score"]
        if entry.get("synopsis"):
            row.synopsis = entry["synopsis"]
        for field in ("title_english", "genres", "themes", "studios", "episodes", "status", "year", "type"):
            if entry.get(field) is not None:
                setattr(row, field, entry[field])
        updated += 1

    if inserted or updated:
        db.commit()
        print(f"Demo titles: inserted {inserted}, updated {updated}.")
    else:
        print("All demo titles already present with images.")
    return inserted + updated


def _jikan_title_candidates(item: dict) -> list[str]:
    out: list[str] = []
    for key in ("title", "title_english", "title_japanese"):
        if item.get(key):
            out.append(str(item[key]))
    for t in item.get("titles") or []:
        if isinstance(t, dict) and t.get("title"):
            out.append(str(t["title"]))
        elif isinstance(t, str):
            out.append(t)
    return out


def _jikan_pick_best(query: str, data: list[dict]) -> dict | None:
    nq = _norm_title(query)
    exact: list[dict] = []
    partial: list[dict] = []
    for item in data:
        for c in _jikan_title_candidates(item):
            nc = _norm_title(c)
            if nc == nq:
                exact.append(item)
                break
            if nq and (nq in nc or nc in nq):
                partial.append(item)
                break
    if exact:
        return exact[0]
    if partial:
        return partial[0]
    return data[0] if data else None


def _jikan_search_image(client: httpx.Client, title: str) -> tuple[int | None, str | None]:
    resp = client.get(
        "https://api.jikan.moe/v4/anime",
        params={"q": title, "limit": 5},
    )
    if resp.status_code == 429:
        time.sleep(1.5)
        resp = client.get(
            "https://api.jikan.moe/v4/anime",
            params={"q": title, "limit": 5},
        )
    resp.raise_for_status()
    data = resp.json().get("data") or []
    best = _jikan_pick_best(title, data)
    if not best:
        return None, None
    jpg = (best.get("images") or {}).get("jpg") or {}
    img = jpg.get("large_image_url") or jpg.get("image_url")
    return best.get("mal_id"), img


def enrich_missing_images(db: Session, limit: int = 80) -> int:
    """Fallback: fill missing posters via Jikan for famous + top-scored titles."""
    print(f"Enriching missing images via Jikan (up to {limit} titles)...")
    targets: list[Anime] = []
    seen_ids: set[int] = set()

    for entry in FAMOUS_ANIME:
        row = _find_famous_row(db, entry)
        if row and row.id not in seen_ids and not (row.image_url or "").strip():
            targets.append(row)
            seen_ids.add(row.id)

    if len(targets) < limit:
        top = (
            db.query(Anime)
            .filter(or_(Anime.image_url.is_(None), Anime.image_url == ""))
            .order_by(Anime.score.desc().nullslast(), Anime.id)
            .limit(limit)
            .all()
        )
        for row in top:
            if row.id in seen_ids:
                continue
            targets.append(row)
            seen_ids.add(row.id)
            if len(targets) >= limit:
                break

    updated = 0
    with httpx.Client(timeout=45.0, follow_redirects=True) as client:
        for row in targets[:limit]:
            try:
                mal_id, image_url = _jikan_search_image(client, row.title)
            except Exception as exc:
                print(f"  Jikan miss for {row.title!r}: {exc}")
                time.sleep(0.4)
                continue
            if image_url:
                row.image_url = image_url
                if mal_id and (row.mal_id is None or row.mal_id >= DEMO_MAL_ID_BASE):
                    conflict = (
                        db.query(Anime)
                        .filter(Anime.mal_id == mal_id, Anime.id != row.id)
                        .first()
                    )
                    if not conflict:
                        row.mal_id = mal_id
                updated += 1
                print(f"  enriched {row.title} -> {image_url}")
            time.sleep(0.4)

    if updated:
        db.commit()
    print(f"Enriched {updated} image URLs via Jikan.")
    return updated


def _insert_anime_rows(db: Session, rows: list[dict]) -> int:
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
        db.query(WatchlistItem).delete()
        db.query(Rating).delete()
        db.query(Anime).delete()
        db.commit()

    return _insert_anime_rows(db, rows)


def refresh_catalog_from_manami(db: Session, target: int = 12000) -> int:
    """Replace anime catalog with Manami data (includes picture URLs)."""
    print("Refreshing catalog from Manami...")
    db.query(WatchlistItem).delete()
    db.query(Rating).delete()
    db.query(Anime).delete()
    db.commit()

    try:
        rows = load_from_manami(limit=target)
        used_manami = True
    except Exception as exc:
        print(f"Manami download failed ({exc}). Falling back to synthetic data.")
        rows = generate_synthetic(limit=target)
        used_manami = False

    count = _insert_anime_rows(db, rows)
    ensure_demo_titles(db)
    if not used_manami:
        enrich_missing_images(db)
    else:
        missing = (
            db.query(Anime)
            .filter(or_(Anime.image_url.is_(None), Anime.image_url == ""))
            .count()
        )
        with_images = count - missing
        print(f"Manami load complete: {with_images}/{count} rows have image_url.")
        if with_images == 0:
            enrich_missing_images(db)
    return db.query(Anime).count()


def seed_users_and_ratings(db: Session) -> None:
    demo = db.query(User).filter(User.email == "demo@anime.app").first()
    alice = db.query(User).filter(User.email == "alice@anime.app").first()
    bob = db.query(User).filter(User.email == "bob@anime.app").first()

    created = []
    if not demo:
        demo = User(
            email="demo@anime.app",
            username="demo",
            hashed_password=hash_password("demo1234"),
        )
        created.append(demo)
    if not alice:
        alice = User(
            email="alice@anime.app",
            username="alice",
            hashed_password=hash_password("demo1234"),
        )
        created.append(alice)
    if not bob:
        bob = User(
            email="bob@anime.app",
            username="bob",
            hashed_password=hash_password("demo1234"),
        )
        created.append(bob)

    if created:
        db.add_all(created)
        db.commit()
        print(f"Created {len(created)} demo user(s).")
    else:
        print("Demo users already exist.")

    users = [u for u in (demo, alice, bob) if u is not None]
    user_ids = [u.id for u in users]
    existing_ratings = db.query(Rating).filter(Rating.user_id.in_(user_ids)).count()
    if existing_ratings > 0:
        print(f"Demo ratings already exist ({existing_ratings}).")
        return

    anime_ids = [a.id for a in db.query(Anime.id).order_by(Anime.id).limit(800).all()]
    if not anime_ids:
        return

    random.seed(7)
    ratings: list[Rating] = []
    for user in users:
        sample = random.sample(anime_ids, k=min(40, len(anime_ids)))
        for aid in sample:
            ratings.append(
                Rating(user_id=user.id, anime_id=aid, score=float(random.randint(5, 10)))
            )
    db.add_all(ratings)
    db.commit()
    print(f"Created {len(ratings)} demo ratings.")


def reseed_with_images(target: int = 12000) -> None:
    """Wipe anime/ratings/watchlist, reload Manami with pictures, recreate demo ratings."""
    print("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        count = refresh_catalog_from_manami(db, target=target)
        seed_users_and_ratings(db)
        print("Fitting recommendation model...")
        recommender.fit(db)
        with_img = (
            db.query(Anime)
            .filter(Anime.image_url.isnot(None), Anime.image_url != "")
            .count()
        )
        https_img = (
            db.query(Anime)
            .filter(Anime.image_url.ilike("https://%"))
            .count()
        )
        print(f"Seed complete. Anime rows: {count}")
        print(f"Rows with image_url: {with_img}")
        print(f"Rows with https image_url: {https_img}")
    finally:
        db.close()


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
        with_img = (
            db.query(Anime)
            .filter(Anime.image_url.isnot(None), Anime.image_url != "")
            .count()
        )
        print(f"Seed complete. Anime rows: {count} (with images: {with_img})")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        if "--reseed-images" in sys.argv:
            reseed_with_images()
        else:
            main()
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise
