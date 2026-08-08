# Architecture

## Request path

```
Browser (React SPA via nginx, service worker for the offline shell)
   │  JWT on protected routes
   │  heartbeats every 15s while a session is running
   │  impression beacons batched every 4s or 40 events
   ▼
FastAPI  ── Redis (response cache, rate limits, cache hit counters)
   │
   ├─ PostgreSQL
   ├─ HybridRecommender (TF-IDF matrix, collaborative neighbours, MMR)
   ├─ EmbeddingIndex (TruncatedSVD document and term vectors)
   └─ events.jsonl (+ optional KURA_WEBHOOK_URL)
```

## Data model

| Table | Holds |
|-------|-------|
| `anime` | Catalog, plus `season`, `duration_minutes`, `franchise_key`, `catalog_source` |
| `users` | Accounts, plus a short `friend_code` |
| `ratings` | Scores with `created_at` and `updated_at` for time decay |
| `watchlist` | Status, progress, `watch_seconds`, `rewatches`, `is_rewatching`, `completed_at` |
| `user_preferences` | Diversity, ranking variant, runtimes, idle cutoff, toggles, quiz weights |
| `watch_sessions` | One focused stretch: device, active seconds, ticks, carry seconds |
| `watch_days` | Daily rollup powering the streak heatmap without scanning sessions |
| `impressions` | Poster view, hover, click, dismiss with dwell and grid position |
| `title_feedback` | Not interested, with the reason given |
| `collections`, `collection_items` | Custom shelves |
| `notes` | Private by default, optional share flag |
| `episode_markers` | User editable intro and outro timestamps |
| `friendships`, `activity_events` | Local social graph and feed |
| `airing_entries` | One row per title with a clock on it: status, next episode + exact UTC instant, start and end dates, source popularity, `refreshed_at` |
| `linked_accounts` | A username on another tracker, per provider, plus the outcome of the last sync. No secrets: read-only by construction |
| `search_queries` | Aggregated counter for the operator dashboard |

New columns land in `app/migrate.py`, which is idempotent and runs on every boot
against Postgres (Docker) and SQLite (tests). `create_all` handles new tables;
it never alters an existing one, which is the whole reason that module exists.

## Ranking methods

| Method | When used | Signal |
|--------|-----------|--------|
| Popularity | Cold start, and the control variant | score, then scored_by, then MAL id |
| Content (TF-IDF) | Search, similar, hybrid recs | title, genres, themes, studios, synopsis |
| Collaborative | Hybrid recs | Pearson neighbours, weighted by overlap size |
| Semantic (SVD) | `mode=semantic` | dense projection, plus expanded query terms |
| Sequence | `/api/insights/next-up` | bigram over completion order across accounts |
| Attention rerank | `/api/discover/rail` | tag affinity, tag novelty, dismissals, render fatigue |

### Time decay

Ratings are weighted by `0.5 ** (age_days / 120)`. Something rated last week
drives the page; something rated two years ago barely nudges it.

### Diversity

After scoring, candidates go through maximal marginal relevance against the
already-picked set. The slider is the lambda: 0 is pure relevance, 1 is pure
novelty. Before that, one entry per franchise, matched on a prefix so
`gantz` and `gantz stage` count as the same thing.

### Safety

Adult-tagged rows are excluded from browse, rails, and recommendations. The id
set is built once during `fit()` rather than re-queried per request. A query
that names an adult tag explicitly is still allowed to find it.

## Watch telemetry

The client owns the clock. A second counts only when the tab is visible, the
window has focus, and there has been input within the idle cutoff. Every fifteen
seconds it posts the count.

The server adds those seconds to the session and to `watchlist.watch_seconds`,
carries the remainder in `carry_seconds`, and once the carry passes one episode
of runtime it advances progress and subtracts. Runtime comes from
`anime.duration_minutes`, falling back to the per-type value in preferences.

