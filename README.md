<p align="center">
  <img src="docs/brand/logo.png" alt="Kura logo" width="110" />
</p>

<h1 align="center">Kura</h1>

<p align="center">
  <b>An anime tracker and recommendation engine you run yourself.</b><br/>
  Live airing countdowns, hybrid recommendations that explain themselves,<br/>
  and a watch timer that moves your episode counter without you touching it.
</p>

<p align="center">
  <a href="#quick-start"><b>Quick start</b></a> ·
  <a href="#bring-your-list-with-you">Import your list</a> ·
  <a href="#whats-inside">Features</a> ·
  <a href="#how-it-is-built">Architecture</a>
</p>

<p align="center">
  <img src="docs/brand/mascot.png" alt="Kura mascot" width="170" />
</p>

<p align="center">
  Built by <a href="https://github.com/ayushreg">Ayush Regmi</a>
</p>

---

I got tired of anime sites that want an account before they will show me a
poster, and of tracking apps where "what's airing tonight" and "what should I
watch next" live in two different tabs. **Kura** is one app that does both, runs
on your own machine, and keeps your list yours.

Point it at your MyAnimeList or AniList username and it pulls your whole
history in. From there it knows what you have finished, what you are mid-way
through, and which of the shows airing this week you actually care about.

---

## Quick start

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/).
Nothing else. No Python, no Node, no database to install.

```bash
git clone https://github.com/ayushreg/anime-recommendation-platform.git
cd anime-recommendation-platform
docker compose up
```

Then open **http://localhost:3000** and sign in with:

| | |
|---|---|
| **Email** | `demo@anime.app` |
| **Password** | `demo1234` |

That is the whole setup. There is no `.env` to write and no config to edit.

<details>
<summary>Prefer a script that checks things first?</summary>

```powershell
.\start.ps1     # Windows
```

```bash
./start.sh      # macOS and Linux
```

Same thing, but it tells you in one sentence if Docker is not running, and
prints the URL and login when it finishes.
</details>

**The first run takes a few minutes.** It downloads a catalog of about 12,000
titles with cover art, then generates some demo activity so every screen has
something on it. Later runs start in seconds. Watch it work with:

```bash
docker compose logs -f api
```

<details>
<summary>Something went wrong</summary>

| What you see | What to do |
|---|---|
| `port is already allocated` | Something else uses 3000 or 8000. Copy `.env.example` to `.env` and change `KURA_WEB_PORT` or `KURA_API_PORT`. |
| `Cannot connect to the Docker daemon` | Docker Desktop is installed but not started. Open it, wait for it to settle, try again. |
| Page loads but is empty | The catalog is still downloading. Check `docker compose logs -f api`. |
| You want a clean slate | `docker compose down -v` wipes the database, then `docker compose up` reseeds. |

</details>

Stop with `Ctrl+C`, or `docker compose down`.

---

## Bring your list with you

A fresh tracker is a boring tracker. Go to **Settings → Connected accounts**,
pick your service, type your username, and Kura reads your public list.

<p align="center">
  <img src="docs/screenshots/12-settings.png" alt="Connected accounts in Kura settings" width="100%" />
</p>

- **Nothing is written back.** Kura only ever reads. There is no password field
  on that page, no token, and no code path that can touch your account.
- **Titles it has never heard of get fetched.** The bundled catalog is a subset
  of every anime ever made, so a real list always names shows it is missing.
  Rather than skipping them, Kura looks those up by id and adds them. A 58 title
  list imports as 58 titles, not 33.
- **Unlinking keeps everything.** Your ratings and progress live here now.

Both services work with just a public username. If you would rather not go over
the network at all, the MyAnimeList XML export import is still there and reads
straight from the file.

---

## What is airing next

<p align="center">
  <img src="docs/screenshots/13-upcoming.png" alt="Kura Upcoming page with airing countdowns" width="100%" />
</p>

Three views, all built from live airing data:

