from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Anime, Rating
from app.services.cache import cache_get, cache_set


@dataclass
class ScoredAnime:
    anime: Anime
    score: float
    reason: str
    method: str


class HybridRecommender:
    """Hybrid engine: TF-IDF content similarity + item-item collaborative filtering."""

    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._anime_ids: list[int] = []
        self._id_to_idx: dict[int, int] = {}
        self._ready = False

    def fit(self, db: Session) -> None:
        rows = db.query(Anime).order_by(Anime.id).all()
        if not rows:
            self._ready = False
            return

        corpus = [
            " ".join(
                filter(
                    None,
                    [
                        a.title,
                        a.title_english or "",
                        a.genres,
                        a.themes,
                        a.studios,
                        a.synopsis or "",
                        a.type or "",
                        str(a.year or ""),
                    ],
                )
            )
            for a in rows
        ]
        self._vectorizer = TfidfVectorizer(
            max_features=8000,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        self._matrix = self._vectorizer.fit_transform(corpus)
        self._anime_ids = [a.id for a in rows]
        self._id_to_idx = {aid: i for i, aid in enumerate(self._anime_ids)}
        self._ready = True

    def ensure_fit(self, db: Session) -> None:
        if not self._ready:
            self.fit(db)

    def _lexical_search(self, db: Session, query: str, limit: int) -> list[Anime]:
        """Multi-token ILIKE fallback across title, English title, genres, themes, synopsis."""
        tokens = [t for t in query.strip().split() if len(t) >= 2]
        clauses = []
        for token in tokens:
            pattern = f"%{token}%"
            clauses.append(
                or_(
                    Anime.title.ilike(pattern),
                    Anime.title_english.ilike(pattern),
                    Anime.genres.ilike(pattern),
                    Anime.themes.ilike(pattern),
                    Anime.synopsis.ilike(pattern),
                )
            )
        full_pattern = f"%{query.strip()}%"
        full_match = or_(
            Anime.title.ilike(full_pattern),
            Anime.title_english.ilike(full_pattern),
        )
        if clauses:
            filt = or_(full_match, and_(*clauses))
        else:
            filt = full_match
        return (
            db.query(Anime)
            .filter(filt)
            .order_by(Anime.score.desc().nullslast())
            .limit(limit)
            .all()
        )

    def search(self, db: Session, query: str, limit: int = 24, *, lexical_only: bool = False) -> list[Anime]:
        self.ensure_fit(db)
        # Bust stale caches when catalog grows (e.g. demo title backfill).
        cache_key = f"search:v2:{query.lower().strip()}:{limit}:{int(lexical_only)}"
        cached = cache_get(cache_key)
        if cached:
            ids = cached
            by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
            return [by_id[i] for i in ids if i in by_id]

        if not query.strip():
            rows = (
                db.query(Anime)
                .order_by(Anime.score.desc().nullslast(), Anime.popularity.desc())
                .limit(limit)
                .all()
            )
            return rows

        lexical = self._lexical_search(db, query, limit=limit)
        if lexical_only or not self._ready:
            if lexical:
                cache_set(cache_key, [a.id for a in lexical])
            return lexical

        q = self._vectorizer.transform([query])
        sims = cosine_similarity(q, self._matrix).ravel()
        # Require a meaningful similarity so weak OOV matches don't drown titles.
        top_idx = np.argsort(-sims)[: limit * 2]
        tfidf_ids = [self._anime_ids[i] for i in top_idx if sims[i] > 0.08]

        # Prefer lexical (exact/token title hits), then fill with TF-IDF.
        seen: set[int] = set()
        ordered: list[Anime] = []
        for anime in lexical:
            if anime.id not in seen:
                ordered.append(anime)
                seen.add(anime.id)
        if tfidf_ids:
            by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(tfidf_ids)).all()}
            for aid in tfidf_ids:
                if aid not in seen and aid in by_id:
                    ordered.append(by_id[aid])
                    seen.add(aid)
                if len(ordered) >= limit:
                    break

        ordered = ordered[:limit]
        if ordered:
            cache_set(cache_key, [a.id for a in ordered])
        return ordered

    def recommend_for_user(self, db: Session, user_id: int, limit: int = 12) -> tuple[list[ScoredAnime], bool]:
        self.ensure_fit(db)
        cache_key = f"recs:user:{user_id}:{limit}"
        cached = cache_get(cache_key)
        if cached:
            ids = [c["anime_id"] for c in cached]
            by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
            out = []
            for c in cached:
                anime = by_id.get(c["anime_id"])
                if anime:
                    out.append(
                        ScoredAnime(
                            anime=anime,
                            score=c["score"],
                            reason=c["reason"],
                            method=c["method"],
                        )
                    )
            return out, True

        ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        if not ratings:
            popular = (
                db.query(Anime)
                .order_by(Anime.score.desc().nullslast(), Anime.scored_by.desc())
                .limit(limit)
                .all()
            )
            out = [
                ScoredAnime(
                    anime=a,
                    score=float(a.score or 0),
                    reason="Popular titles while we learn your taste",
                    method="popularity",
                )
                for a in popular
            ]
            payload = [
                {"anime_id": s.anime.id, "score": s.score, "reason": s.reason, "method": s.method}
                for s in out
            ]
            cache_set(cache_key, payload)
            return out, False

        liked = [r for r in ratings if r.score >= 7]
        seed_ids = [r.anime_id for r in (liked or ratings)]
        rated_ids = {r.anime_id for r in ratings}

        content_scores: dict[int, float] = {}
        for seed_id in seed_ids:
            idx = self._id_to_idx.get(seed_id)
            if idx is None:
                continue
            sims = cosine_similarity(self._matrix[idx], self._matrix).ravel()
            for j, sim in enumerate(sims):
                aid = self._anime_ids[j]
                if aid in rated_ids:
                    continue
                content_scores[aid] = max(content_scores.get(aid, 0.0), float(sim))

        collab_scores = self._collaborative_scores(db, user_id, rated_ids)

        combined: dict[int, tuple[float, str, str]] = {}
        for aid, score in content_scores.items():
            combined[aid] = (0.65 * score, "Similar themes/genres to shows you liked", "content")
        for aid, score in collab_scores.items():
            if aid in combined:
                base, _, _ = combined[aid]
                combined[aid] = (base + 0.35 * score, "Liked by users with similar taste", "hybrid")
            else:
                combined[aid] = (0.35 * score, "Liked by users with similar taste", "collaborative")

        ranked = sorted(combined.items(), key=lambda x: -x[1][0])[:limit]
        ids = [aid for aid, _ in ranked]
        by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
        out: list[ScoredAnime] = []
        for aid, (score, reason, method) in ranked:
            anime = by_id.get(aid)
            if anime:
                out.append(ScoredAnime(anime=anime, score=score, reason=reason, method=method))

        payload = [
            {"anime_id": s.anime.id, "score": s.score, "reason": s.reason, "method": s.method}
            for s in out
        ]
        cache_set(cache_key, payload)
        return out, False

    def similar_to(self, db: Session, anime_id: int, limit: int = 12) -> list[ScoredAnime]:
        self.ensure_fit(db)
        cache_key = f"similar:{anime_id}:{limit}"
        cached = cache_get(cache_key)
        if cached:
            ids = [c["anime_id"] for c in cached]
            by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
            return [
                ScoredAnime(
                    anime=by_id[c["anime_id"]],
                    score=c["score"],
                    reason=c["reason"],
                    method=c["method"],
                )
                for c in cached
                if c["anime_id"] in by_id
            ]

        idx = self._id_to_idx.get(anime_id)
        if idx is None:
            return []
        sims = cosine_similarity(self._matrix[idx], self._matrix).ravel()
        top = np.argsort(-sims)[1 : limit + 1]
        ids = [self._anime_ids[i] for i in top]
        by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
        out = [
            ScoredAnime(
                anime=by_id[self._anime_ids[i]],
                score=float(sims[i]),
                reason="Content similarity (TF-IDF + cosine)",
                method="content",
            )
            for i in top
            if self._anime_ids[i] in by_id
        ]
        payload = [
            {"anime_id": s.anime.id, "score": s.score, "reason": s.reason, "method": s.method}
            for s in out
        ]
        cache_set(cache_key, payload)
        return out

    def _collaborative_scores(
        self, db: Session, user_id: int, rated_ids: set[int]
    ) -> dict[int, float]:
        my_ratings = {r.anime_id: r.score for r in db.query(Rating).filter(Rating.user_id == user_id)}
        if not my_ratings:
            return {}

        # Find users who rated overlapping titles
        other_ratings = (
            db.query(Rating)
            .filter(Rating.user_id != user_id, Rating.anime_id.in_(list(my_ratings.keys())))
            .all()
        )
        by_user: dict[int, dict[int, float]] = {}
        for r in other_ratings:
            by_user.setdefault(r.user_id, {})[r.anime_id] = r.score

        neighbor_weights: dict[int, float] = {}
        for other_id, their in by_user.items():
            shared = [aid for aid in their if aid in my_ratings]
            if len(shared) < 2:
                continue
            a = np.array([my_ratings[aid] for aid in shared], dtype=float)
            b = np.array([their[aid] for aid in shared], dtype=float)
            if np.std(a) == 0 or np.std(b) == 0:
                continue
            corr = float(np.corrcoef(a, b)[0, 1])
            if corr > 0:
                neighbor_weights[other_id] = corr

        if not neighbor_weights:
            return {}

        top_neighbors = sorted(neighbor_weights.items(), key=lambda x: -x[1])[:25]
        neighbor_ids = [uid for uid, _ in top_neighbors]
        cand_ratings = db.query(Rating).filter(Rating.user_id.in_(neighbor_ids)).all()

        scores: dict[int, float] = {}
        weights: dict[int, float] = {}
        weight_map = dict(top_neighbors)
        for r in cand_ratings:
            if r.anime_id in rated_ids:
                continue
            w = weight_map.get(r.user_id, 0.0)
            scores[r.anime_id] = scores.get(r.anime_id, 0.0) + w * r.score
            weights[r.anime_id] = weights.get(r.anime_id, 0.0) + w

        return {
            aid: scores[aid] / weights[aid]
            for aid in scores
            if weights[aid] > 0
        }


recommender = HybridRecommender()
