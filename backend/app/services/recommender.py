from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Anime, Rating, WatchlistItem
from app.services.cache import cache_get, cache_set
from app.services.ordering import ADULT_TAGS, best_first, is_adult, safe_filter

# A rating from six months ago counts about a third as much as one from today.
RATING_HALF_LIFE_DAYS = 120.0

VARIANTS = ("hybrid", "content", "collaborative", "popularity")


@dataclass
class ScoredAnime:
    anime: Anime
    score: float
    reason: str
    method: str
    seed_title: str | None = None
    shared_tags: list[str] | None = None


def _split(raw: str | None) -> list[str]:
    from app.services.attention import _split as normalized

    return normalized(raw)


def same_franchise(a: str | None, b: str | None) -> bool:
    """Treat 'gantz' and 'gantz stage' as one thing.

    Franchise keys are built by stripping season and format words from a title,
    which leaves sequels as a prefix of, or prefixed by, the original. Comparing
    on that prefix catches the cases a plain equality check misses.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    return a.startswith(f"{b} ") or b.startswith(f"{a} ")


def _decay(created_at: datetime | None) -> float:
    if not created_at:
        return 1.0
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return float(0.5 ** (age_days / RATING_HALF_LIFE_DAYS))


class HybridRecommender:
    """Hybrid engine: TF-IDF content similarity + item-item collaborative filtering."""

    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._anime_ids: list[int] = []
        self._id_to_idx: dict[int, int] = {}
        self._adult_ids: set[int] = set()
        self._franchise: dict[int, str] = {}
        self._ready = False

    def fit(self, db: Session) -> None:
        rows = db.query(Anime).order_by(Anime.id).all()
        if not rows:
            self._ready = False
            return

        # Built once here instead of re-queried per request.
        self._adult_ids = {a.id for a in rows if is_adult(a)}
        self._franchise = {a.id: (a.franchise_key or a.title.lower()) for a in rows}

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

    def wants_adult(self, query: str) -> bool:
        """Only surface adult rows when the query itself asks for them."""
        text = (query or "").lower()
        return any(tag in text for tag in ADULT_TAGS)

    def _drop_adult(self, rows: list[Anime], query: str) -> list[Anime]:
        if self.wants_adult(query):
            return rows
        return [a for a in rows if a.id not in self._adult_ids]

    def search(self, db: Session, query: str, limit: int = 24, *, lexical_only: bool = False) -> list[Anime]:
        self.ensure_fit(db)
        # Bust stale caches when catalog grows (e.g. demo title backfill).
        cache_key = f"search:v3:{query.lower().strip()}:{limit}:{int(lexical_only)}"
        cached = cache_get(cache_key)
        if cached:
            ids = cached
            by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
            return [by_id[i] for i in ids if i in by_id]

        if not query.strip():
            rows = (
                safe_filter(db.query(Anime))
                .order_by(*best_first())
                .limit(limit)
                .all()
            )
            return rows

        lexical = self._drop_adult(
            self._lexical_search(db, query, limit=limit * 2), query
        )[:limit]
        if lexical_only or not self._ready:
            if lexical:
                cache_set(cache_key, [a.id for a in lexical])
            return lexical

        q = self._vectorizer.transform([query])
        sims = cosine_similarity(q, self._matrix).ravel()
        # Require a meaningful similarity so weak OOV matches don't drown titles.
        top_idx = np.argsort(-sims)[: limit * 2]
        allow_adult = self.wants_adult(query)
        tfidf_ids = [
            self._anime_ids[i]
            for i in top_idx
            if sims[i] > 0.08 and (allow_adult or self._anime_ids[i] not in self._adult_ids)
        ]

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

    # ------------------------------------------------------------------ recs

    def recommend_for_user(
        self,
        db: Session,
        user_id: int,
        limit: int = 12,
        *,
        variant: str = "hybrid",
        diversity: float = 0.35,
        exclude_ids: set[int] | None = None,
    ) -> tuple[list[ScoredAnime], bool]:
        self.ensure_fit(db)
        variant = variant if variant in VARIANTS else "hybrid"
        exclude_ids = set(exclude_ids or set())
        # The version segment sits inside the "recs:user:{id}:*" delete pattern so
        # a ranking change invalidates every cached page without a Redis flush.
        cache_key = (
            f"recs:user:{user_id}:v4:{limit}:{variant}:"
            f"{round(diversity, 2)}:{len(exclude_ids)}"
        )
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
                            seed_title=c.get("seed_title"),
                            shared_tags=c.get("shared_tags") or [],
                        )
                    )
            return out, True

        ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        if not ratings or variant == "popularity":
            out = self._popular_fallback(db, limit, exclude_ids)
            cache_set(cache_key, [self._payload(s) for s in out])
            return out, False

        liked = [r for r in ratings if r.score >= 7]
        seeds = liked or ratings
        rated_ids = {r.anime_id for r in ratings}
        blocked = rated_ids | exclude_ids | self._adult_ids
        # Franchises you have already rated should not come back as their own
        # sequels, movies, and recaps.
        rated_franchises = {
            self._franchise.get(aid) for aid in rated_ids if self._franchise.get(aid)
        }

        content_scores: dict[int, tuple[float, int]] = {}
        if variant in ("hybrid", "content"):
            content_scores = self._content_scores(db, seeds, blocked)

        collab_scores: dict[int, float] = {}
        if variant in ("hybrid", "collaborative"):
            collab_scores = self._collaborative_scores(db, user_id, blocked)

        combined: dict[int, tuple[float, str, int | None]] = {}
        for aid, (score, seed_id) in content_scores.items():
            combined[aid] = (0.65 * score, "content", seed_id)
        for aid, score in collab_scores.items():
            if aid in combined:
                base, _, seed_id = combined[aid]
                combined[aid] = (base + 0.35 * score, "hybrid", seed_id)
            else:
                combined[aid] = (0.35 * score, "collaborative", None)

        if not combined:
            out = self._popular_fallback(db, limit, exclude_ids)
            cache_set(cache_key, [self._payload(s) for s in out])
            return out, False

        pool_size = max(limit * 6, 60)
        ordered = sorted(combined.items(), key=lambda x: -x[1][0])

        # One entry per franchise. Ten flavours of the same show is not a page
        # of recommendations, it is a search result.
        seen_franchises: list[str] = [k for k in rated_franchises if k]
        ranked: list[tuple[int, tuple[float, str, int | None]]] = []
        for aid, payload in ordered:
            key = self._franchise.get(aid)
            if key and any(same_franchise(key, seen) for seen in seen_franchises):
                continue
            if key:
                seen_franchises.append(key)
            ranked.append((aid, payload))
            if len(ranked) >= pool_size:
                break

        pool_ids = [aid for aid, _ in ranked]
        by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(pool_ids)).all()}
        seed_titles = {
            a.id: a
            for a in db.query(Anime)
            .filter(Anime.id.in_({s for _, (_, _, s) in ranked if s}))
            .all()
        }

        picked = self._diversify([aid for aid in pool_ids if aid in by_id], diversity, limit)

        out: list[ScoredAnime] = []
        for aid in picked:
            anime = by_id[aid]
            score, method, seed_id = combined[aid]
            seed = seed_titles.get(seed_id) if seed_id else None
            shared = self._shared_tags(anime, seed) if seed else []
            if seed and shared:
                reason = f"Because you liked {seed.title} (shares {', '.join(shared[:2])})"
            elif seed:
                reason = f"Because you liked {seed.title}"
            elif method == "collaborative":
                reason = "Rated highly by accounts whose taste lines up with yours"
            else:
                reason = "Close to the themes you keep finishing"
            out.append(
                ScoredAnime(
                    anime=anime,
                    score=score,
                    reason=reason,
                    method=method,
                    seed_title=seed.title if seed else None,
                    shared_tags=shared,
                )
            )

        cache_set(cache_key, [self._payload(s) for s in out])
        return out, False

    @staticmethod
    def _payload(s: ScoredAnime) -> dict:
        return {
            "anime_id": s.anime.id,
            "score": s.score,
            "reason": s.reason,
            "method": s.method,
            "seed_title": s.seed_title,
            "shared_tags": s.shared_tags or [],
        }

    @staticmethod
    def _shared_tags(anime: Anime, seed: Anime | None) -> list[str]:
        if not seed:
            return []
        mine = set(_split(anime.genres) + _split(anime.themes))
        theirs = set(_split(seed.genres) + _split(seed.themes))
        return sorted(mine & theirs)

    def _popular_fallback(
        self, db: Session, limit: int, exclude_ids: set[int]
    ) -> list[ScoredAnime]:
        query = safe_filter(db.query(Anime))
        if exclude_ids:
            query = query.filter(~Anime.id.in_(list(exclude_ids)))
        popular = (
            query.order_by(*best_first())
            .limit(limit)
            .all()
        )
        return [
            ScoredAnime(
                anime=a,
                score=float(a.score or 0),
                reason="Popular in the vault while we learn your taste",
                method="popularity",
            )
            for a in popular
        ]

    def _content_scores(
        self, db: Session, seeds: list[Rating], blocked: set[int]
    ) -> dict[int, tuple[float, int]]:
        """Best content match per candidate, remembering which seed produced it."""
        if not self._ready or self._matrix is None:
            return {}
        scores: dict[int, tuple[float, int]] = {}
        # Newest, strongest ratings first, and cap the fan-out so a 500 rating
        # library does not turn one request into 500 cosine passes.
        ordered = sorted(seeds, key=lambda r: (-_decay(r.created_at) * r.score))[:40]
        for rating in ordered:
            idx = self._id_to_idx.get(rating.anime_id)
            if idx is None:
                continue
            weight = _decay(rating.created_at) * (rating.score / 10.0)
            sims = cosine_similarity(self._matrix[idx], self._matrix).ravel()
            top = np.argsort(-sims)[:60]
            for j in top:
                aid = self._anime_ids[j]
                if aid in blocked:
                    continue
                value = float(sims[j]) * weight
                current = scores.get(aid)
                if current is None or value > current[0]:
                    scores[aid] = (value, rating.anime_id)
        return scores

    def _diversify(self, candidate_ids: list[int], diversity: float, limit: int) -> list[int]:
        """Maximal marginal relevance so the page is not ten clones of one show."""
        if not candidate_ids:
            return []
        if diversity <= 0.02 or not self._ready or self._matrix is None:
            return candidate_ids[:limit]

        lam = max(0.0, min(1.0, diversity))
        picked: list[int] = [candidate_ids[0]]
        remaining = candidate_ids[1:]

        while remaining and len(picked) < limit:
            best_id = remaining[0]
            best_value = -1e9
            picked_idx = [self._id_to_idx[p] for p in picked if p in self._id_to_idx]
            for rank, aid in enumerate(remaining):
                idx = self._id_to_idx.get(aid)
                relevance = 1.0 - (rank / max(1, len(remaining)))
                if idx is None or not picked_idx:
                    novelty = 1.0
                else:
                    sims = cosine_similarity(self._matrix[idx], self._matrix[picked_idx]).ravel()
                    novelty = 1.0 - float(sims.max())
                value = (1.0 - lam) * relevance + lam * novelty
                if value > best_value:
                    best_value = value
                    best_id = aid
            picked.append(best_id)
            remaining.remove(best_id)

        return picked

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

        neighbor_weights = self.neighbor_weights(db, user_id, my_ratings)
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
            w = weight_map.get(r.user_id, 0.0) * _decay(r.created_at)
            scores[r.anime_id] = scores.get(r.anime_id, 0.0) + w * r.score
            weights[r.anime_id] = weights.get(r.anime_id, 0.0) + w

        return {
            aid: scores[aid] / weights[aid]
            for aid in scores
            if weights[aid] > 0
        }

    def neighbor_weights(
        self, db: Session, user_id: int, my_ratings: dict[int, float] | None = None
    ) -> dict[int, float]:
        """Pearson correlation with every account that shares at least two titles."""
        if my_ratings is None:
            my_ratings = {
                r.anime_id: r.score
                for r in db.query(Rating).filter(Rating.user_id == user_id)
            }
        if not my_ratings:
            return {}

        other_ratings = (
            db.query(Rating)
            .filter(Rating.user_id != user_id, Rating.anime_id.in_(list(my_ratings.keys())))
            .all()
        )
        by_user: dict[int, dict[int, float]] = {}
        for r in other_ratings:
            by_user.setdefault(r.user_id, {})[r.anime_id] = r.score

        weights: dict[int, float] = {}
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
                # More overlap means more confidence in the correlation.
                weights[other_id] = corr * min(1.0, math.log1p(len(shared)) / math.log(12))
        return weights

    def next_title_markov(self, db: Session, user_id: int, limit: int = 8) -> list[ScoredAnime]:
        """Bigram over completion order across all accounts: what follows what."""
        completions = (
            db.query(WatchlistItem)
            .filter(WatchlistItem.status == "completed")
            .order_by(WatchlistItem.user_id, WatchlistItem.completed_at.nullslast(), WatchlistItem.updated_at)
            .all()
        )
        by_user: dict[int, list[int]] = {}
        for item in completions:
            by_user.setdefault(item.user_id, []).append(item.anime_id)

        transitions: dict[int, dict[int, int]] = {}
        for uid, sequence in by_user.items():
            for a, b in zip(sequence, sequence[1:]):
                if a == b:
                    continue
                transitions.setdefault(a, {})
                transitions[a][b] = transitions[a].get(b, 0) + 1

        mine = by_user.get(user_id, [])
        if not mine:
            return []
        recent = mine[-5:]
        seen = set(mine)

        scores: dict[int, float] = {}
        origins: dict[int, int] = {}
        for weight, anime_id in zip((1.0, 0.8, 0.6, 0.45, 0.3), reversed(recent)):
            for nxt, count in (transitions.get(anime_id) or {}).items():
                if nxt in seen:
                    continue
                scores[nxt] = scores.get(nxt, 0.0) + weight * count
                origins.setdefault(nxt, anime_id)

        if not scores:
            return []
        top = sorted(scores.items(), key=lambda x: -x[1])[:limit]
        ids = [aid for aid, _ in top] + list(origins.values())
        by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
        out: list[ScoredAnime] = []
        for aid, score in top:
            anime = by_id.get(aid)
            if not anime:
                continue
            origin = by_id.get(origins.get(aid, 0))
            reason = (
                f"People who finished {origin.title} watched this next"
                if origin
                else "Common next watch in this vault"
            )
            out.append(
                ScoredAnime(
                    anime=anime,
                    score=float(score),
                    reason=reason,
                    method="sequence",
                    seed_title=origin.title if origin else None,
                )
            )
        return out


recommender = HybridRecommender()
