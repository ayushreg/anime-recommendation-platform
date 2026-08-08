"""Local-instance social: friend codes, a feed, an opt-in leaderboard.

Nothing federates. These are the accounts on this one machine, which is the
whole point when the family shares a server.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import (
    ActivityEvent,
    Anime,
    Friendship,
    User,
    UserPreference,
    WatchDay,
    WatchlistItem,
)
from app.schemas import (
    ActivityOut,
    AnimeOut,
    FollowIn,
    FriendOut,
    RecommendToFriendIn,
)
from app.services import events
from app.services.flags import enabled
from app.services.library import get_preferences, now

router = APIRouter(prefix="/api/social", tags=["social"])

FEED_KINDS = (
    "rated",
    "completed",
    "watch_started",
    "collection_add",
    "recommended",
    "rewatch_started",
)


def _require_social() -> None:
    if not enabled("social"):
        raise HTTPException(status_code=404, detail="Social is switched off on this instance")


def _week_hours(db: Session, user_id: int) -> float:
    start = now().date() - timedelta(days=6)
    seconds = (
        db.query(func.coalesce(func.sum(WatchDay.seconds), 0))
        .filter(WatchDay.user_id == user_id, WatchDay.day >= start)
        .scalar()
        or 0
    )
    return round(seconds / 3600, 2)


def _completed(db: Session, user_id: int) -> int:
    return (
        db.query(func.count(WatchlistItem.id))
        .filter(WatchlistItem.user_id == user_id, WatchlistItem.status == "completed")
        .scalar()
        or 0
    )


@router.get("/me")
def my_card(user: User = Depends(require_user), db: Session = Depends(get_db)):
    _require_social()
    prefs = get_preferences(db, user.id)
    db.commit()
    return {
        "user_id": user.id,
        "username": user.username,
        "friend_code": user.friend_code,
        "share_activity": bool(prefs.share_activity),
        "hours_this_week": _week_hours(db, user.id),
        "completed": _completed(db, user.id),
    }


@router.get("/friends", response_model=list[FriendOut])
def list_friends(user: User = Depends(require_user), db: Session = Depends(get_db)):
    _require_social()
    edges = db.query(Friendship).filter(Friendship.user_id == user.id).all()
    if not edges:
        return []
    friends = {
        u.id: u
        for u in db.query(User).filter(User.id.in_([e.friend_id for e in edges])).all()
    }
    return [
        FriendOut(
            user_id=friend.id,
            username=friend.username,
            friend_code=friend.friend_code,
            hours_this_week=_week_hours(db, friend.id),
            completed=_completed(db, friend.id),
        )
        for friend in friends.values()
    ]


@router.post("/follow", response_model=FriendOut)
def follow(
    payload: FollowIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _require_social()
    code = payload.friend_code.strip().upper()
    friend = db.query(User).filter(func.upper(User.friend_code) == code).first()
    if not friend:
        raise HTTPException(status_code=404, detail="No account on this instance uses that code")
    if friend.id == user.id:
        raise HTTPException(status_code=400, detail="That is your own code")

    exists = (
        db.query(Friendship)
        .filter(Friendship.user_id == user.id, Friendship.friend_id == friend.id)
        .first()
    )
    if not exists:
        db.add(Friendship(user_id=user.id, friend_id=friend.id))
        db.commit()

    return FriendOut(
        user_id=friend.id,
        username=friend.username,
        friend_code=friend.friend_code,
        hours_this_week=_week_hours(db, friend.id),
        completed=_completed(db, friend.id),
    )


@router.delete("/follow/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
def unfollow(
    friend_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _require_social()
    db.query(Friendship).filter(
        Friendship.user_id == user.id, Friendship.friend_id == friend_id
    ).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/feed", response_model=list[ActivityOut])
def feed(
    limit: int = 30,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _require_social()
    friend_ids = [
        e.friend_id for e in db.query(Friendship).filter(Friendship.user_id == user.id).all()
    ]
    visible = set(friend_ids + [user.id])

    # Respect the share toggle for everyone except the viewer.
    muted = {
        p.user_id
        for p in db.query(UserPreference)
        .filter(UserPreference.user_id.in_(list(visible)), UserPreference.share_activity.is_(False))
        .all()
    }
    visible -= muted - {user.id}

    rows = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.user_id.in_(list(visible)), ActivityEvent.kind.in_(FEED_KINDS))
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    users = {u.id: u for u in db.query(User).filter(User.id.in_(list(visible))).all()}
    anime_ids = [r.anime_id for r in rows if r.anime_id]
    animes = (
        {a.id: a for a in db.query(Anime).filter(Anime.id.in_(anime_ids)).all()}
        if anime_ids
        else {}
    )
    return [
        ActivityOut(
            id=r.id,
            username=users[r.user_id].username if r.user_id in users else "someone",
            kind=r.kind,
            detail=r.detail,
            anime=AnimeOut.model_validate(animes[r.anime_id])
            if r.anime_id in animes
            else None,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/leaderboard")
def leaderboard(user: User = Depends(require_user), db: Session = Depends(get_db)):
    _require_social()
    friend_ids = [
        e.friend_id for e in db.query(Friendship).filter(Friendship.user_id == user.id).all()
    ]
    pool = set(friend_ids + [user.id])
    opted_out = {
        p.user_id
        for p in db.query(UserPreference)
        .filter(UserPreference.user_id.in_(list(pool)), UserPreference.share_activity.is_(False))
        .all()
    }
    pool -= opted_out - {user.id}

    users = {u.id: u for u in db.query(User).filter(User.id.in_(list(pool))).all()}
    rows = [
        {
            "user_id": uid,
            "username": users[uid].username,
            "hours": _week_hours(db, uid),
            "completed": _completed(db, uid),
            "is_you": uid == user.id,
        }
        for uid in pool
        if uid in users
    ]
    rows.sort(key=lambda r: -r["hours"])
    return {"period": "last 7 days", "rows": rows, "opted_out": len(opted_out)}


@router.post("/recommend")
def recommend_to_friend(
    payload: RecommendToFriendIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _require_social()
    friend = db.get(User, payload.friend_user_id)
    anime = db.get(Anime, payload.anime_id)
    if not friend or not anime:
        raise HTTPException(status_code=404, detail="Friend or title not found")
    following = (
        db.query(Friendship)
        .filter(Friendship.user_id == user.id, Friendship.friend_id == friend.id)
        .first()
    )
    if not following:
        raise HTTPException(status_code=400, detail="Follow them first with their friend code")

    note = (payload.note or "").strip()
    events.record(
        db,
        user_id=user.id,
        kind="recommended",
        anime_id=anime.id,
        detail=f"{anime.title} to {friend.username}" + (f": {note}" if note else ""),
        target_user_id=friend.id,
    )
    db.commit()
    return {"sent": True, "to": friend.username, "anime_id": anime.id}


@router.get("/inbox", response_model=list[ActivityOut])
def inbox(user: User = Depends(require_user), db: Session = Depends(get_db)):
    _require_social()
    rows = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.target_user_id == user.id, ActivityEvent.kind == "recommended")
        .order_by(ActivityEvent.created_at.desc())
        .limit(40)
        .all()
    )
    users = {
        u.id: u for u in db.query(User).filter(User.id.in_([r.user_id for r in rows])).all()
    }
    anime_ids = [r.anime_id for r in rows if r.anime_id]
    animes = (
        {a.id: a for a in db.query(Anime).filter(Anime.id.in_(anime_ids)).all()}
        if anime_ids
        else {}
    )
    return [
        ActivityOut(
            id=r.id,
            username=users[r.user_id].username if r.user_id in users else "someone",
            kind=r.kind,
            detail=r.detail,
            anime=AnimeOut.model_validate(animes[r.anime_id]) if r.anime_id in animes else None,
            created_at=r.created_at,
        )
        for r in rows
    ]
