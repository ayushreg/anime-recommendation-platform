# Kura: Local Anime Vault

<p align="center">
  <img src="docs/brand/logo.png" alt="Kura logo" width="120" />
</p>

<p align="center">
  <b>A local-first anime discovery and tracking app I built from scratch.</b><br/>
  Hybrid recommendations, episode progress, dense poster catalog, Docker one-command boot
</p>

<p align="center">
  <img src="docs/brand/mascot.png" alt="Kura mascot" width="200" />
</p>

**Author:** [Ayush Regmi](https://github.com/ayushreg) · **Repo:** [ayushreg/anime-recommendation-platform](https://github.com/ayushreg/anime-recommendation-platform)

I got tired of cloud-only anime lists that want an account before they'll even show me a poster. **Kura** (vault) is my answer: a full-stack recommendation system you run on your own machine. Seed about 12k titles with cover art, rate what you finish, track what you're mid-season on, and let a hybrid engine (content + collaborative filtering) suggest what to watch next.

---

## Screenshots

### Discover: dense poster vault
<img src="docs/screenshots/01-discover.png" alt="Kura Discover page with poster grid" width="100%" />

### Login: neon vault door
<img src="docs/screenshots/02-login.png" alt="Kura login page with mascot" width="100%" />

### For You: hybrid personalized picks
<img src="docs/screenshots/03-for-you.png" alt="Kura For You recommendations" width="100%" />

### Watching: continue where you left off
<img src="docs/screenshots/04-watching.png" alt="Kura currently watching page" width="100%" />

### Title detail: rate, track, similar shows
<img src="docs/screenshots/05-detail.png" alt="Kura anime detail page" width="100%" />

### Shelf: statuses for your whole list
<img src="docs/screenshots/06-shelf.png" alt="Kura shelf with status filters" width="100%" />

---

## Why I built this

I wanted a project that touched **real product surfaces** (search, personalization, tracking) and **real infra** (Postgres, Redis, Docker, background workers), not just a toy notebook model.

Goals I set for myself:

1. One command should bring the whole stack up with real data and posters
2. Recommendations should be explainable (content vs collaborative vs hybrid)
3. Tracking should feel automatic: rate a show and it completes; +1 an episode and progress moves
4. The UI should feel like a late-night catalog site, not a generic CRUD admin

---

## Features

| Area | What it does |
|------|----------------|
| **Discover** | Hybrid / lexical / semantic search, autocomplete, genre + type filters, recently opened |
| **Continue watching** | Home-row of in-progress titles with progress bars |
| **Watching** | Dedicated currently-watching queue with **+1 episode** |
| **Shelf** | Plan / watching / completed / on hold / dropped |
| **Library** | Your ratings, sortable |
| **For You** | Hybrid recs (TF-IDF content ~65% + collaborative ~35%), Redis-cached |
| **Auto-tracking** | Rating marks completed; finishing the last episode via +1 marks completed |
| **Ops** | JWT auth, Redis rate limits, Prometheus `/metrics`, health checks, model refit worker |

Demo login after boot: `demo@anime.app` / `demo1234`

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
| http://localhost:8000/api/health | Dependency health |

First boot downloads the [Manami offline database](https://github.com/manami-project/anime-offline-database) from **GitHub Releases** (about 12k titles + posters). Later boots reuse the Postgres volume.

Force a poster-rich reseed if you ever landed on synthetic-only data:

```bash
docker compose exec api python -m app.seed --reseed-images
```

Stop with `Ctrl+C` or `docker compose down`. Wipe data with `docker compose down -v`.

---

## Architecture (short version)

```
Browser (React/Vite/nginx)
        │  /api/*
        ▼
   FastAPI  ── Redis (cache + rate limit)
        │
   PostgreSQL (anime, users, ratings, library/watchlist)
        │
   Worker process (periodic TF-IDF + SVD refit)
```

Ranking paths:

1. **Lexical / TF-IDF**: cosine over title, genres, themes, synopsis (plus multi-token SQL fallback)
2. **Semantic**: TruncatedSVD dense vectors (`mode=semantic`)
3. **Hybrid For You**: blend content neighbors with users who rated like you

Deeper notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 19, Vite, React Router, nginx |
| API | FastAPI, Uvicorn, Pydantic, JWT, Passlib/bcrypt |
| ML | scikit-learn TF-IDF, cosine similarity, collaborative filtering, TruncatedSVD |
| Data | PostgreSQL 16, SQLAlchemy 2 |
| Catalog | Manami Releases dump + famous-title backfill |
| Cache | Redis 7 |
| Infra | Docker Compose, GitHub Actions CI |

Brand assets: [`docs/brand/`](docs/brand/) · UI captures: [`docs/screenshots/`](docs/screenshots/)

---

## API highlights

```
GET  /api/anime/search?q=&mode=hybrid|semantic|lexical
GET  /api/anime/suggest?q=
GET  /api/anime/genres
GET  /api/anime/browse?genre=&type=&year=
GET  /api/recommendations                 (JWT)
POST /api/ratings                         (JWT)  also marks completed
PUT  /api/library/{id}                    (JWT)  status + progress
POST /api/library/{id}/tick               (JWT)  +1 episode
GET  /api/library?status=watching         (JWT)
GET  /api/library/continue                (JWT)
GET  /api/anime/{id}/similar
GET  /api/health · /api/stats · /metrics
```

---

## Local development (API without Compose UI)

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

## Challenges I hit (and how I worked through them)

Building this wasn't a straight line. A few problems that ate real evenings:

1. **Manami "just works" until it doesn't.**  
   The old raw GitHub URL for the offline DB started 404'ing after the project moved datasets to **Releases**. Seed fell back to synthetic titles with **zero posters**, so search for "One Piece" returned empty while the empty-query browse still looked fine. Fix: point seed at the Releases download, add `--reseed-images`, and backfill famous titles with real MAL ids/images.

2. **TF-IDF lied politely.**  
   Weak cosine hits (`sims > 0`) were ranking random synthetic titles *above* exact lexical matches, so "one piece" could surface nonsense before the SQL fallback ever ran. Fix: always merge **lexical first**, then fill with TF-IDF above a real similarity threshold.

3. **In-memory models vs a growing catalog.**  
   After inserting demo titles into Postgres, the live API process still held an old fitted matrix. Search looked broken until refit. Fix: fit after seed/reseed, and make search prefer durable SQL lexical hits so a stale matrix can't hide real titles.

4. **Watchlist wasn't enough.**  
   "Add to shelf" doesn't answer "what episode am I on?" Extending the table with `status` / `progress` on a live Postgres volume meant `create_all` alone wouldn't alter columns, so I added a small startup migrator that is careful on SQLite (tests) vs Postgres (Docker).

5. **Making the UI feel alive without shipping piracy.**  
   I studied the *layout energy* of dense anime catalog sites (poster grids, neon accents, continue-watching rows) and rebuilt Kura as a **legal local vault** with Manami/MAL-sourced metadata and covers. Same vibe, clean data story.

6. **Little landmines.**  
   A missing `TYPES` constant blanked Discover after a refactor. `useEffectEvent` wasn't safe on the React version I pinned, so I ripped it out. Both were "one line" bugs that looked like total black screens until the console told the truth.

---

## What's next (if I keep iterating)

- Import from MyAnimeList XML / AniList for your existing scores  
- Smarter "next episode" reminders from progress + airing status  
- Offline-friendly poster cache so covers survive CDN hiccups  

---

## License / credit

Catalog metadata sourced from the community [Manami anime-offline-database](https://github.com/manami-project/anime-offline-database) (ODbL). Cover images are loaded from provider CDNs referenced by that dataset / MAL ids.

Built by **Ayush Regmi** ([github.com/ayushreg](https://github.com/ayushreg))
