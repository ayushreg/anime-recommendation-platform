"""Startup migrator.

`Base.metadata.create_all` happily creates brand new tables but never alters an
existing one, so every column added after the first release lands here. The
helpers below are idempotent and safe to run on every boot, on Postgres (Docker)
and on SQLite (tests).
"""

from __future__ import annotations

import re

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# table -> column -> (postgres type + default, sqlite type + default)
COLUMN_ADDITIONS: dict[str, dict[str, tuple[str, str]]] = {
    "users": {
        "friend_code": ("VARCHAR(16)", "VARCHAR(16)"),
    },
    "anime": {
        "season": ("VARCHAR(16)", "VARCHAR(16)"),
        "duration_minutes": ("INTEGER", "INTEGER"),
        "franchise_key": ("VARCHAR(160)", "VARCHAR(160)"),
    },
    "ratings": {
        "updated_at": ("TIMESTAMPTZ DEFAULT NOW()", "DATETIME"),
    },
    "watchlist": {
        "status": ("VARCHAR(32) DEFAULT 'plan_to_watch'", "VARCHAR(32) DEFAULT 'plan_to_watch'"),
        "progress": ("INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        "updated_at": ("TIMESTAMPTZ DEFAULT NOW()", "DATETIME"),
        "watch_seconds": ("INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        "rewatches": ("INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        "is_rewatching": ("BOOLEAN DEFAULT FALSE", "BOOLEAN DEFAULT 0"),
        "completed_at": ("TIMESTAMPTZ", "DATETIME"),
    },
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_watchlist_status ON watchlist (status)",
    "CREATE INDEX IF NOT EXISTS ix_anime_season ON anime (season)",
    "CREATE INDEX IF NOT EXISTS ix_anime_franchise_key ON anime (franchise_key)",
    "CREATE INDEX IF NOT EXISTS ix_impressions_created ON impressions (created_at)",
]

BACKFILLS = [
    "UPDATE watchlist SET status = 'plan_to_watch' WHERE status IS NULL OR status = ''",
    "UPDATE watchlist SET progress = 0 WHERE progress IS NULL",
    "UPDATE watchlist SET watch_seconds = 0 WHERE watch_seconds IS NULL",
    "UPDATE watchlist SET rewatches = 0 WHERE rewatches IS NULL",
    "UPDATE ratings SET updated_at = created_at WHERE updated_at IS NULL",
]

# Rough per-episode runtimes when the catalog does not carry one.
DEFAULT_RUNTIME_BY_TYPE = {
    "TV": 24,
    "ONA": 24,
    "OVA": 26,
    "Special": 25,
    "Movie": 100,
    "MUSIC": 5,
    "Music": 5,
}

_SEASON_NOISE = re.compile(
    r"\b(season|part|cour|final|movie|film|the animation|tv|ova|ona|special|specials|"
    r"2nd|3rd|4th|5th|ii|iii|iv|v|vi|vii|viii|ix|x)\b",
    re.IGNORECASE,
)
_NON_WORD = re.compile(r"[^a-z0-9]+")


def franchise_key_for(title: str) -> str:
    """Collapse 'Attack on Titan Season 3 Part 2' and its movies onto one key."""
    base = (title or "").lower()
    base = base.split(":")[0]
    base = re.sub(r"\b(19|20)\d{2}\b", " ", base)
    base = _SEASON_NOISE.sub(" ", base)
    base = _NON_WORD.sub(" ", base).strip()
    words = [w for w in base.split() if w and not w.isdigit()]
    return " ".join(words[:6])[:160] or (title or "").lower()[:160]


def _add_missing_columns(engine: Engine) -> list[str]:
    dialect = engine.dialect.name
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    statements: list[str] = []
    for table, columns in COLUMN_ADDITIONS.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for name, (pg_type, sqlite_type) in columns.items():
            if name in existing:
                continue
            if dialect == "sqlite":
                statements.append(f"ALTER TABLE {table} ADD COLUMN {name} {sqlite_type}")
            else:
                statements.append(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {pg_type}"
                )
    return statements


def backfill_catalog_fields(engine: Engine, batch: int = 4000) -> int:
    """Fill franchise_key and duration_minutes for rows seeded before those columns."""
    insp = inspect(engine)
    if "anime" not in insp.get_table_names():
        return 0
    columns = {c["name"] for c in insp.get_columns("anime")}
    if "franchise_key" not in columns or "duration_minutes" not in columns:
        return 0

    touched = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, title, type FROM anime "
                "WHERE franchise_key IS NULL OR duration_minutes IS NULL "
                "LIMIT :batch"
            ),
            {"batch": batch},
        ).fetchall()
        while rows:
            payload = [
                {
                    "id": row[0],
                    "fk": franchise_key_for(row[1] or ""),
                    "dur": DEFAULT_RUNTIME_BY_TYPE.get((row[2] or "TV").strip(), 24),
                }
                for row in rows
            ]
            conn.execute(
                text(
                    "UPDATE anime SET franchise_key = :fk, "
                    "duration_minutes = COALESCE(duration_minutes, :dur) WHERE id = :id"
                ),
                payload,
            )
            touched += len(rows)
            if len(rows) < batch:
                break
            rows = conn.execute(
                text(
                    "SELECT id, title, type FROM anime "
                    "WHERE franchise_key IS NULL OR duration_minutes IS NULL "
                    "LIMIT :batch"
                ),
                {"batch": batch},
            ).fetchall()
    return touched


def ensure_friend_codes(engine: Engine) -> int:
    """Give every account a short share code. Deterministic, no collisions in practice."""
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return 0
    if "friend_code" not in {c["name"] for c in insp.get_columns("users")}:
        return 0
    import hashlib

    filled = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, username FROM users WHERE friend_code IS NULL")
        ).fetchall()
        for uid, username in rows:
            digest = hashlib.sha1(f"kura:{uid}:{username}".encode()).hexdigest()
            code = f"KURA-{digest[:4].upper()}{digest[4:8].upper()}"
            conn.execute(
                text("UPDATE users SET friend_code = :code WHERE id = :id"),
                {"code": code, "id": uid},
            )
            filled += 1
    return filled


def ensure_schema(engine: Engine) -> None:
    dialect = engine.dialect.name
    statements = _add_missing_columns(engine)

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    insp = inspect(engine)
    tables = set(insp.get_table_names())

    with engine.begin() as conn:
        for stmt in BACKFILLS:
            table = stmt.split()[1]
            if table not in tables:
                continue
            try:
                conn.execute(text(stmt))
            except Exception:  # pragma: no cover - column may not exist on old SQLite
                pass

    with engine.begin() as conn:
        for stmt in INDEXES:
            target = stmt.split(" ON ")[-1].split()[0]
            if target not in tables:
                continue
            if dialect == "sqlite" and "TIMESTAMPTZ" in stmt:
                continue
            try:
                conn.execute(text(stmt))
            except Exception:  # pragma: no cover
                pass

    backfill_catalog_fields(engine)
    ensure_friend_codes(engine)