| Tab | What it shows |
|-----|----------------|
| **Your radar** | Airing and announced titles that touch your shelf, each saying why: *on your shelf and airing now*, *new entry in a franchise you follow*, *matches your action, comedy streak* |
| **This week** | Every episode landing in the next seven days, in the order it lands |
| **Upcoming** | Announced but unaired, soonest first |

Countdowns are exact to the minute and computed on the server, so a laptop with
a wrong clock still shows the right number.

Under the hood a refresh writes into your own Postgres and every view reads from
that copy. Opening the page costs zero upstream requests, which is what keeps a
free public API happy.

---

## The watch timer

This was the hard design problem. "Automatically track what I watch" usually
means hooking into a streaming service or scraping a pirate site. Both were off
the table, so the browser does the counting instead, and it is honest about it:

- A second counts only when the tab is **visible**, the window has **focus**, and
  you have moved a mouse, key, or finger recently
- Every fifteen seconds the tab posts how many of those seconds were real
- Once a session banks one episode of runtime, your counter moves
- The HUD says out loud when it stopped counting and why: *paused: window is not
  focused*

<p align="center">
  <img src="docs/screenshots/04-watching.png" alt="Kura watching page with a live session timer" width="100%" />
</p>

Turn auto tick off and it asks instead: *looks like you finished episode 7, mark
it?*

A companion CLI reads a folder of files you already own, fuzzy-matches filenames
against the catalog, and offers progress updates one at a time. It reads names
and modification times, never opens a media file, and never contacts a tracker.

```bash
docker compose exec api python -m app.tools.folder_watch --path /media/anime --dry-run
```

---

## Recommendations that say why

<p align="center">
  <img src="docs/screenshots/03-for-you.png" alt="Kura For You recommendations with explanation cards" width="100%" />
</p>

Every card names the reason it is there. No black box, no "trust me".

The Discover rail reacts to what you actually do:

- **Exploit** — titles whose tags match what you rate and finish move up
- **Explore** — tags you have barely touched get a bonus, scaled by a slider
- **Fatigue** — a poster you keep scrolling past gets discounted
- **Dismissals** — "not interested" with a reason hides the title and dampens its tags

Poster renders, hovers, clicks, and dwell get batched in the browser and posted
in one beacon. A tile has to hold still on screen for most of a second before it
counts, so flicking through a grid logs nothing.

---

## What's inside

| Area | What it does |
|------|----------------|
| **Upcoming** | Live airing schedule, per-episode countdowns, next week's broadcasts, and a personalised radar |
| **Connected accounts** | Read-only MyAnimeList and AniList sync by username, with automatic backfill of missing titles |
| **Watch timer** | Visibility, focus, and idle aware session timer; auto episode tick; multi device conflict notice; rewatch mode; editable intro and outro markers |
| **Discover** | Attention-ranked rail with an explore/exploit slider, hybrid / lexical / semantic search, vibe query expansion, smart filters, surprise me |
| **For You** | Time-decayed hybrid ranking, four switchable variants, explanation cards naming the seed title, sequence model over completion order |
| **Insights** | Streak calendar heatmap, vault health with backlog hours and abandonment rate, taste DNA radar, people who rate like you |
| **Lists** | Custom collections beside the status buckets, private notes per title |
| **Seasons** | Year and season calendar across the whole catalog |
| **Friends** | Friend codes, follows, activity feed, opt-in weekly hours leaderboard |
| **Your data** | JSON export and restore, MyAnimeList XML import, unhide list |
| **Interface** | Command palette on Ctrl+K, keyboard mode, poster colour tinting, reactive mascot, PWA, mobile nav |
| **Ops** | Operator dashboard, runtime feature flags, JSONL event log, Prometheus series, JWT auth, Redis cache and rate limits |

<p align="center">
  <img src="docs/screenshots/01-discover.png" alt="Kura Discover page" width="49%" />
  <img src="docs/screenshots/07-insights.png" alt="Kura Insights page" width="49%" />
