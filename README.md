# Kura — Local Anime Vault

<p align="center">
  <img src="docs/brand/logo.png" alt="Kura logo" width="128" />
</p>

<p align="center">
  <img src="docs/brand/hero.png" alt="Kura hero" width="100%" />
</p>

**Kura** is a local-first anime recommendation vault. Run it on your machine, browse a large catalog, rate what you watch, and get hybrid personalized picks — no cloud account required beyond your own Docker stack.

**Repo:** https://github.com/ayushreg/anime-recommendation-platform

---

## Does this work out of the box?

**Yes.** You do **not** need to upload CSVs, buy API keys, or type in anime titles by hand.

On first `docker compose up --build`, the API container automatically runs the seed script, which:

1. **Downloads ~12,000 real titles** from the public [Manami anime-offline-database](https://github.com/manami-project/anime-offline-database) on GitHub (titles, tags, images when available).
2. **If that download fails** (offline, rate limit, etc.), **generates ~12,000 synthetic titles** and still injects **25 well-known demos** (One Piece, Naruto, Attack on Titan, …) so search stays intuitive.
3. Creates a **demo account** with sample ratings so “For You” works immediately.

First boot can take several minutes. Later boots reuse the seeded Postgres volume.

| Requirement | Notes |
|-------------|--------|
| Docker Desktop running | Required for the one-command path |
| Internet on first seed | Recommended for real Manami titles; optional if you accept synthetic + demo titles |
| Manual data entry | **Not required** |

Demo login after boot:

- Email: `demo@anime.app`
- Password: `demo1234`

---

## Quick start

```bash
docker compose up --build
```

| URL | What |
|-----|------|
| http://localhost:3000 | Kura web app |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/metrics | Prometheus metrics |
| http://localhost:8000/api/health | Dependency health check |

Stop with `Ctrl+C` or `docker compose down`. Reset the database with `docker compose down -v` for a clean re-seed.

---

## What you can do in the app

Local-first app shell (not a marketing landing page):

- **Discover** — command search with autocomplete, hybrid / lexical / semantic modes, genre chips, type filters, recently opened titles
- **For You** — hybrid personalized recommendations (content + collaborative)
- **Shelf** — watch-later queue (add / remove)
- **Library** — your ratings, sortable
- **Title pages** — synopsis, full 1–10 rating dial, similar titles, shelf toggle

Press `/` anywhere to focus search.

---

## Ranking engine

1. **Lexical / TF-IDF search** — match query text to titles, genres, themes, synopsis (with multi-token SQL fallback)
2. **Semantic search** — TruncatedSVD dense vectors (`mode=semantic`)
3. **Hybrid personalized recommendations** — content similarity + collaborative filtering from user ratings

Also includes JWT auth, Redis caching, API rate limiting, and a background model refit worker.

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, React Router, nginx |
| API | FastAPI, Uvicorn, Pydantic, JWT (python-jose), Passlib/bcrypt |
| ML / ranking | scikit-learn TF-IDF, cosine similarity, collaborative filtering, TruncatedSVD embeddings |
| Data | PostgreSQL 16, SQLAlchemy 2, Alembic |
| Catalog seed | Manami offline DB (primary) + synthetic generator + famous-title backfill |
| Cache / limits | Redis 7 |
| Observability | Prometheus metrics (`/metrics`), structured health checks |
| Infra | Docker Compose, GitHub Actions CI |

Brand assets live in [`docs/brand/`](docs/brand/) (logo, hero, icon sheet).

---

## API highlights

- `GET /api/anime/search?q=&mode=hybrid|semantic|lexical`
- `GET /api/anime/suggest?q=` — autocomplete
- `GET /api/anime/genres` · `GET /api/anime/browse?genre=&type=&year=`
- `GET /api/recommendations` (JWT)
- `POST /api/ratings` · `GET /api/ratings/me` (JWT)
- `POST|DELETE /api/watchlist/{id}` · `GET /api/watchlist` (JWT)
- `GET /api/anime/{id}/similar`
- `GET /api/health` · `GET /api/stats` · `GET /metrics`

---

## Local development (without full Compose UI)

```bash
docker compose up db redis -d
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg://anime:anime@localhost:5432/anime_recs
set REDIS_URL=redis://localhost:6379/0
python -m app.seed
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

```bash
cd backend && pytest -q
```

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for request path, caching keys, ranking methods, and service roles.
