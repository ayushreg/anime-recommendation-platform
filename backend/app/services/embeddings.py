from __future__ import annotations

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from sqlalchemy.orm import Session

from app.models import Anime
from app.services.recommender import recommender


class EmbeddingIndex:
    """Dense semantic index: TF-IDF -> TruncatedSVD embeddings for nearest-neighbor search."""

    def __init__(self, dims: int = 128) -> None:
        self.dims = dims
        self._svd: TruncatedSVD | None = None
        self._embeddings: np.ndarray | None = None
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
        self._ready = True

    def ensure_fit(self, db: Session) -> None:
        if not self._ready:
            self.fit(db)

    def semantic_search(self, db: Session, query: str, limit: int = 24) -> list[Anime]:
        self.ensure_fit(db)
        if not self._ready or not query.strip() or recommender._vectorizer is None:
            return recommender.search(db, query, limit=limit)

        q = recommender._vectorizer.transform([query])
        q_dense = normalize(self._svd.transform(q))
        scores = (self._embeddings @ q_dense.T).ravel()
        top = np.argsort(-scores)[:limit]
        ids = [self._anime_ids[i] for i in top if scores[i] > 0]
        if not ids:
            return recommender.search(db, query, limit=limit)
        by_id = {a.id: a for a in db.query(Anime).filter(Anime.id.in_(ids)).all()}
        return [by_id[i] for i in ids if i in by_id]

    def stats(self) -> dict:
        return {
            "ready": self._ready,
            "dimensions": int(self._embeddings.shape[1]) if self._embeddings is not None else 0,
            "vectors": int(self._embeddings.shape[0]) if self._embeddings is not None else 0,
        }


embedding_index = EmbeddingIndex()
