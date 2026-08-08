"""Test environment, set once before any test module is imported.

Each test module used to call `os.environ.setdefault("DATABASE_URL", ...)` at
import time, which made the winner depend on collection order: whichever module
sorted first decided the database for the whole run. Doing it here removes the
ordering trap.

The URL points at a file rather than `:memory:` on purpose. In-memory SQLite
gives every connection its own empty database, so tables created at import are
invisible to a request served on another thread and any route that touches the
database fails with "no such table". A file behaves the way Postgres does in
the real stack.
"""

import os
import tempfile

_DB_FILE = os.path.join(tempfile.gettempdir(), "kura_test.db")
if os.path.exists(_DB_FILE):
    os.remove(_DB_FILE)

os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{_DB_FILE.replace(os.sep, '/')}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
# Live data is off in tests unless a test turns it on, matching what ships.
os.environ.setdefault("KURA_FLAGS", "live_data=off")