A second live session for the same title on a different device sets `conflict`
on the response so the interface can say so. Resolution is last write wins.

## Live data (opt-in)

`app/services/live.py` is the only module in the codebase that opens a socket to
the internet, and it is gated behind the `live_data` flag, which ships off.

```
AniList GraphQL ─┐
                 ├─ services/live.py ─ normalize ─ services/ingest.py ─ Postgres
Jikan (MAL) ─────┘   (raises LiveUnavailable,      (fills blanks only)      │
                      never leaks httpx errors)                    routers/live.py
                                                                    (reads Postgres)
```

- **Fetch and read are separate.** `POST /api/live/refresh` writes; the grids only
  ever query Postgres. Once a refresh lands, every view works offline, and the
  response carries `refreshed_at` plus a `stale` flag past 24 hours rather than
  presenting an old copy as current.
- **Ingest fills blanks, never overwrites.** `services/ingest.FILLABLE` lists the
  columns a refresh may touch, and only when the existing value is empty. The
  ranking columns (`score`, `scored_by`, `popularity`) are not on that list, so a
  nightly job cannot quietly undo the ordering work. Titles new to the catalog
  arrive with `catalog_source='live'` and a null score, which keeps anything
  unaired out of every `best_first()` query without a special case.
- **`idMal` is the join key.** Rows without one are dropped rather than matched on
  title text, which is what stops the refresh inventing duplicates.
- **Errors are UI copy.** `LiveUnavailable` carries a sentence written for a
  person, because the settings page prints it verbatim. AniList's own body text
  is preferred over its status code, so "User not found" and "Private User" stay
  distinguishable instead of collapsing into "404".
- Cache keys: `live:media:{status}:{limit}`, TTL `live_cache_ttl_seconds` (6h).
  Dates are serialised on the way into Redis and revived on the way out.

## Caching

- Keys: `search:v3:{q}:{limit}`, `recs:user:{id}:v4:{...}`, `similar:{id}:{limit}`
- The version segment sits inside the delete pattern, so a ranking change
  invalidates every cached page without a Redis flush
- Invalidation: rating writes, dismissals, and preference changes delete `recs:user:{id}:*`
- Hit and miss counters live in Redis so every worker shares one tally
- Rate limit keys: `rl:{ip}:{window}`

## Services (Compose)

| Service | Role |
|---------|------|
| `db` | PostgreSQL 16 |
| `redis` | Cache, rate limits, cache stats |
| `api` | Seed, migrate, FastAPI |
| `worker` | Periodic TF-IDF and SVD refit; live refresh and account re-sync on a longer interval when `live_data` is on |
| `frontend` | Static React build behind nginx |

## Feature flags

`app/feature_flags.json` ships the defaults. The operator dashboard writes
overrides to `feature_flags.local.json`, and `KURA_FLAGS=social=off,...` beats
both. `GET /api/flags` is public so the interface can hide switched-off surfaces
instead of rendering a dead link.

## Observability

- `/api/health`: postgres, redis, embedding readiness, cache hit rate, flags
- `/metrics`: default FastAPI series plus:
  - `kura_watch_seconds_total{source}`
  - `kura_episodes_ticked_total{mode}`
  - `kura_impressions_total{surface,kind}`
  - `kura_ranking_requests_total{variant,cached}`
  - `kura_ranking_seconds` (histogram)
  - `kura_cache_events_total{result}`
  - `kura_active_watch_sessions` (gauge)
- `data/events.jsonl`: one JSON object per line for your own automation, plus
  an optional POST to `KURA_WEBHOOK_URL`

## Tests

- `backend/tests`: pure logic, no database or network. Franchise keys, adult
  detection, episode length, rating decay, attention scoring, rerank behaviour,
  quiz scoring, tag normalization, and a check that every router is mounted.
- `frontend/e2e`: Playwright against a running stack. Login, search, +1 episode,
  rate, watch session, command palette, not interested, and a pass over all
  twelve pages asserting no console errors.
