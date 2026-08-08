# Kura: Local Anime Vault

<p align="center">
  <img src="docs/brand/logo.png" alt="Kura logo" width="120" />
</p>

<p align="center">
  <b>A local-first anime discovery and tracking app I built from scratch.</b><br/>
  Watch-time telemetry from your own tab, attention-aware ranking, hybrid recommendations, Docker one-command boot
</p>

<p align="center">
  <img src="docs/brand/mascot.png" alt="Kura mascot" width="200" />
</p>

**Author:** [Ayush Regmi](https://github.com/ayushreg) · **Repo:** [ayushreg/anime-recommendation-platform](https://github.com/ayushreg/anime-recommendation-platform)

I got tired of cloud-only anime lists that want an account before they'll even show me a poster. **Kura** (vault) is my answer: a full-stack recommendation system you run on your own machine. Seed about 12k titles with cover art, rate what you finish, and let a hybrid engine suggest what to watch next.

The v2 push added the part I actually wanted: **Kura now notices what you do.** Start a session timer while you watch on your own setup and your episode counter moves on its own. Scroll past the same poster ten times and it sinks. Linger on one and it comes back tomorrow in a rail called "you almost clicked these." All of that runs on signals this instance already owns. Nothing streams, nothing scrapes, nothing leaves the box.

---

## Screenshots

### Discover: attention-ranked poster vault
<img src="docs/screenshots/01-discover.png" alt="Kura Discover page with poster grid and diversity slider" width="100%" />

### Watching: the session timer counting real attention
<img src="docs/screenshots/04-watching.png" alt="Kura watching page with a live watch session timer" width="100%" />

### Insights: streaks, vault health, taste DNA
<img src="docs/screenshots/07-insights.png" alt="Kura insights page with heatmap and taste radar" width="100%" />

### For You: hybrid picks that explain themselves
<img src="docs/screenshots/03-for-you.png" alt="Kura For You recommendations with explanation cards" width="100%" />

### Title detail: track, note, rate, mark the intro
<img src="docs/screenshots/05-detail.png" alt="Kura anime detail page" width="100%" />

### Seasons, lists, friends, instance
<p align="center">
  <img src="docs/screenshots/09-seasons.png" alt="Kura season calendar" width="49%" />
  <img src="docs/screenshots/08-collections.png" alt="Kura collections" width="49%" />
</p>
<p align="center">
  <img src="docs/screenshots/10-social.png" alt="Kura friends page" width="49%" />
  <img src="docs/screenshots/11-admin.png" alt="Kura operator dashboard" width="49%" />
</p>

---

## Why I built this

I wanted a project that touched **real product surfaces** (search, personalization, tracking, telemetry) and **real infra** (Postgres, Redis, Docker, background workers, metrics), not just a toy notebook model.

Goals I set for myself:

1. One command should bring the whole stack up with real data and posters
2. Recommendations should be explainable, not a black box that says "trust me"
3. Tracking should feel automatic without me pretending to be a streaming site
4. The interface should feel like a late-night catalog site, not a CRUD admin

---

## The watch timer, and why it works this way

This was the hard design problem. "Automatically track what I watch" usually means one of two things, and both were off the table: hook into a streaming service (not mine to hook into) or scrape a pirate site (not happening).

So the browser does the counting, and it is honest about it:

- A second counts only when the tab is **visible**, the window has **focus**, and you have moved a mouse, key, or finger in the last few minutes
- Every fifteen seconds the tab posts how many of those seconds were real
- Once a session banks one episode of runtime, your counter moves and the dial resets
- The HUD says out loud when it stopped counting and why: *paused: window is not focused*
- Runtime comes from the catalog per title, with a per-type fallback you can edit in settings
- If a second device is beating for the same title, you get told, and last write wins

Turn auto tick off and it asks instead: *looks like you finished episode 7, mark it?*

A companion CLI reads a folder of files you already own, fuzzy-matches filenames against the catalog, and offers progress updates one at a time. It reads names and modification times. It never opens a media file and never contacts a tracker.

```bash
docker compose exec api python -m app.tools.folder_watch --path /media/anime --dry-run
```

---

## Attention signals, and where they actually land

Poster renders, hovers, clicks, and dwell get batched in the browser and posted in one beacon. A tile has to hold still on screen for most of a second before it counts, so flicking through a grid logs nothing.

Those rows feed one surface you can watch change in real time, the **Discover rail**:

- **Exploit**: titles whose tags match what you rate and finish move up
- **Explore**: tags you have barely touched get a bonus, scaled by the diversity slider
- **Fatigue**: a poster you keep scrolling past gets discounted, up to a hard floor
- **Dismissals**: "not interested" with a reason both hides the title and dampens its tags

Each card says which of those decided its position: *matches your Action streak*, *something new for you: Sports*, *dampened, you have scrolled past this a lot*.

---

## Features

| Area | What it does |
|------|----------------|
| **Watch timer** | Visibility, focus, and idle aware session timer; auto episode tick; multi device conflict notice; rewatch mode that keeps the original finish date; editable intro and outro markers |
| **Discover** | Attention-ranked rail with explore/exploit and a diversity slider, hybrid / lexical / semantic search, vibe query expansion, smart filters, surprise me |
| **For You** | Time-decayed hybrid ranking, four switchable variants, explanation cards naming the seed title, sequence model over completion order, signal metrics panel |
| **Insights** | Streak calendar heatmap, vault health with backlog hours and abandonment rate, taste DNA radar, attention scores, people who rate like you |
| **Lists** | Custom collections beside the status buckets, private notes per title |
| **Seasons** | Year and season calendar built from offline catalog fields, works with no network |
| **Friends** | Friend codes, follows, activity feed, opt-in weekly hours leaderboard, recommend to a friend |
| **Your data** | JSON export and restore, MyAnimeList XML import, optional AniList import, unhide list |
| **Interface** | Command palette on Ctrl+K, keyboard mode, poster colour tinting, reactive mascot, synthesised sounds, PWA with an offline shell, mobile bottom nav |
| **Ops** | Operator dashboard, runtime feature flags, JSONL event log plus local webhook, Prometheus series, JWT auth, Redis cache and rate limits |

Full prioritized backlog, including what I deliberately skipped and why: [`docs/BACKLOG.md`](docs/BACKLOG.md)

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

First boot downloads the [Manami offline database](https://github.com/manami-project/anime-offline-database) from **GitHub Releases** (about 12k titles plus posters), then generates local demo telemetry so every screen has something on it: watch days, sessions, impressions, collections, follows. Later boots reuse the Postgres volume.

```bash
# rebuild only the demo telemetry, leaving the catalog alone
docker compose exec api python -m app.seed --reseed-signals

# force a poster-rich reseed if you ever landed on synthetic-only data
docker compose exec api python -m app.seed --reseed-images
```

Stop with `Ctrl+C` or `docker compose down`. Wipe data with `docker compose down -v`.

---

## Architecture

```
Browser (React 19 / Vite / nginx)
   │  heartbeats, impression beacons, /api/*
   ▼
FastAPI ── Redis (cache, rate limits, hit-rate counters)
   │
PostgreSQL (catalog, accounts, ratings, library,
            sessions, watch days, impressions,
            feedback, collections, notes, activity)
   │
Worker process (periodic TF-IDF and SVD refit)
   │
data/events.jsonl (+ optional local webhook)
```

Ranking paths:

1. **Lexical / TF-IDF**: cosine over title, genres, themes, synopsis, with a multi-token SQL fallback that always wins ties
2. **Semantic**: TruncatedSVD dense vectors, with query expansion from a vibe lexicon and nearest latent terms
3. **Hybrid For You**: time-decayed content neighbours blended with correlated accounts, then franchise-deduped and diversified by maximal marginal relevance
4. **Discover rail**: catalog score reweighted by tag affinity, tag novelty, dismissal penalties, and render fatigue

Deeper notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 19, Vite, React Router, nginx, service worker |
| API | FastAPI, Uvicorn, Pydantic v2, JWT, Passlib/bcrypt |
| ML | scikit-learn TF-IDF, cosine similarity, collaborative filtering, TruncatedSVD, MMR diversification |
| Data | PostgreSQL 16, SQLAlchemy 2, startup migrator |
| Catalog | Manami Releases dump plus famous-title backfill |
| Cache | Redis 7 |
| Tests | pytest, Playwright |
| Infra | Docker Compose, GitHub Actions CI, Prometheus |

Brand assets: [`docs/brand/`](docs/brand/) · UI captures: [`docs/screenshots/`](docs/screenshots/)

---

## API highlights

```
GET  /api/anime/search?q=&mode=hybrid|semantic|lexical
GET  /api/anime/browse?genre=&studio=&year_min=&min_score=&sort=
GET  /api/discover/rail?diversity=            attention-ranked
GET  /api/discover/almost                     what you nearly clicked
GET  /api/discover/smart?filter=one_sitting   time budget filters
GET  /api/discover/seasons                    season calendar
POST /api/watch/session                       start a timer
POST /api/watch/heartbeat                     bank real attention seconds
GET  /api/watch/streak                        heatmap and streak
GET  /api/watch/tonight?minutes=180           what actually closes tonight
POST /api/signals/impressions                 batched beacon
POST /api/signals/feedback                    not interested, with a reason
GET  /api/recommendations?variant=&diversity= explainable picks
GET  /api/insights/vault | /taste | /next-up | /similar-users
GET  /api/collections · /api/notes/{id} · /api/social/feed
GET  /api/vault/export · POST /api/vault/import/mal
GET  /api/admin/overview · POST /api/admin/flags
GET  /api/health · /api/stats · /metrics
```

---

## Local development

```bash
docker compose up db redis -d
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://anime:anime@localhost:5432/anime_recs
export REDIS_URL=redis://localhost:6379/0
python -m app.seed
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

```bash
cd backend && pytest -q
```

```bash
cd frontend && npm run test:e2e
```

The Playwright suite runs against whatever is already up. Point it at the dev server with `KURA_BASE_URL=http://localhost:5173`, or leave it alone to hit the Compose stack on port 3000. CI boots the whole stack and runs it there.

---

## Challenges I hit (and how I worked through them)

Building this wasn't a straight line. A few problems that ate real evenings:

1. **"Automatic tracking" almost pushed me somewhere I didn't want to go.**
   Every obvious implementation of "know what I watched" involves someone else's video. I sat with that for a while and ended up inverting it: the browser already knows whether you are present, so let *presence* be the signal. Visible plus focused plus not idle, counted a second at a time, posted every fifteen. It turned out to be more honest than a player integration would have been, because the HUD can tell you exactly why it stopped counting.

2. **The catalog had no scores, so "top of the vault" was random.**
   The Manami dump ships no ratings, which left about twelve thousand rows tied at NULL and the tiebreak landing wherever Postgres felt like. Every "best first" list was quietly garbage. The fix was accepting the honest signal I did have: MyAnimeList ids were handed out in registration order, so a low id means an older title that stuck around long enough to be catalogued early. Score first, then id. One shared ordering helper, and Discover went from obscure Korean kids' shows to Cowboy Bebop and FLCL.

3. **Content-based recommenders love sequels.**
   The nearest neighbour to *Gantz* is *Gantz 2nd Stage*, so the page filled with one franchise wearing different hats. Exact-match dedupe on a normalized franchise key was not enough, because stripping season words leaves `gantz` and `gantz stage`. Comparing on prefix caught it, and one entry per franchise turned the page from a search result back into a recommendation.

4. **The offline catalog contains adult titles.**
   The demo account's ratings happened to include a couple, and content similarity did what content similarity does. Kura is a shelf you might open in front of other people, so adult-tagged rows now stay out of every browse, rail, and recommendation unless the query itself asks for them. The tag list is built once at fit time rather than re-queried per request.

5. **My own test suite caught a real bug that I would have shipped.**
   A Playwright run bounced to the login page halfway through. The cause: `auth.jsx` cleared the stored token on *any* failed `/api/auth/me`, so one rate limit or one restarting container silently logged you out. Now only a 401 or 403 ends a session, everything else retries with backoff. That is exactly what a smoke suite is for.

6. **Hooks after an early return.**
   `Watching` gained a `useEffect` below its `if (loading) return`, which is fine until the guard flips and React counts a different number of hooks. Blank screen, and a stack trace that points at React rather than at me. Moving one effect above two guards fixed it. The console-error test now walks all twelve pages so the next one gets caught by a machine.

7. **Little landmines.**
   Genre chips were rendering raw catalog tags alphabetically, so the filter row read "abstract, adult audience only, aliens, angst" instead of anything a person would browse by. And an impression only fired when a tile *left* the viewport, which meant the poster you stared at for thirty seconds without scrolling logged nothing at all. Both were a handful of lines and both made the product look broken.

---

## What's next (if I keep iterating)

- LAN watch parties with synced episode ticks
- Browser push reminders for continue-watching
- Grafana dashboard JSON to go with the exported Prometheus series

---

## License / credit

Catalog metadata sourced from the community [Manami anime-offline-database](https://github.com/manami-project/anime-offline-database) (ODbL). Cover images are loaded from provider CDNs referenced by that dataset and by MAL ids. Kura does not host, stream, or link to video.

Built by **Ayush Regmi** ([github.com/ayushreg](https://github.com/ayushreg))