</p>
<p align="center">
  <img src="docs/screenshots/09-seasons.png" alt="Kura season calendar" width="49%" />
  <img src="docs/screenshots/11-admin.png" alt="Kura operator dashboard" width="49%" />
</p>

Full prioritized backlog, including what I deliberately skipped and why:
[`docs/BACKLOG.md`](docs/BACKLOG.md)

---

## How it is built

```
Browser (React 19 / Vite / nginx)
   │  heartbeats, impression beacons, /api/*
   ▼
FastAPI ── Redis (cache, rate limits, hit-rate counters)
   │
PostgreSQL (catalog, accounts, ratings, library, sessions,
            watch days, impressions, feedback, collections,
            notes, activity, airing entries, linked accounts)
   │
Worker process (periodic TF-IDF and SVD refit, live refresh)
   │
AniList / MyAnimeList ── read-only
```

Ranking paths:

1. **Lexical / TF-IDF** — cosine over title, genres, themes, synopsis, with a
   multi-token SQL fallback that always wins ties
2. **Semantic** — TruncatedSVD dense vectors, with query expansion from a vibe
   lexicon and nearest latent terms
3. **Hybrid For You** — time-decayed content neighbours blended with correlated
   accounts, then franchise-deduped and diversified by maximal marginal relevance
4. **Discover rail** — catalog score reweighted by tag affinity, tag novelty,
   dismissal penalties, and render fatigue

Deeper notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

### Stack

| Layer | Tech |
|-------|------|
| Frontend | React 19, Vite, React Router, nginx, service worker |
| API | FastAPI, Uvicorn, Pydantic v2, JWT, Passlib/bcrypt |
| ML | scikit-learn TF-IDF, cosine similarity, collaborative filtering, TruncatedSVD, MMR |
| Data | PostgreSQL 16, SQLAlchemy 2, startup migrator |
| Catalog | Manami offline database, plus live lookups by MAL id |
| Cache | Redis 7 |
| Tests | pytest, Playwright |
| Infra | Docker Compose, GitHub Actions CI, Prometheus |

### API highlights

```
GET  /api/anime/search?q=&mode=hybrid|semantic|lexical
GET  /api/discover/rail?diversity=            attention-ranked
GET  /api/live/schedule?days=7                episodes landing this week
GET  /api/live/upcoming · /api/live/radar     announced · what touches your shelf
POST /api/live/refresh                        pull airing data
GET  /api/connect/accounts                    linked list accounts
POST /api/connect/accounts/{provider}/sync
POST /api/watch/session · /api/watch/heartbeat
GET  /api/recommendations?variant=&diversity= explainable picks
GET  /api/insights/vault | /taste | /next-up | /similar-users
GET  /api/vault/export · POST /api/vault/import/mal
GET  /api/health · /api/stats · /metrics
```

| URL | What |
|-----|------|
| http://localhost:3000 | Web app |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/metrics | Prometheus metrics |

---

## Working on it

