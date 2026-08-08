"""Backup, restore, and imports.

Your ratings and shelf are yours. Export walks out as one JSON file you can read
in a text editor; import takes that file back, a MyAnimeList XML export, or a
public AniList username if this machine happens to have internet.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import Anime, Collection, CollectionItem, Note, Rating, User, WatchlistItem
from app.schemas import ImportResultOut, VaultExportOut
from app.services import events
from app.services.importer import apply_entries as _apply_entries
from app.services.importer import match_anime as _match_anime

router = APIRouter(prefix="/api/vault", tags=["vault"])

MAL_STATUS_MAP = {
    "completed": "completed",
    "watching": "watching",
    "on-hold": "on_hold",
    "on hold": "on_hold",
    "dropped": "dropped",
    "plan to watch": "plan_to_watch",
    "plantowatch": "plan_to_watch",
}

ANILIST_STATUS_MAP = {
    "COMPLETED": "completed",
    "CURRENT": "watching",
    "PAUSED": "on_hold",
    "DROPPED": "dropped",
    "PLANNING": "plan_to_watch",
    "REPEATING": "watching",
}

ANILIST_URL = "https://graphql.anilist.co"
ANILIST_QUERY = """
query ($name: String) {
  MediaListCollection(userName: $name, type: ANIME) {
    lists {
      entries {
        status
        score(format: POINT_10)
        progress
        media { idMal title { romaji english } }
      }
    }
  }
}
"""


class VaultImportIn(BaseModel):
    payload: dict = Field(default_factory=dict)
    overwrite: bool = False


class AniListImportIn(BaseModel):
    username: str = Field(min_length=2, max_length=60)


@router.get("/export", response_model=VaultExportOut)
def export_vault(user: User = Depends(require_user), db: Session = Depends(get_db)):
    ratings = (
        db.query(Rating, Anime)
        .join(Anime, Anime.id == Rating.anime_id)
        .filter(Rating.user_id == user.id)
        .all()
    )
    library = (
        db.query(WatchlistItem, Anime)
        .join(Anime, Anime.id == WatchlistItem.anime_id)
        .filter(WatchlistItem.user_id == user.id)
        .all()
    )
    collections = db.query(Collection).filter(Collection.user_id == user.id).all()
    notes = (
        db.query(Note, Anime)
        .join(Anime, Anime.id == Note.anime_id)
        .filter(Note.user_id == user.id)
        .all()
    )

    return VaultExportOut(
        version=2,
        exported_at=datetime.now(timezone.utc),
        username=user.username,
        ratings=[
            {"mal_id": a.mal_id, "title": a.title, "score": r.score, "rated_at": r.created_at}
            for r, a in ratings
        ],
        library=[
            {
                "mal_id": a.mal_id,
                "title": a.title,
                "status": item.status,
                "progress": int(item.progress or 0),
                "watch_seconds": int(item.watch_seconds or 0),
                "rewatches": int(item.rewatches or 0),
                "completed_at": item.completed_at,
            }
            for item, a in library
        ],
        collections=[
            {
                "name": c.name,
                "emoji": c.emoji,
                "description": c.description,
                "titles": [
                    a.title
                    for a in db.query(Anime)
                    .join(CollectionItem, CollectionItem.anime_id == Anime.id)
                    .filter(CollectionItem.collection_id == c.id)
                    .all()
                ],
            }
            for c in collections
        ],
        notes=[{"title": a.title, "body": n.body, "is_shared": n.is_shared} for n, a in notes],
    )


@router.post("/import", response_model=ImportResultOut)
def import_vault(
    payload: VaultImportIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Restore a file produced by /api/vault/export."""
    data = payload.payload or {}
    entries: list[dict] = []

    by_key: dict[str, dict] = {}
    for row in data.get("library") or []:
        key = str(row.get("mal_id") or row.get("title") or "")
        if not key:
            continue
        by_key[key] = {
            "mal_id": row.get("mal_id"),
            "title": row.get("title"),
            "status": row.get("status"),
            "progress": row.get("progress"),
            "watch_seconds": row.get("watch_seconds"),
            "rewatches": row.get("rewatches"),
        }
    for row in data.get("ratings") or []:
        key = str(row.get("mal_id") or row.get("title") or "")
        if not key:
            continue
        merged = by_key.setdefault(
            key, {"mal_id": row.get("mal_id"), "title": row.get("title")}
        )
        merged["score"] = row.get("score")
    entries = list(by_key.values())

    result = _apply_entries(db, user.id, entries, overwrite=payload.overwrite)

    for row in data.get("notes") or []:
        anime = _match_anime(db, None, row.get("title"))
        if not anime:
            continue
        note = (
            db.query(Note).filter(Note.user_id == user.id, Note.anime_id == anime.id).first()
        )
        if not note:
            note = Note(user_id=user.id, anime_id=anime.id)
            db.add(note)
        note.body = row.get("body") or ""
        note.is_shared = bool(row.get("is_shared"))
    db.commit()

    events.record(
        db,
        user_id=user.id,
        kind="vault_import",
        detail=f"{result.matched} titles matched",
        persist=False,
    )
    return result


