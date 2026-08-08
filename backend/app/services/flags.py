"""Feature flags so a big surface can be switched off without a redeploy.

Resolution order, last one wins:
  1. `app/feature_flags.json` shipped with the repo
  2. `app/feature_flags.local.json` written by the admin panel
  3. `KURA_FLAGS` env var, a comma list like "social=off,sound_design=on"
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent.parent / "feature_flags.json"
LOCAL_PATH = Path(__file__).resolve().parent.parent / "feature_flags.local.json"

_lock = threading.Lock()
_cache: dict[str, bool] | None = None

TRUTHY = {"1", "true", "on", "yes", "enabled"}


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _from_env() -> dict[str, bool]:
    raw = os.getenv("KURA_FLAGS", "").strip()
    if not raw:
        return {}
    out: dict[str, bool] = {}
    for chunk in raw.split(","):
        if "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        out[name.strip()] = value.strip().lower() in TRUTHY
    return out


def load(force: bool = False) -> dict[str, bool]:
    global _cache
    with _lock:
        if _cache is not None and not force:
            return dict(_cache)
        merged: dict[str, bool] = {k: bool(v) for k, v in _read(BASE_PATH).items()}
        merged.update({k: bool(v) for k, v in _read(LOCAL_PATH).items()})
        merged.update(_from_env())
        _cache = merged
        return dict(merged)


def enabled(name: str, default: bool = True) -> bool:
    return bool(load().get(name, default))


def set_flag(name: str, value: bool) -> dict[str, bool]:
    """Persist an override so it survives a restart of the API container."""
    current = _read(LOCAL_PATH)
    current[name] = bool(value)
    try:
        LOCAL_PATH.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        # Read-only mount: keep the change in memory for this process at least.
        pass
    with _lock:
        global _cache
        _cache = None
    return load(force=True)
