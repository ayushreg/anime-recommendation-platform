"""Cold-start taste quiz and the blend between quiz answers and real behaviour."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import Rating, UserPreference
from app.services.attention import genre_affinity

# Ten questions, each choice worth a small push toward a few catalog tags.
QUIZ: list[dict] = [
    {
        "id": "energy",
        "prompt": "Pick tonight's energy",
        "choices": [
            {"id": "loud", "label": "Loud and kinetic", "tags": "Action,Adventure,Sports"},
            {"id": "quiet", "label": "Quiet and warm", "tags": "Slice of Life,Comedy,Romance"},
            {"id": "tense", "label": "Tense and twisty", "tags": "Thriller,Mystery,Psychological"},
        ],
    },
    {
        "id": "world",
        "prompt": "Where should it be set",
        "choices": [
            {"id": "now", "label": "Somewhere like now", "tags": "School,Drama,Slice of Life"},
            {"id": "elsewhere", "label": "Another world entirely", "tags": "Fantasy,Isekai,Adventure"},
            {"id": "future", "label": "A future that went wrong", "tags": "Sci-Fi,Mecha,Space"},
        ],
    },
    {
        "id": "stakes",
        "prompt": "How high are the stakes",
        "choices": [
            {"id": "world", "label": "The whole world", "tags": "Action,Military,Supernatural"},
            {"id": "person", "label": "One person's life", "tags": "Drama,Psychological,Romance"},
            {"id": "none", "label": "Nothing at all, thanks", "tags": "Comedy,Slice of Life,Music"},
        ],
    },
    {
        "id": "length",
        "prompt": "How long can you commit",
        "choices": [
            {"id": "movie", "label": "One evening", "tags": "Movie,Drama"},
            {"id": "cour", "label": "A single season", "tags": "TV,Mystery,Thriller"},
            {"id": "epic", "label": "Give me hundreds of episodes", "tags": "Adventure,Action,Shounen"},
        ],
    },
    {
        "id": "ending",
        "prompt": "What kind of ending do you want",
        "choices": [
            {"id": "happy", "label": "Send me off smiling", "tags": "Comedy,Romance,Slice of Life"},
            {"id": "gut", "label": "Wreck me", "tags": "Drama,Tragedy,Psychological"},
            {"id": "open", "label": "Leave me thinking", "tags": "Mystery,Psychological,Sci-Fi"},
        ],
    },
    {
        "id": "cast",
        "prompt": "Who do you want to follow",
        "choices": [
            {"id": "underdog", "label": "An underdog with something to prove", "tags": "Sports,Shounen,Action"},
            {"id": "genius", "label": "Someone dangerously clever", "tags": "Psychological,Mystery,Thriller"},
            {"id": "group", "label": "A messy group of friends", "tags": "Comedy,School,Slice of Life"},
        ],
    },
    {
        "id": "look",
        "prompt": "Pick a look",
        "choices": [
            {"id": "neon", "label": "Neon and rain", "tags": "Sci-Fi,Supernatural,Psychological"},
            {"id": "pastel", "label": "Soft pastel afternoons", "tags": "Slice of Life,Romance,Music"},
            {"id": "ink", "label": "Heavy ink and grit", "tags": "Action,Historical,Military"},
        ],
    },
    {
        "id": "sound",
        "prompt": "What should the soundtrack do",
        "choices": [
            {"id": "band", "label": "Carry the whole show", "tags": "Music,Drama"},
            {"id": "orchestra", "label": "Swell at the right moment", "tags": "Fantasy,Adventure,Drama"},
            {"id": "silence", "label": "Get out of the way", "tags": "Mystery,Psychological,Slice of Life"},
        ],
    },
    {
        "id": "weird",
        "prompt": "How weird can it get",
        "choices": [
            {"id": "grounded", "label": "Keep it grounded", "tags": "Drama,Sports,School"},
            {"id": "strange", "label": "A little strange is good", "tags": "Supernatural,Fantasy,Comedy"},
            {"id": "unhinged", "label": "Completely unhinged", "tags": "Psychological,Horror,Sci-Fi"},
        ],
    },
    {
        "id": "guilt",
        "prompt": "Last one: your comfort pick is",
        "choices": [
            {"id": "shounen", "label": "A long running shounen", "tags": "Action,Adventure,Martial Arts"},
            {"id": "romcom", "label": "A romcom you have seen twice", "tags": "Romance,Comedy,School"},
            {"id": "mecha", "label": "Robots hitting each other", "tags": "Mecha,Sci-Fi,Military"},
        ],
    },
]

QUIZ_BY_ID = {q["id"]: q for q in QUIZ}


def score_answers(answers: list[tuple[str, str]]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for question_id, choice_id in answers:
        question = QUIZ_BY_ID.get(question_id)
        if not question:
            continue
        for choice in question["choices"]:
            if choice["id"] != choice_id:
                continue
            for tag in choice["tags"].split(","):
                tag = tag.strip()
                if tag:
                    weights[tag] = weights.get(tag, 0.0) + 1.0
    if not weights:
        return {}
    peak = max(weights.values())
    return {k: round(v / peak, 4) for k, v in weights.items()}


def load_quiz_taste(prefs: UserPreference | None) -> dict[str, float]:
    if not prefs or not prefs.taste_json:
        return {}
    try:
        raw = json.loads(prefs.taste_json)
    except (TypeError, ValueError):
        return {}
    return {str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))}


def save_quiz_taste(prefs: UserPreference, weights: dict[str, float]) -> None:
    prefs.taste_json = json.dumps(weights)
    prefs.quiz_done = True


def blended_affinity(db: Session, user_id: int, prefs: UserPreference | None) -> dict[str, float]:
    """Quiz answers carry the cold start, then real ratings take over.

    With no ratings the quiz is the whole signal. By about twenty ratings the
    quiz is down to a quarter of the weight, which is roughly the point where
    behaviour is more honest than a questionnaire.
    """
    behaviour = genre_affinity(db, user_id)
    quiz = load_quiz_taste(prefs)
    if not quiz:
        return behaviour
    if not behaviour:
        return quiz

    rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()
    quiz_weight = max(0.15, 1.0 - min(1.0, rating_count / 20.0) * 0.85)
    merged: dict[str, float] = dict(behaviour)
    for tag, value in quiz.items():
        merged[tag] = merged.get(tag, 0.0) * (1 - quiz_weight) + value * quiz_weight
    return {k: round(v, 4) for k, v in merged.items()}