@router.post("/import/mal", response_model=ImportResultOut)
async def import_mal(
    file: UploadFile = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Take a MyAnimeList XML export straight from their export page."""
    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="That export is larger than 12 MB")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse that XML: {exc}") from exc

    entries: list[dict] = []
    for node in root.findall("anime"):
        def text(tag: str) -> str | None:
            found = node.find(tag)
            return found.text.strip() if found is not None and found.text else None

        mal_id = text("series_animedb_id")
        status_raw = (text("my_status") or "").strip().lower()
        entries.append(
            {
                "mal_id": int(mal_id) if mal_id and mal_id.isdigit() else None,
                "title": text("series_title"),
                "status": MAL_STATUS_MAP.get(status_raw),
                "progress": int(text("my_watched_episodes") or 0),
                "score": float(text("my_score") or 0) or None,
                "rewatches": int(text("my_times_watched") or 0),
            }
        )

    if not entries:
        raise HTTPException(status_code=400, detail="No <anime> entries found in that file")
    result = _apply_entries(db, user.id, entries, overwrite=True)
    events.record(
        db,
        user_id=user.id,
        kind="vault_import",
        detail=f"MAL import: {result.matched} matched, {result.skipped} skipped",
        persist=False,
    )
    db.commit()
    return result


@router.post("/import/anilist", response_model=ImportResultOut)
def import_anilist(
    payload: AniListImportIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """One-shot import of a public list. For an account that keeps syncing, use
    /api/connect/accounts instead."""
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                ANILIST_URL,
                json={"query": ANILIST_QUERY, "variables": {"name": payload.username}},
            )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not reach AniList. Check this machine's connection and try again.",
        ) from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=404, detail="No public AniList list for that username")

    body = resp.json()
    lists = ((body.get("data") or {}).get("MediaListCollection") or {}).get("lists") or []
    entries: list[dict] = []
    for group in lists:
        for entry in group.get("entries") or []:
            media = entry.get("media") or {}
            titles = media.get("title") or {}
            entries.append(
                {
                    "mal_id": media.get("idMal"),
                    "title": titles.get("english") or titles.get("romaji"),
                    "status": ANILIST_STATUS_MAP.get(entry.get("status") or ""),
                    "progress": entry.get("progress") or 0,
                    "score": entry.get("score") or None,
                }
            )
    if not entries:
        raise HTTPException(status_code=404, detail="That AniList profile has no anime entries")
    result = _apply_entries(db, user.id, entries, overwrite=True)
    events.record(
        db,
        user_id=user.id,
        kind="vault_import",
        detail=f"AniList import for {payload.username}: {result.matched} matched",
        persist=False,
    )
    db.commit()
    return result


@router.get("/events")
def local_events(limit: int = 60, user: User = Depends(require_user)):
    """Tail of the JSONL automation log, same rows your own scripts would read."""
    return {"path": str(events.EVENT_LOG), "events": events.tail(limit)}


@router.get("/export.json")
def export_download(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Same payload, shaped for a Save As dialog."""
    from fastapi.responses import Response

    data = export_vault(user, db)
    body = json.dumps(json.loads(data.model_dump_json()), indent=2)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="kura-vault-{user.username}-{stamp}.json"'
        },
    )
