import React, { useEffect, useEffectEvent, useRef, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";
import { Icon } from "./icons";

const GENRE_SHORTCUTS = [
  "Action",
  "Adventure",
  "Comedy",
  "Drama",
  "Fantasy",
  "Romance",
  "Sci-Fi",
  "Slice of Life",
  "Sports",
  "Supernatural",
  "Mecha",
  "Mystery",
];

const STATUS_LABELS = {
  plan_to_watch: "Plan to watch",
  watching: "Watching",
  completed: "Completed",
  on_hold: "On hold",
  dropped: "Dropped",
};

function progressPct(entry) {
  const total = entry?.anime?.episodes;
  const prog = entry?.progress || 0;
  if (!total || total <= 0) return 0;
  return Math.min(100, Math.round((prog / total) * 100));
}

function ContinueCard({ entry, token, onTick }) {
  const anime = entry.anime;
  if (!anime) return null;
  const total = anime.episodes || "?";
  return (
    <article className="watch-card">
      <Link to={`/anime/${anime.id}`}>
        {anime.image_url ? (
          <img src={anime.image_url} alt="" />
        ) : (
          <img src="/poster-fallback.png" alt="" />
        )}
      </Link>
      <div>
        <h3>
          <Link to={`/anime/${anime.id}`}>{anime.title}</Link>
        </h3>
        <p className="meta">
          Ep {entry.progress || 0} / {total} · {STATUS_LABELS[entry.status] || entry.status}
        </p>
        <div className="progress-bar" aria-hidden>
          <span style={{ width: `${progressPct(entry)}%` }} />
        </div>
      </div>
      {token && (
        <div className="watch-actions">
          <button type="button" className="btn compact" onClick={() => onTick(anime.id)}>
            +1 ep
          </button>
          <Link className="ghost-btn" to={`/anime/${anime.id}`}>
            Open
          </Link>
        </div>
      )}
    </article>
  );
}

function useDebounced(value, ms = 280) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function rememberRecent(anime) {
  try {
    const key = "kura_recent";
    const prev = JSON.parse(localStorage.getItem(key) || "[]");
    const next = [{ id: anime.id, title: anime.title, image_url: anime.image_url }, ...prev.filter((x) => x.id !== anime.id)].slice(0, 12);
    localStorage.setItem(key, JSON.stringify(next));
  } catch {
    /* ignore */
  }
}

function readRecent() {
  try {
    return JSON.parse(localStorage.getItem("kura_recent") || "[]");
  } catch {
    return [];
  }
}

function ScoreBadge({ score }) {
  if (score == null) return null;
  return <span className="score-badge">{Number(score).toFixed(1)}</span>;
}

function AnimeCard({ anime, token, onRate, reason, method, userScore }) {
  return (
    <article className="tile">
      <Link
        to={`/anime/${anime.id}`}
        className="tile-poster"
        onClick={() => rememberRecent(anime)}
      >
        {anime.image_url ? (
          <img
            src={anime.image_url}
            alt=""
            loading="lazy"
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = "/poster-fallback.png";
            }}
          />
        ) : (
          <div className="poster-fallback">
            <span>{anime.title.slice(0, 1)}</span>
          </div>
        )}
        <ScoreBadge score={anime.score} />
        {userScore != null && <span className="you-rated">You · {userScore}</span>}
      </Link>
      <div className="tile-body">
        <h3>
          <Link to={`/anime/${anime.id}`} onClick={() => rememberRecent(anime)}>
            {anime.title}
          </Link>
        </h3>
        <p className="meta">{[anime.type, anime.year].filter(Boolean).join(" · ")}</p>
        {(reason || method) && (
          <p className="reason">
            {method && <span className="method-tag">{method}</span>}
            {reason}
          </p>
        )}
        {!reason && (
          <p className="genres">{(anime.genres || "").split(",").slice(0, 2).join(" · ")}</p>
        )}
        {token && onRate && (
          <div className="rate-strip" role="group" aria-label={`Rate ${anime.title}`}>
            {[7, 8, 9, 10].map((s) => (
              <button key={s} type="button" onClick={() => onRate(anime.id, s)} title={`Rate ${s}/10`}>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function EmptyState({ title, body, action }) {
  return (
    <div className="empty">
      <img src="/mascot-chibi.png" alt="" className="empty-mascot" />
      <h2>{title}</h2>
      <p>{body}</p>
      {action}
    </div>
  );
}

function Toast({ message, onDone }) {
  useEffect(() => {
    if (!message) return undefined;
    const t = setTimeout(onDone, 2600);
    return () => clearTimeout(t);
  }, [message, onDone]);
  if (!message) return null;
  return <div className="toast-float" role="status">{message}</div>;
}

function Shell({ children, searchSlot }) {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api("/api/stats").then(setStats).catch(() => {});
  }, []);

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Primary">
        <Link to="/" className="brand">
          <img src="/logo.png" alt="" className="brand-logo" />
          <span>
            <strong>Kura</strong>
            <small>local vault</small>
          </span>
        </Link>

        <nav className="rail-nav">
          <NavLink to="/" end>
            <Icon name="discover" /> Discover
          </NavLink>
          <NavLink to="/watching">
            <Icon name="watch" /> Watching
          </NavLink>
          <NavLink to="/recommendations">
            <Icon name="foryou" /> For You
          </NavLink>
          <NavLink to="/shelf">
            <Icon name="shelf" /> Shelf
          </NavLink>
          <NavLink to="/library">
            <Icon name="ratings" /> Library
          </NavLink>
        </nav>

        <div className="rail-foot">
          <div className="rail-mascot" aria-hidden>
            <img src="/mascot-chibi.png" alt="" />
            <span>Your vault buddy</span>
          </div>
          {stats && (
            <div className="vault-meter" title="Catalog health">
              <div className="meter-label">
                <Icon name="local" size={14} /> Vault
              </div>
              <div className="meter-bars" aria-hidden>
                {[0.55, 0.8, 0.45, 0.95, 0.7].map((h, i) => (
                  <span key={i} style={{ "--h": h }} />
                ))}
              </div>
              <p>
                <strong>{stats.anime_count.toLocaleString()}</strong> titles ·{" "}
                <strong>{stats.rating_count.toLocaleString()}</strong> ratings
              </p>
            </div>
          )}
          {user ? (
            <div className="rail-user">
              <Icon name="user" size={16} />
              <span>{user.username}</span>
              <button type="button" className="icon-btn" onClick={logout} aria-label="Log out">
                <Icon name="logout" size={16} />
              </button>
            </div>
          ) : (
            <Link className="btn block" to="/login">
              Sign in
            </Link>
          )}
        </div>
      </aside>

      <div className="workspace">
        <header className="workspace-bar">
          {searchSlot || <div />}
          <div className="bar-hint">
            <kbd>/</kbd> search
          </div>
        </header>
        <main className="workspace-main">{children}</main>
      </div>
    </div>
  );
}

function SearchBar({ q, setQ, onSubmit, mode, setMode, suggestions, onPick, busy, inputRef }) {
  return (
    <form
      className="command-search"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      role="search"
    >
      <Icon name="search" size={18} />
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search titles, genres, vibes…"
        aria-label="Search anime"
        autoComplete="off"
      />
      <select
        value={mode}
        onChange={(e) => setMode(e.target.value)}
        aria-label="Search mode"
        className="mode-select"
      >
        <option value="hybrid">Hybrid</option>
        <option value="lexical">Lexical</option>
        <option value="semantic">Semantic</option>
      </select>
      <button type="submit" className="btn compact" disabled={busy}>
        {busy ? "…" : "Go"}
      </button>
      {suggestions?.length > 0 && (
        <ul className="suggest-panel">
          {suggestions.map((s) => (
            <li key={s.id}>
              <button type="button" onClick={() => onPick(s)}>
                {s.image_url ? (
                  <img src={s.image_url} alt="" className="suggest-thumb" />
                ) : (
                  <span className="suggest-thumb" />
                )}
                <span>{s.title}</span>
                <small>{[s.type, s.year].filter(Boolean).join(" · ")}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}

function Discover() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const [mode, setMode] = useState("hybrid");
  const [genre, setGenre] = useState(params.get("genre") || "");
  const [type, setType] = useState(params.get("type") || "");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(true);
  const [booted, setBooted] = useState(false);
  const [message, setMessage] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [genres, setGenres] = useState(GENRE_SHORTCUTS);
  const [recent, setRecent] = useState([]);
  const [continueWatching, setContinueWatching] = useState([]);
  const inputRef = useRef(null);
  const debouncedQ = useDebounced(q, 260);

  const clearToast = useEffectEvent(() => setMessage(""));

  useEffect(() => {
    setRecent(readRecent());
    api("/api/anime/genres")
      .then((d) => {
        if (d.genres?.length) setGenres(d.genres.slice(0, 16));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!token) {
      setContinueWatching([]);
      return;
    }
    api("/api/library/continue?limit=6", { token })
      .then(setContinueWatching)
      .catch(() => setContinueWatching([]));
  }, [token]);

  useEffect(() => {
    const g = params.get("genre") || "";
    const t = params.get("type") || "";
    const query = params.get("q") || "";
    setGenre(g);
    setType(t);
    setQ(query);
    load({ query, g, t, p: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, mode]);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "/" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!debouncedQ.trim() || debouncedQ.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    api(`/api/anime/suggest?q=${encodeURIComponent(debouncedQ.trim())}`)
      .then((d) => setSuggestions(d.items || []))
      .catch(() => setSuggestions([]));
  }, [debouncedQ]);

  async function load({ query = q, g = genre, t = type, p = 1, append = false } = {}) {
    setBusy(true);
    try {
      let data;
      if (g || t) {
        const browseParams = new URLSearchParams({ page: String(p), page_size: "24" });
        if (g) browseParams.set("genre", g);
        if (t) browseParams.set("type", t);
        data = await api(`/api/anime/browse?${browseParams}`);
      } else {
        data = await api(
          `/api/anime/search?q=${encodeURIComponent(query)}&limit=24&mode=${encodeURIComponent(mode)}`
        );
      }
      setItems((prev) => (append ? [...prev, ...data.items] : data.items));
      setTotal(data.total);
      setPage(p);
      setBooted(true);
      if (!append && data.items.length === 0 && query.trim()) {
        setMessage(`No matches for “${query.trim()}”. Try a genre chip or shorter keywords.`);
      }
    } catch (err) {
      setMessage(err.message);
      setBooted(true);
    } finally {
      setBusy(false);
    }
  }

  function syncParams({ query = "", g = "", t = "" } = {}) {
    const next = new URLSearchParams();
    if (query.trim()) next.set("q", query.trim());
    if (g) next.set("genre", g);
    if (t) next.set("type", t);
    setParams(next, { replace: true });
  }

  async function rate(animeId, score) {
    try {
      await api("/api/ratings", { method: "POST", token, body: { anime_id: animeId, score } });
      setMessage(`Saved ${score}/10 · marked completed`);
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function tickContinue(animeId) {
    try {
      const data = await api(`/api/library/${animeId}/tick`, { method: "POST", token });
      setMessage(
        data.status === "completed"
          ? `Finished ${data.anime?.title || "title"}`
          : `Now on ep ${data.progress}`
      );
      const rows = await api("/api/library/continue?limit=6", { token });
      setContinueWatching(rows);
    } catch (err) {
      setMessage(err.message);
    }
  }

  const heading = genre
    ? `${genre} shelf`
    : type
      ? `${type} titles`
      : q.trim()
        ? `Results for “${q.trim()}”`
        : "Top of the vault";

  return (
    <Shell
      searchSlot={
        <SearchBar
          q={q}
          setQ={setQ}
          mode={mode}
          setMode={setMode}
          busy={busy}
          inputRef={inputRef}
          suggestions={suggestions}
          onSubmit={() => {
            setSuggestions([]);
            syncParams({ query: q, g: "", t: "" });
          }}
          onPick={(s) => {
            setSuggestions([]);
            setQ(s.title);
            navigate(`/anime/${s.id}`);
          }}
        />
      }
    >
      {!q && !genre && !type && (
        <section className="feature-hero">
          <div
            className="feature-hero-bg"
            style={{
              backgroundImage: `url(${items[0]?.image_url || "/hero-banner.png"})`,
            }}
          />
          <div className="feature-hero-copy">
            <p className="eyebrow">Tonight in your vault</p>
            <h1>Pick a poster. Rate it. Get better picks.</h1>
            <p>
              Dense local catalog with real cover art — search vibes, stack a shelf, let hybrid
              ranking learn what you actually finish.
            </p>
            <div className="hero-actions">
              <button type="button" className="btn" onClick={() => inputRef.current?.focus()}>
                Start searching
              </button>
              <Link className="btn ghost-neon" to="/recommendations">
                Open For You
              </Link>
            </div>
          </div>
          <div className="feature-hero-mascot" aria-hidden>
            <img src="/mascot.png" alt="" />
          </div>
        </section>
      )}

      <section className="panel-head">
        <div>
          <p className="eyebrow">Discover</p>
          <h1>{heading}</h1>
          <p className="lede">
            Browse your local catalog. Rate what you finish so For You can learn your taste.
          </p>
        </div>
        <div className="head-meta">
          {busy ? "Searching…" : `${total.toLocaleString()} matches`}
        </div>
      </section>

      <div className="filter-row">
        <button
          type="button"
          className={`chip ${!genre && !type && !q ? "active" : ""}`}
          onClick={() => syncParams({})}
        >
          All
        </button>
        {genres.map((g) => (
          <button
            key={g}
            type="button"
            className={`chip ${genre === g ? "active" : ""}`}
            onClick={() => syncParams({ g, t: type })}
          >
            {g}
          </button>
        ))}
      </div>

      <div className="filter-row slim">
        <Icon name="filter" size={14} />
        {TYPES.map((t) => (
          <button
            key={t}
            type="button"
            className={`chip ghost ${type === t ? "active" : ""}`}
            onClick={() => syncParams({ g: genre, t: type === t ? "" : t })}
          >
            {t}
          </button>
        ))}
      </div>

      {continueWatching.length > 0 && !q && !genre && !type && (
        <section className="recent-rail">
          <h2>Continue watching</h2>
          <div className="continue-row">
            {continueWatching.map((entry) => (
              <ContinueCard
                key={entry.anime_id}
                entry={entry}
                token={token}
                onTick={tickContinue}
              />
            ))}
          </div>
        </section>
      )}

      {recent.length > 0 && !q && !genre && !type && (
        <section className="recent-rail">
          <h2>Recently opened</h2>
          <div className="recent-row">
            {recent.map((r) => (
              <Link key={r.id} to={`/anime/${r.id}`} className="recent-pill">
                {r.image_url ? <img src={r.image_url} alt="" /> : <span>{r.title.slice(0, 1)}</span>}
                <em>{r.title}</em>
              </Link>
            ))}
          </div>
        </section>
      )}

      {busy && !booted ? (
        <p className="pad">Loading vault…</p>
      ) : items.length === 0 && !busy ? (
        <EmptyState
          title="Nothing on this shelf"
          body="Try another spelling, a single keyword, or pick a genre chip above."
          action={
            <button type="button" className="btn" onClick={() => syncParams({})}>
              Reset filters
            </button>
          }
        />
      ) : (
        <section className="tile-grid">
          {items.map((anime) => (
            <AnimeCard key={anime.id} anime={anime} token={token} onRate={rate} />
          ))}
        </section>
      )}

      {genre || type ? (
        <div className="pager">
          <button
            type="button"
            className="ghost-btn"
            disabled={page <= 1 || busy}
            onClick={() => load({ g: genre, t: type, p: page - 1 })}
          >
            Previous
          </button>
          <span>
            Page {page}
          </span>
          <button
            type="button"
            className="ghost-btn"
            disabled={busy || items.length < 24}
            onClick={() => load({ g: genre, t: type, p: page + 1 })}
          >
            Next
          </button>
        </div>
      ) : null}

      <Toast message={message} onDone={clearToast} />
    </Shell>
  );
}

function Recommendations() {
  const { token, user, loading } = useAuth();
  const [rows, setRows] = useState([]);
  const [cached, setCached] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    if (!token) return;
    setBusy(true);
    try {
      const data = await api("/api/recommendations?limit=24", { token });
      setRows(data.recommendations);
      setCached(data.cached);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [token]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading your vault…</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">For You</p>
          <h1>Picks for {user.username}</h1>
          <p className="lede">
            Hybrid ranking blends shows like ones you rated with neighbors who share your taste
            {cached ? " · Redis cache hit" : " · freshly scored"}.
          </p>
        </div>
        <button type="button" className="btn" onClick={refresh} disabled={busy}>
          <Icon name="spark" size={16} /> Refresh
        </button>
      </section>
      {error && <p className="toast">{error}</p>}
      {rows.length === 0 ? (
        <EmptyState
          title="Rate a few titles first"
          body="Open Discover, score shows you like (7+), then come back for personalized picks."
          action={
            <Link className="btn" to="/">
              Go discover
            </Link>
          }
        />
      ) : (
        <section className="tile-grid">
          {rows.map((row) => (
            <AnimeCard
              key={row.anime.id}
              anime={row.anime}
              reason={row.reason}
              method={row.method}
            />
          ))}
        </section>
      )}
    </Shell>
  );
}

function Watching() {
  const { token, user, loading } = useAuth();
  const [rows, setRows] = useState([]);
  const [message, setMessage] = useState("");
  const clearToast = useEffectEvent(() => setMessage(""));

  async function load() {
    const data = await api("/api/library?status=watching", { token });
    setRows(data);
  }

  useEffect(() => {
    if (token) load().catch((e) => setMessage(e.message));
  }, [token]);

  if (loading) return <Shell><p className="pad">Loading…</p></Shell>;
  if (!user) return <Navigate to="/login" replace />;

  async function tick(animeId) {
    const data = await api(`/api/library/${animeId}/tick`, { method: "POST", token });
    setMessage(data.status === "completed" ? "Marked completed" : `Ep ${data.progress}`);
    await load();
  }

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Watching</p>
          <h1>Currently watching</h1>
          <p className="lede">
            Tap +1 ep as you finish episodes. Hit the end and Kura auto-marks it completed.
            Rating a title also completes it automatically.
          </p>
        </div>
        <span className="head-meta">{rows.length} in progress</span>
      </section>
      {rows.length === 0 ? (
        <EmptyState
          title="Nothing in progress"
          body="Open a title and hit Start watching, or +1 ep to begin auto-tracking."
          action={<Link className="btn" to="/">Find something to watch</Link>}
        />
      ) : (
        <div className="continue-row">
          {rows.map((entry) => (
            <ContinueCard key={entry.anime_id} entry={entry} token={token} onTick={tick} />
          ))}
        </div>
      )}
      <Toast message={message} onDone={clearToast} />
    </Shell>
  );
}

function Shelf() {
  const { token, user, loading } = useAuth();
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [message, setMessage] = useState("");
  const clearToast = useEffectEvent(() => setMessage(""));

  async function load() {
    const path = filter === "all" ? "/api/library" : `/api/library?status=${filter}`;
    const data = await api(path, { token });
    setItems(data);
  }

  useEffect(() => {
    if (token) load().catch((e) => setMessage(e.message));
  }, [token, filter]);

  if (loading) return <Shell><p className="pad">Loading…</p></Shell>;
  if (!user) return <Navigate to="/login" replace />;

  async function remove(id) {
    await api(`/api/watchlist/${id}`, { method: "DELETE", token });
    setItems((prev) => prev.filter((a) => a.anime_id !== id));
    setMessage("Removed from shelf");
  }

  async function setStatus(id, status) {
    await api(`/api/library/${id}`, {
      method: "PUT",
      token,
      body: { status },
    });
    setMessage(`Moved to ${STATUS_LABELS[status] || status}`);
    await load();
  }

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Shelf</p>
          <h1>Your list</h1>
          <p className="lede">Plan, watch, hold, drop, or finish — tracked on this machine with your account.</p>
        </div>
        <span className="head-meta">{items.length} titles</span>
      </section>
      <div className="filter-row">
        {["all", ...Object.keys(STATUS_LABELS)].map((key) => (
          <button
            key={key}
            type="button"
            className={`chip ${filter === key ? "active" : ""}`}
            onClick={() => setFilter(key)}
          >
            {key === "all" ? "All" : STATUS_LABELS[key]}
          </button>
        ))}
      </div>
      {items.length === 0 ? (
        <EmptyState
          title="Shelf is empty"
          body="On any title page, add to shelf or start watching to queue it here."
          action={<Link className="btn" to="/">Browse catalog</Link>}
        />
      ) : (
        <div className="continue-row">
          {items.map((entry) => (
            <article className="watch-card" key={entry.anime_id}>
              <Link to={`/anime/${entry.anime_id}`}>
                {entry.anime?.image_url ? (
                  <img src={entry.anime.image_url} alt="" />
                ) : (
                  <img src="/poster-fallback.png" alt="" />
                )}
              </Link>
              <div>
                <h3>
                  <Link to={`/anime/${entry.anime_id}`}>{entry.anime?.title}</Link>
                </h3>
                <p className="meta">
                  {STATUS_LABELS[entry.status] || entry.status}
                  {entry.anime?.episodes
                    ? ` · Ep ${entry.progress || 0}/${entry.anime.episodes}`
                    : entry.progress
                      ? ` · Ep ${entry.progress}`
                      : ""}
                </p>
                <div className="progress-bar" aria-hidden>
                  <span style={{ width: `${progressPct(entry)}%` }} />
                </div>
                <label className="sort-label" style={{ marginTop: "0.55rem" }}>
                  Status
                  <select
                    className="status-select"
                    value={entry.status}
                    onChange={(e) => setStatus(entry.anime_id, e.target.value)}
                  >
                    {Object.entries(STATUS_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="watch-actions">
                {entry.status === "watching" && (
                  <button
                    type="button"
                    className="btn compact"
                    onClick={() =>
                      api(`/api/library/${entry.anime_id}/tick`, { method: "POST", token }).then(load)
                    }
                  >
                    +1 ep
                  </button>
                )}
                <button type="button" className="ghost-btn danger" onClick={() => remove(entry.anime_id)}>
                  Remove
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      <Toast message={message} onDone={clearToast} />
    </Shell>
  );
}

function Library() {
  const { token, user, loading } = useAuth();
  const [rows, setRows] = useState([]);
  const [sort, setSort] = useState("score");

  useEffect(() => {
    if (!token) return;
    api("/api/ratings/me", { token }).then(setRows).catch(() => setRows([]));
  }, [token]);

  if (loading) return <Shell><p className="pad">Loading…</p></Shell>;
  if (!user) return <Navigate to="/login" replace />;

  const sorted = [...rows].sort((a, b) => {
    if (sort === "score") return b.score - a.score;
    return (a.anime?.title || "").localeCompare(b.anime?.title || "");
  });

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Library</p>
          <h1>Your ratings</h1>
          <p className="lede">These scores train hybrid recommendations for your account.</p>
        </div>
        <label className="sort-label">
          Sort
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="score">Highest score</option>
            <option value="title">Title</option>
          </select>
        </label>
      </section>
      {sorted.length === 0 ? (
        <EmptyState
          title="No ratings yet"
          body="Rate titles from Discover or a detail page. Use 7–10 for shows you want more of."
          action={<Link className="btn" to="/">Start rating</Link>}
        />
      ) : (
        <section className="tile-grid">
          {sorted.map((r) =>
            r.anime ? (
              <AnimeCard key={r.anime_id} anime={r.anime} userScore={r.score} />
            ) : null
          )}
        </section>
      )}
    </Shell>
  );
}

function Detail() {
  const { id } = useParams();
  const { token } = useAuth();
  const [anime, setAnime] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [message, setMessage] = useState("");
  const [myScore, setMyScore] = useState(null);
  const [entry, setEntry] = useState(null);
  const clearToast = useEffectEvent(() => setMessage(""));

  async function refreshLibrary() {
    if (!token) return;
    const rows = await api("/api/library", { token });
    setEntry(rows.find((r) => r.anime_id === Number(id)) || null);
  }

  useEffect(() => {
    api(`/api/anime/${id}`)
      .then((a) => {
        setAnime(a);
        rememberRecent(a);
      })
      .catch((err) => setMessage(err.message));
    api(`/api/anime/${id}/similar`).then(setSimilar).catch(() => {});
  }, [id]);

  useEffect(() => {
    if (!token) {
      setEntry(null);
      setMyScore(null);
      return;
    }
    api("/api/ratings/me", { token })
      .then((rows) => {
        const hit = rows.find((r) => r.anime_id === Number(id));
        setMyScore(hit?.score ?? null);
      })
      .catch(() => {});
    refreshLibrary().catch(() => {});
  }, [token, id]);

  async function rate(score) {
    if (!token) {
      setMessage("Sign in to rate");
      return;
    }
    await api("/api/ratings", {
      method: "POST",
      token,
      body: { anime_id: Number(id), score },
    });
    setMyScore(score);
    setMessage(`Rated ${score}/10 · auto-marked completed`);
    await refreshLibrary();
  }

  async function setStatus(status) {
    if (!token) {
      setMessage("Sign in to track watching");
      return;
    }
    const data = await api(`/api/library/${id}`, {
      method: "PUT",
      token,
      body: { status, progress: entry?.progress ?? 0 },
    });
    setEntry(data);
    setMessage(`Status: ${STATUS_LABELS[data.status] || data.status}`);
  }

  async function tick() {
    if (!token) {
      setMessage("Sign in to track episodes");
      return;
    }
    const data = await api(`/api/library/${id}/tick`, { method: "POST", token });
    setEntry({
      anime_id: data.anime_id,
      status: data.status,
      progress: data.progress,
      anime: data.anime,
    });
    setMessage(
      data.status === "completed"
        ? "Finished — marked completed"
        : `Now on episode ${data.progress}`
    );
  }

  async function toggleShelf() {
    if (!token) {
      setMessage("Sign in to use your shelf");
      return;
    }
    if (entry) {
      await api(`/api/watchlist/${id}`, { method: "DELETE", token });
      setEntry(null);
      setMessage("Removed from shelf");
    } else {
      await setStatus("plan_to_watch");
    }
  }

  if (!anime) {
    return (
      <Shell>
        <p className="pad">{message || "Loading title…"}</p>
      </Shell>
    );
  }

  return (
    <Shell>
      <section className="detail-hero">
        <div className="detail-art">
          {anime.image_url ? (
            <img
              src={anime.image_url}
              alt=""
              onError={(e) => {
                e.currentTarget.onerror = null;
                e.currentTarget.src = "/poster-fallback.png";
              }}
            />
          ) : (
            <div className="poster-fallback large">
              <span>{anime.title.slice(0, 1)}</span>
            </div>
          )}
        </div>
        <div className="detail-copy">
          <p className="eyebrow">Title</p>
          <h1>{anime.title}</h1>
          {anime.title_english && anime.title_english !== anime.title && (
            <p className="aka">{anime.title_english}</p>
          )}
          <p className="meta lg">
            {[anime.type, anime.year, anime.episodes ? `${anime.episodes} eps` : null, anime.status]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <div className="tag-row">
            {(anime.genres || "")
              .split(",")
              .map((g) => g.trim())
              .filter(Boolean)
              .map((g) => (
                <Link key={g} className="chip" to={`/?genre=${encodeURIComponent(g)}`}>
                  {g}
                </Link>
              ))}
          </div>
          <p className="synopsis">{anime.synopsis}</p>
          <div className="actions">
            <button
              type="button"
              className="btn"
              onClick={() => setStatus(entry?.status === "watching" ? "on_hold" : "watching")}
            >
              <Icon name="watch" size={16} />
              {entry?.status === "watching" ? "Pause watching" : "Start watching"}
            </button>
            <button type="button" className="btn ghost-neon" onClick={tick}>
              +1 episode
            </button>
            <button type="button" className="ghost-btn" onClick={toggleShelf}>
              <Icon name={entry ? "check" : "plus"} size={16} />
              {entry ? "On shelf" : "Add to shelf"}
            </button>
            {anime.score != null && (
              <span className="score-pill">
                Catalog <strong>{Number(anime.score).toFixed(1)}</strong>
              </span>
            )}
            {myScore != null && (
              <span className="score-pill you">Your score <strong>{myScore}</strong></span>
            )}
          </div>
          {entry && (
            <div className="rate-panel">
              <span>
                Tracking · {STATUS_LABELS[entry.status] || entry.status}
                {anime.episodes
                  ? ` · Ep ${entry.progress || 0}/${anime.episodes}`
                  : entry.progress
                    ? ` · Ep ${entry.progress}`
                    : ""}
              </span>
              <div className="progress-bar" aria-hidden>
                <span
                  style={{
                    width: `${
                      anime.episodes
                        ? Math.min(100, Math.round(((entry.progress || 0) / anime.episodes) * 100))
                        : 0
                    }%`,
                  }}
                />
              </div>
              <label className="sort-label">
                Status
                <select
                  className="status-select"
                  value={entry.status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  {Object.entries(STATUS_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <div className="rate-panel">
            <span>Rate (auto-completes)</span>
            <div className="rate-strip large">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((s) => (
                <button
                  key={s}
                  type="button"
                  className={myScore === s ? "active" : ""}
                  onClick={() => rate(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      <h2 className="section-title">
        <Icon name="similar" size={22} /> Similar titles
      </h2>
      <section className="tile-grid">
        {similar.map((item) => (
          <AnimeCard key={item.id} anime={item} />
        ))}
      </section>
      <Toast message={message} onDone={clearToast} />
    </Shell>
  );
}

function Login() {
  const { login, register, user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("demo@anime.app");
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");

  if (user) return <Navigate to="/recommendations" replace />;

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      if (mode === "login") await login(email, password);
      else await register(email, username, password);
      navigate("/recommendations");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-visual" aria-hidden>
        <img src="/mascot.png" alt="" className="auth-mascot" />
      </div>
      <form className="auth-card" onSubmit={submit}>
        <p className="eyebrow">Kura</p>
        <h1>{mode === "login" ? "Open your vault" : "Create a vault login"}</h1>
        <p className="hint">Local-first demo · demo@anime.app / demo1234</p>
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        {mode === "register" && (
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
        )}
        <label>
          Password
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
          />
        </label>
        {error && <p className="toast">{error}</p>}
        <button className="btn block" type="submit">
          {mode === "login" ? "Sign in" : "Register"}
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account?" : "Have an account?"}
        </button>
        <Link to="/" className="text-link">
          Back to Discover
        </Link>
      </form>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Discover />} />
      <Route path="/watching" element={<Watching />} />
      <Route path="/recommendations" element={<Recommendations />} />
      <Route path="/shelf" element={<Shelf />} />
      <Route path="/library" element={<Library />} />
      <Route path="/anime/:id" element={<Detail />} />
      <Route path="/login" element={<Login />} />
    </Routes>
  );
}
