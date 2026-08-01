"""Ensure newer columns exist when create_all won't alter existing tables."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_schema(engine: Engine) -> None:
    dialect = engine.dialect.name
    insp = inspect(engine)
    if "watchlist" not in insp.get_table_names():
        return

    existing = {c["name"] for c in insp.get_columns("watchlist")}
    alters: list[str] = []

    if "status" not in existing:
        if dialect == "sqlite":
            alters.append(
                "ALTER TABLE watchlist ADD COLUMN status VARCHAR(32) DEFAULT 'plan_to_watch'"
            )
        else:
            alters.append(
                "ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'plan_to_watch'"
            )
    if "progress" not in existing:
        if dialect == "sqlite":
            alters.append("ALTER TABLE watchlist ADD COLUMN progress INTEGER DEFAULT 0")
        else:
            alters.append(
                "ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0"
            )
    if "updated_at" not in existing:
        if dialect == "sqlite":
            alters.append("ALTER TABLE watchlist ADD COLUMN updated_at DATETIME")
        else:
            alters.append(
                "ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
            )

    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))
        if dialect != "sqlite":
            conn.execute(
                text(
                    "UPDATE watchlist SET status = 'plan_to_watch' WHERE status IS NULL OR status = ''"
                )
            )
            conn.execute(text("UPDATE watchlist SET progress = 0 WHERE progress IS NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_watchlist_status ON watchlist (status)"))
