"""Local automation hook.

Every meaningful action appends one JSON object per line to `data/events.jsonl`
so you can tail it with your own scripts. If `KURA_WEBHOOK_URL` points at
something on your machine, the same payload is POSTed there, best effort.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.models import ActivityEvent

DATA_DIR = Path(os.getenv("KURA_DATA_DIR", "/app/data"))
EVENT_LOG = DATA_DIR / "events.jsonl"
WEBHOOK_URL = os.getenv("KURA_WEBHOOK_URL", "").strip()

_lock = threading.Lock()
_MAX_LINES = 20000


def _append_line(payload: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _lock:
            with EVENT_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, default=str) + "\n")
    except OSError:
        pass


def _post_webhook(payload: dict) -> None:
    if not WEBHOOK_URL:
        return

    def _send() -> None:
        try:
            httpx.post(WEBHOOK_URL, json=payload, timeout=3.0)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def record(
    db: Session | None,
    *,
    user_id: int | None,
    kind: str,
    anime_id: int | None = None,
    detail: str | None = None,
    target_user_id: int | None = None,
    persist: bool = True,
) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "user_id": user_id,
        "anime_id": anime_id,
        "detail": detail,
    }
    _append_line(payload)
    _post_webhook(payload)
    if persist and db is not None and user_id is not None:
        db.add(
            ActivityEvent(
                user_id=user_id,
                anime_id=anime_id,
                kind=kind,
                detail=(detail or "")[:400] or None,
                target_user_id=target_user_id,
            )
        )


def tail(limit: int = 100) -> list[dict]:
    if not EVENT_LOG.exists():
        return []
    try:
        with EVENT_LOG.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()[-max(1, min(limit, 500)) :]
    except OSError:
        return []
    out: list[dict] = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))


def trim() -> None:
    """Keep the log from growing without bound on a long-lived instance."""
    if not EVENT_LOG.exists():
        return
    try:
        with _lock:
            lines = EVENT_LOG.read_text(encoding="utf-8").splitlines()
            if len(lines) <= _MAX_LINES:
                return
            EVENT_LOG.write_text("\n".join(lines[-_MAX_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass
