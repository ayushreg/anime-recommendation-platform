# Anime Recommendation Platform

Full-stack hybrid recommendation system that helps people find what anime to watch next across a large catalog.

**Repo:** https://github.com/ayushreg/anime-recommendation-platform

---

## Does this work out of the box?

**Yes.** You do **not** need to upload CSVs, buy API keys, or type in anime titles by hand.

On first `docker compose up --build`, the API container automatically runs the seed script, which:

1. **Downloads ~12,000 real titles** from the public [Manami anime-offline-database](https://github.com/manami-project/anime-offline-database) on GitHub (titles, tags, images when available).
2. **If that download fails** (offline, rate limit, etc.), **generates ~12,000 synthetic titles** so search, recommendations, and the UI still work.
3. Creates a **demo account** with sample ratings so “For You” works immediately.

First boot can take several minutes (download + database insert + fitting the ML indexes). Later boots reuse the seeded Postgres volume.

| Requirement | Notes |
|-------------|--------|
| Docker Desktop running | Required for the one-command path |
| Internet on first seed | Recommended for real Manami titles; optional if you accept synthetic fallback |
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
| http://localhost:3000 | Web app |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/metrics | Prometheus metrics |
| http://localhost:8000/api/health | Dependency health check |

Stop with `Ctrl+C` or `docker compose down`. Reset the database volume with `docker compose down -v` if you want a clean re-seed.

---

## What the product does

Helps viewers discover anime using three ranking modes:

1. **Lexical / TF-IDF search** — match query text to titles, genres, themes, synopsis  
2. **Semantic search** — TruncatedSVD dense vectors over TF-IDF (`mode=semantic`)  
3. **Hybrid personalized recommendations** — content similarity + collaborative filtering from user ratings  

Also includes JWT auth, ratings, watchlist, similar-title pages, Redis caching, and API rate limiting.

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, React Router, nginx |
| API | FastAPI, Uvicorn, Pydantic, JWT (python-jose), Passlib/bcrypt |
| ML / ranking | scikit-learn TF-IDF, cosine similarity, collaborative filtering, TruncatedSVD embeddings |
| Data | PostgreSQL 16, SQLAlchemy 2, Alembic |
| Catalog seed | Manami offline DB (primary) + synthetic generator (fallback) |
| Cache / limits | Redis 7 (response cache + fixed-window rate limits) |
| Observability | Prometheus metrics (`/metrics`), structured health checks |
| Workers | Background refit worker (TF-IDF + embedding index) |
| Infra | Docker Compose, GitHub Actions CI |

---

## Data source (details)

| Source | When used | What you get |
|--------|-----------|--------------|
| **Manami anime-offline-database** (GitHub raw JSON) | Default on first seed with network | Large real-world catalog (~12k titles pulled into Postgres) |
| **Synthetic generator** | Automatic fallback if Manami download fails | Fake but structured titles/genres so ML + UI still demo cleanly |
| **Demo users + ratings** | Always on first seed | `demo` / `alice` / `bob` accounts with overlapping ratings for collaborative filtering demos |

Seed entrypoint: `backend/app/seed.py` (also invoked from the `api` service command in `docker-compose.yml`).

You can re-run seeding manually:

```bash
docker compose exec api python -m app.seed
```

---

## API highlights

- `GET /api/anime/search?q=&mode=hybrid|semantic|lexical`
- `GET /api/recommendations` (JWT)
- `POST /api/ratings` (JWT)
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
