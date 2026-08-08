"""Custom shelves and private notes.

Statuses answer "where am I with this". Collections answer "what mood is this",
which is a different question and deserves its own surface.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import Anime, Collection, CollectionItem, Note, User
from app.schemas import (
    AnimeOut,
    CollectionDetailOut,
    CollectionIn,
    CollectionItemIn,
    CollectionOut,
    NoteIn,
    NoteOut,
)
from app.services import events

router = APIRouter(prefix="/api/collections", tags=["collections"])

STARTER_COLLECTIONS = [
    ("Comfort rewatch", "~", "Shows that always work when nothing else does"),
    ("Cyberpunk night", "#", "Neon, rain, and questionable life choices"),
    ("Finish this year", "!", "The backlog I keep promising to close"),
]


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:140] or "list"


def _unique_slug(db: Session, user_id: int, name: str) -> str:
    base = _slugify(name)
    slug = base
    n = 2
    while (
        db.query(Collection)
        .filter(Collection.user_id == user_id, Collection.slug == slug)
        .first()
    ):
        slug = f"{base}-{n}"[:140]
        n += 1
    return slug


def _collection_out(db: Session, row: Collection) -> CollectionOut:
    item_rows = (
        db.query(CollectionItem)
        .filter(CollectionItem.collection_id == row.id)
        .order_by(CollectionItem.id.desc())
        .all()
    )
    covers: list[str] = []
    if item_rows:
        art = (
            db.query(Anime.image_url)
            .filter(Anime.id.in_([i.anime_id for i in item_rows[:4]]))
            .all()
        )
        covers = [url for (url,) in art if url]
    return CollectionOut(
        id=row.id,
        name=row.name,
        slug=row.slug,
        emoji=row.emoji,
        description=row.description,
        is_public=bool(row.is_public),
        count=len(item_rows),
        covers=covers,
        created_at=row.created_at,
    )


@router.get("", response_model=list[CollectionOut])
def list_collections(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Collection)
        .filter(Collection.user_id == user.id)
        .order_by(Collection.created_at.asc(), Collection.id.asc())
        .all()
    )
    if not rows:
        # Give a new account something to drag titles into instead of a blank page.
        for name, emoji, description in STARTER_COLLECTIONS:
            db.add(
                Collection(
                    user_id=user.id,
                    name=name,
                    slug=_unique_slug(db, user.id, name),
                    emoji=emoji,
                    description=description,
                )
            )
        db.commit()
        rows = (
            db.query(Collection)
            .filter(Collection.user_id == user.id)
            .order_by(Collection.id.asc())
            .all()
        )
    return [_collection_out(db, row) for row in rows]


@router.post("", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CollectionIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = Collection(
        user_id=user.id,
        name=payload.name.strip(),
        slug=_unique_slug(db, user.id, payload.name),
        emoji=payload.emoji or "*",
        description=payload.description,
        is_public=payload.is_public,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _collection_out(db, row)


@router.get("/{collection_id}", response_model=CollectionDetailOut)
def get_collection(
    collection_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.get(Collection, collection_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = (
        db.query(Anime)
        .join(CollectionItem, CollectionItem.anime_id == Anime.id)
        .filter(CollectionItem.collection_id == row.id)
        .order_by(CollectionItem.id.desc())
        .all()
    )
    base = _collection_out(db, row)
    return CollectionDetailOut(**base.model_dump(), items=[AnimeOut.model_validate(a) for a in items])


@router.put("/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: int,
    payload: CollectionIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.get(Collection, collection_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    row.name = payload.name.strip()
    row.emoji = payload.emoji or "*"
    row.description = payload.description
    row.is_public = payload.is_public
    db.commit()
    db.refresh(row)
    return _collection_out(db, row)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.get(Collection, collection_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    db.query(CollectionItem).filter(CollectionItem.collection_id == row.id).delete(
        synchronize_session=False
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{collection_id}/items", response_model=CollectionDetailOut)
def add_item(
    collection_id: int,
    payload: CollectionItemIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.get(Collection, collection_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    anime = db.get(Anime, payload.anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")

    existing = (
        db.query(CollectionItem)
        .filter(
            CollectionItem.collection_id == row.id,
            CollectionItem.anime_id == anime.id,
        )
        .first()
    )
    if existing:
        existing.note = payload.note
    else:
        db.add(CollectionItem(collection_id=row.id, anime_id=anime.id, note=payload.note))
        events.record(
            db,
            user_id=user.id,
            kind="collection_add",
            anime_id=anime.id,
            detail=f"{anime.title} into {row.name}",
        )
    db.commit()
    return get_collection(collection_id, user, db)


@router.delete("/{collection_id}/items/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    collection_id: int,
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.get(Collection, collection_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    db.query(CollectionItem).filter(
        CollectionItem.collection_id == row.id, CollectionItem.anime_id == anime_id
    ).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------- notes

notes_router = APIRouter(prefix="/api/notes", tags=["notes"])


@notes_router.get("/{anime_id}", response_model=NoteOut)
def get_note(
    anime_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(Note).filter(Note.user_id == user.id, Note.anime_id == anime_id).first()
    )
    if not row:
        return NoteOut(anime_id=anime_id, body="", is_shared=False, updated_at=None)
    return NoteOut(
        anime_id=anime_id, body=row.body or "", is_shared=bool(row.is_shared), updated_at=row.updated_at
    )


@notes_router.put("/{anime_id}", response_model=NoteOut)
def put_note(
    anime_id: int,
    payload: NoteIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not db.get(Anime, anime_id):
        raise HTTPException(status_code=404, detail="Anime not found")
    row = db.query(Note).filter(Note.user_id == user.id, Note.anime_id == anime_id).first()
    if not row:
        row = Note(user_id=user.id, anime_id=anime_id)
        db.add(row)
    row.body = payload.body
    row.is_shared = payload.is_shared
    db.commit()
    db.refresh(row)
    return NoteOut(
        anime_id=anime_id, body=row.body or "", is_shared=bool(row.is_shared), updated_at=row.updated_at
    )
