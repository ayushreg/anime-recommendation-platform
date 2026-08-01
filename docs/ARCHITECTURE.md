# Architecture

## Request path

```
Browser (React SPA via nginx)
   │  JWT on protected routes
   ▼
FastAPI  ── Redis rate limit + response cache
   │
   ├─ PostgreSQL (users, anime, ratings, watchlist)
   ├─ HybridRecommender (TF-IDF matrix + collaborative neighbors)
   └─ EmbeddingIndex (TruncatedSVD dense vectors for semantic search)
```

## Ranking methods

| Method | When used | Signal |
|--------|-----------|--------|
| Popularity | Cold-start users | score / scored_by |
| Content (TF-IDF) | Search, similar, hybrid recs | title, genres, themes, synopsis |
| Collaborative | Hybrid recs | Pearson-correlated neighbor ratings |
| Semantic (SVD) | `mode=semantic` search | dense projection of TF-IDF |

## Caching

- Keys: `search:{q}:{limit}`, `recs:user:{id}:{limit}`, `similar:{id}:{limit}`
- Invalidation: rating writes delete `recs:user:{id}:*`
- Rate limit keys: `rl:{ip}:{window}`

## Services (Compose)

| Service | Role |
|---------|------|
| `db` | PostgreSQL |
| `redis` | Cache + rate limits |
| `api` | Seed + FastAPI |
| `worker` | Periodic model refit |
| `frontend` | Static React build behind nginx |

## Observability

- `/api/health`: postgres, redis, embedding readiness
- `/metrics`: Prometheus HTTP metrics via instrumentator
