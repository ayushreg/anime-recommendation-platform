# Kura backlog

The list I worked from for the v2 push. **Must** shipped first, **Should**
shipped where the vertical slice was clean, **Could** is what I deliberately
left on the shelf and why.

Status key: `done` shipped and browser tested, `later` still open.

---

## A. Watch and attention telemetry

Legal constraint I set before writing a line: no streaming, no scraping, no
touching anyone else's video. Every second in the database came from a tab open
on the user's own machine.

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| 1 | Visibility and focus aware watch session timer | Must | done |
| 2 | Heartbeat accumulation into `watch_seconds` | Must | done |
| 3 | Auto episode tick once a session banks one episode of runtime | Must | done |
| 4 | Idle classifier that stops the clock after N minutes of no input | Must | done |
| 5 | "Did you finish ep N?" prompt when auto tick is off | Must | done |
| 6 | Multi device session detection with last write wins | Should | done |
| 7 | Watch streak calendar and contribution heatmap | Must | done |
| 8 | Rewatch counter that preserves the original completion date | Should | done |
| 9 | User editable intro and outro markers | Should | done |
| 10 | Local folder matcher CLI for files you already own | Should | done |
| 11 | Per title runtime from the catalog, per type fallback in settings | Must | done |
| 12 | Public domain demo player to prove media time sync | Could | later. The timer already proves the sync and a player is a licensing rabbit hole with no product payoff |

## B. Impression and ranking signals

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| 13 | Batched impression beacon: render, hover, click, dwell | Must | done |
| 14 | Explore versus exploit ranking on the Discover rail | Must | done |
| 15 | Banner fatigue: repeated renders dampen a title | Must | done |
| 16 | Negative signals with reasons, and an unhide list | Must | done |
| 17 | Attention score per title from every signal we hold | Must | done |
| 18 | "You almost clicked these" recovery rail | Should | done |
| 19 | Ranking variants (hybrid, content, neighbours, popularity) as an A/B switch | Should | done |
| 20 | Signal metrics panel showing click through and dwell | Should | done |
| 21 | Cold start taste quiz that seeds tag weights | Must | done |
| 22 | Taste DNA radar from ratings and watch time | Must | done |
| 23 | Server side experiment assignment and holdout cohorts | Could | later. With one household on one instance there is no population to split |

## C. Social, local instance only

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| 24 | Friend codes and follow | Should | done |
| 25 | Activity feed across followed accounts | Should | done |
| 26 | Opt in weekly hours leaderboard | Should | done |
| 27 | Recommend a title to a friend, with an inbox | Should | done |
| 28 | Private notes per title with an optional share flag | Should | done |
| 29 | LAN watch parties with synced episode ticks | Could | later. Needs a websocket layer and a conflict model that earns its keep |

## D. Library power features

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| 30 | Custom collections beyond the status buckets | Must | done |
| 31 | Smart filters: finishable tonight, movies under 100m, currently airing, short, classics, hidden gems | Must | done |
| 32 | Time budget view: what actually closes in the hours I have | Must | done |
| 33 | Season and year calendar browse | Should | done |
| 34 | Franchise grouping so sequels and movies collapse | Should | done |
| 35 | Advanced browse filters: year range, studio, score, episode cap, sort | Should | done |
| 36 | MyAnimeList XML import | Should | done |
| 37 | AniList import by public username | Should | done |
| 38 | Vault export and restore as readable JSON | Must | done |
| 39 | Scheduled reminders and browser push | Could | later. Push needs a service worker subscription and a notification permission prompt I did not want on first run |

## E. Recommendation quality

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| 40 | Time decayed ratings, 120 day half life | Must | done |
| 41 | Explanation cards naming the seed title and shared tags | Must | done |
| 42 | Diversity slider driving maximal marginal relevance | Must | done |
| 43 | Franchise dedupe so one show cannot own the page | Must | done |
| 44 | Adult content filter across every browse surface | Must | done |
| 45 | Sequence model: bigram over completion order | Should | done |
| 46 | Semantic query expansion with a vibe lexicon plus latent term neighbours | Should | done |
| 47 | Similar users discovery with their top unshared picks | Should | done |
| 48 | Surprise me roulette with constraints | Should | done |
| 49 | Confidence weighting on neighbour correlation by overlap size | Should | done |
| 50 | Online incremental refit after every rating | Could | later. The worker refit plus cache invalidation already keeps picks fresh, and a true online update is a much bigger change than it looks |

## F. Interface

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| 51 | Command palette on Ctrl or Cmd + K | Must | done |
| 52 | Keyboard mode: j, k, Enter, e, r, x, and g prefixed navigation | Should | done |
| 53 | Poster colour extraction with a deterministic fallback | Should | done |
| 54 | Reactive mascot states | Should | done |
| 55 | Synthesised interface sounds, off by default | Could | done |
| 56 | PWA install, offline shell, poster cache | Should | done |
| 57 | Mobile bottom navigation | Should | done |
| 58 | Accessibility: skip link, labelled controls, focus rings, reduced motion | Must | done |
| 59 | Swipe gestures between statuses | Could | later. The bottom bar covers the same ground without a gesture layer to maintain |

## G. Platform and operations

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| 60 | Operator dashboard: catalog, cache hit rate, sessions, top queries | Must | done |
| 61 | Feature flags with a runtime toggle that survives a restart | Must | done |
| 62 | JSONL event log plus an optional local webhook | Should | done |
| 63 | Custom Prometheus series for watch seconds, ticks, impressions, ranking latency | Should | done |
| 64 | Startup migrator covering every new column and index | Must | done |
| 65 | Demo telemetry generator so a fresh boot has something to show | Must | done |
| 66 | Playwright smoke suite wired into CI against the real stack | Must | done |
| 67 | Multi profile with a PIN lock | Could | later. Separate accounts already do this and a PIN implies a threat model this app does not have |
| 68 | Grafana dashboard JSON | Could | later. The series are exported, the dashboard is a copy paste away for anyone who wants it |
