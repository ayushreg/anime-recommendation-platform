"""Account preferences, the cold-start quiz, and the public feature flag list."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import User
from app.schemas import (
    PreferencesIn,
    PreferencesOut,
    QuizQuestionOut,
    QuizSubmitIn,
)
from app.services import flags
from app.services.cache import cache_delete_pattern
from app.services.library import get_preferences
from app.services.taste import QUIZ, blended_affinity, load_quiz_taste, save_quiz_taste, score_answers

router = APIRouter(prefix="/api/me", tags=["preferences"])


def _out(db: Session, user_id: int, prefs) -> PreferencesOut:
    return PreferencesOut(
        diversity=float(prefs.diversity or 0.35),
        ranking_variant=prefs.ranking_variant or "hybrid",
        episode_minutes_tv=int(prefs.episode_minutes_tv or 24),
        episode_minutes_movie=int(prefs.episode_minutes_movie or 100),
        idle_timeout_seconds=int(prefs.idle_timeout_seconds or 180),
        auto_tick=bool(prefs.auto_tick),
        sound_enabled=bool(prefs.sound_enabled),
        poster_tint=bool(prefs.poster_tint),
        share_activity=bool(prefs.share_activity),
        quiz_done=bool(prefs.quiz_done),
        taste=load_quiz_taste(prefs),
    )


@router.get("/preferences", response_model=PreferencesOut)
def read_preferences(user: User = Depends(require_user), db: Session = Depends(get_db)):
    prefs = get_preferences(db, user.id)
    db.commit()
    return _out(db, user.id, prefs)


@router.put("/preferences", response_model=PreferencesOut)
def write_preferences(
    payload: PreferencesIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    prefs = get_preferences(db, user.id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(prefs, field, value)
    db.commit()
    db.refresh(prefs)
    # Ranking knobs changed, so the cached rec pages are stale.
    cache_delete_pattern(f"recs:user:{user.id}:*")
    return _out(db, user.id, prefs)


@router.get("/quiz", response_model=list[QuizQuestionOut])
def quiz_questions():
    return [
        QuizQuestionOut(
            id=q["id"],
            prompt=q["prompt"],
            choices=[{"id": c["id"], "label": c["label"]} for c in q["choices"]],
        )
        for q in QUIZ
    ]


@router.post("/quiz", response_model=PreferencesOut)
def submit_quiz(
    payload: QuizSubmitIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    prefs = get_preferences(db, user.id)
    weights = score_answers([(a.question_id, a.choice) for a in payload.answers])
    if weights:
        save_quiz_taste(prefs, weights)
    db.commit()
    db.refresh(prefs)
    cache_delete_pattern(f"recs:user:{user.id}:*")
    return _out(db, user.id, prefs)


@router.get("/affinity")
def affinity(user: User = Depends(require_user), db: Session = Depends(get_db)):
    prefs = get_preferences(db, user.id)
    db.commit()
    merged = blended_affinity(db, user.id, prefs)
    top = sorted(merged.items(), key=lambda kv: -kv[1])[:14]
    return {"tags": [{"tag": tag, "weight": round(weight, 4)} for tag, weight in top]}


flags_router = APIRouter(prefix="/api", tags=["flags"])


@flags_router.get("/flags")
def read_flags():
    return flags.load()