```bash
docker compose up db redis -d

cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://anime:anime@localhost:5432/anime_recs
export REDIS_URL=redis://localhost:6379/0
python -m app.seed
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

The API container mounts `./backend` and runs with `--reload`, so backend edits
apply without a rebuild.

```bash
cd backend && pytest -q                    # 47 tests
cd frontend && npm run test:e2e            # Playwright, against whatever is up
node e2e/screenshots.mjs                   # regenerate the images in this README
```

Feature flags live in `backend/app/feature_flags.json`, are overridable from the
operator dashboard, and `KURA_FLAGS=social=off,live_data=off` beats both.

---

## Problems worth writing down

Building this wasn't a straight line. A few that ate real evenings:

1. **The catalog had no scores, so "top of the vault" was random.**
   The Manami dump ships no ratings, which left about twelve thousand rows tied
   at NULL and the tiebreak landing wherever Postgres felt like. Every "best
   first" list was quietly garbage. The fix was accepting the honest signal I did
   have: MyAnimeList ids were handed out in registration order, so a low id means
   an older title that stuck around long enough to be catalogued early. Score
   first, then id. One shared ordering helper, and Discover went from obscure
   kids' shows to Cowboy Bebop and FLCL.

2. **Content-based recommenders love sequels.**
   The nearest neighbour to *Gantz* is *Gantz 2nd Stage*, so the page filled with
   one franchise wearing different hats. Exact-match dedupe on a normalized
   franchise key was not enough, because stripping season words leaves `gantz`
   and `gantz stage`. Comparing on prefix caught it, and one entry per franchise
   turned the page from a search result back into a recommendation.

3. **The obvious source for airing data was the broken one.**
   MyAnimeList is where the catalog's ids come from, so going to MAL for airing
   dates seemed automatic. It has no public read API without registering an app,
   and the usual way around that, Jikan, reads MAL by scraping it. Every Jikan
   endpoint I tried answered 504 *"failed to connect to MyAnimeList"*, twice,
   minutes apart. Worth noticing: a 504 from an upstream scrape and a 404 from a
   removed route mean opposite things, and only one of them means stop building.
   AniList turned out to be the better source anyway, because it returns a precise
   timestamp per episode and an `idMal` on every row, so live data joins onto the
   existing catalog by id instead of by fuzzy title.

4. **And the fix for MyAnimeList was to stop using a middleman.**
   Linking a MAL account still failed, because it was still going through Jikan.
   MyAnimeList serves its own list page from a plain JSON endpoint that needs no
   app registration and no token, just a browser-shaped request. Going straight
   there worked on the first try. The lesson was that "there is no public API"
   and "there is no public way to read this" are different claims, and I had
   accepted the first as if it were the second.

5. **Importing a list is not the same as matching a list.**
   The first successful MAL sync matched 33 of 58 titles, and the 25 it dropped
   were things like *A Silent Voice* and *Rent-a-Girlfriend*, which look exactly
   like a broken matcher. They were genuinely absent: the bundled catalog is a
   12k subset. Since the list already carries an id for every row, the missing
   ones are now fetched on the spot. 58 of 58.

6. **Every premiere date was off by one day.**
   The upcoming grid showed *Starts Dec 31, 2026* for a show listed as
   `2027-01-01`. `new Date("2027-01-01")` parses as UTC midnight, and rendering
   that west of Greenwich walks it back a day. Timestamps were fine, because
   those carry a real instant. A premiere date has no time attached and should be
   read as a calendar day, which is a different function, not a different format
   string.

7. **My own test suite caught a real bug I would have shipped.**
   A Playwright run bounced to the login page halfway through. The cause:
   `auth.jsx` cleared the stored token on *any* failed `/api/auth/me`, so one rate
   limit or one restarting container silently logged you out. Now only a 401 or
   403 ends a session. That is exactly what a smoke suite is for.

8. **Hooks after an early return.**
   `Watching` gained a `useEffect` below its `if (loading) return`, which is fine
   until the guard flips and React counts a different number of hooks. Blank
   screen, and a stack trace pointing at React rather than at me. The
   console-error test now walks every page so the next one gets caught by a
   machine.

9. **Test order decided which database the tests used.**
   Each test module called `os.environ.setdefault("DATABASE_URL", ...)` at import,
   so whichever file sorted first won, and in-memory SQLite hands every connection
   its own empty database. Any test that touched a real table failed with "no such
   table" depending on what else was running. Moved to one `conftest.py`.

---

## What's next

- LAN watch parties with synced episode ticks
- Browser push when a tracked show is an hour from airing, now that the airing
  table knows the exact minute
- Grafana dashboard JSON to go with the exported Prometheus series

---

## Credit

Catalog metadata from the community
[Manami anime-offline-database](https://github.com/manami-project/anime-offline-database)
(ODbL). Airing schedules from [AniList](https://anilist.co). Cover art is loaded
from provider CDNs. Kura does not host, stream, or link to video.

Built by **Ayush Regmi** · [github.com/ayushreg](https://github.com/ayushreg)
