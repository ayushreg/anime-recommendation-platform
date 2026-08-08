from __future__ import annotations

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from sqlalchemy.orm import Session

from app.models import Anime
from app.services.recommender import recommender

# Vibe words people actually type, mapped onto words the catalog uses.
VIBE_LEXICON: dict[str, str] = {
    "cozy": "slice of life healing relaxing gentle",
    "comfy": "slice of life healing relaxing",
    "chill": "slice of life comedy relaxing",
    "sad": "drama tragedy emotional",
    "cry": "drama tragedy emotional",
    "dark": "psychological thriller horror seinen",
    "edgy": "psychological thriller violence",
    "wholesome": "slice of life family friendship comedy",
    "rain": "atmospheric melancholy drama",
    "school": "school romance youth club",
    "smart": "psychological mystery strategy",
    "brainy": "psychological mystery strategy",
    "fight": "action martial arts tournament shounen",
    "hype": "action shounen tournament",
    "space": "space sci-fi mecha",
    "robot": "mecha sci-fi",
    "food": "gourmet cooking slice of life",
    "sports": "sports team competition",
    "romantic": "romance drama love",
    "funny": "comedy parody gag",
    "short": "ova special movie",
    "classic": "retro historical",
    "creepy": "horror supernatural mystery",
    "epic": "adventure fantasy war",
}


class EmbeddingIndex:
    """Dense semantic index: TF-IDF -> TruncatedSVD embeddings for nearest-neighbor search."""

    def __init__(self, dims: int = 128) -> None:
        self.dims = dims
        self._svd: TruncatedSVD | None = None
        self._embeddings: np.ndarray | None = None
        self._term_vectors: np.ndarray | None = None
        self._vocab: list[str] = []
        self._anime_ids: list[int] = []
        self._ready = False

    def fit(self, db: Session) -> None:
        recommender.ensure_fit(db)
        if not recommender._ready or recommender._matrix is None:
            self._ready = False
            return

        n_features = recommender._matrix.shape[1]
        n_components = min(self.dims, max(2, n_features - 1), recommender._matrix.shape[0] - 1)
        if n_components < 2:
            self._ready = False
            return

        self._svd = TruncatedSVD(n_components=n_components, random_state=42)
        dense = self._svd.fit_transform(recommender._matrix)
        self._embeddings = normalize(dense)
        self._anime_ids = list(recommender._anime_ids)
        # Term vectors live in the same latent space, which gives us cheap
        # query expansion without shipping a language model.
        self._term_vectors = normalize(self._svd.components_.T)
        try:
            self._vocab = list(recommender._vectorizer.get_feature_names_out())
        except Exception:
            self._vocab = []
        self._ready = True

    def ensure_fit(self, db: Session) -> None:
        if not self._ready:
            self.fit(db)

    def expand_query(self, query: str, extra_terms: int = 4) -> tuple[str, list[str]]:
        """Turn 'cozy rain school' into something the catalog vocabulary knows."""
        words = [w.lower().strip(".,!?") for w in query.split() if w.strip()]
        parts = [query]
        added: list[str] = []

        for word in words:
            mapped = VIBE_LEXICON.get(word)
            if mapped:
                parts.append(mapped)
                added.extend(mapped.split())

        if (
            self._ready
            and self._term_vectors is not None
            and self._vocab
            and recommender._vectorizer is not None
            and extra_terms > 0
        ):
            try:
                q = recommender._vectorizer.transform([" ".join(parts)])
                if q.nnz:
                    q_dense = normalize(self._svd.transform(q))
                    sims = (self._term_vectors @ q_dense.T).ravel()
                    top = np.argsort(-sims)[: extra_terms * 3]
                    known = set(words) | set(added)
                    for idx in top:
                        term = self._vocab[idx]
                        if " " in term or term in known or len(term) < 4:
                            continue
                        added.append(term)
                        known.add(term)
                        if len(added) >= extra_terms + len(words):
                            break
            except Exception:
                pass

        expanded = " ".join(parts + added).strip()
        return expanded, added

    def semantic_search(
        self, db: Session, query: str, limit: int = 24, *, expand: bool = True
    ) -> list[Anime]:
        self.ensure_fit(db)
        if not self._ready or not query.strip() or recommender._vectorizer is None:
            return recommender.search(db, query, limit=limit)

        effective = query
        if expand:
            effective, _ = self.expand_query(query)

        q = recommender._vectorizer.transform([effective])
        q_dense = normalize(self._svd.transform(q))
        scores = (self._embeddings @ q_dense.T).ravel()
        top = np.argsort(-scores)[: limit * 3]
        allow_adult = recommender.wants_adult(query)
        ids = [
            self._anime_ids[i]
            for i in top
            if scores[i] > 0 and (allow_adult or self._anime_ids[i] not in recommender._adult_ids)
        ]
        if not ids:
            return recommender.search(db, query, limit=limit)
        by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
        return [by_id[i] for i in ids if i in by_id]

    def stats(self) -> dict:
        return {
            "ready": self._ready,
            "dimensions": int(self._embeddings.shape[1]) if self._embeddings is not None else 0,
            "vectors": int(self._embeddings.shape[0]) if self._embeddings is not None else 0,
            "vocabulary": len(self._vocab),
        }


embedding_index = EmbeddingIndex()
