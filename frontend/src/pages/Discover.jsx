import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../icons";
import { AnimeCard, readRecent } from "../components/AnimeCard";
import { ContinueCard } from "../components/ContinueCard";
import { EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { useGridKeys } from "../lib/useGridKeys";
import { usePrefs } from "../lib/prefs";
import { sfx } from "../lib/sound";

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

const TYPES = ["TV", "Movie", "OVA", "ONA", "Special"];

const SMART_FILTERS = [
  { id: "one_sitting", label: "Finishable tonight" },
  { id: "movies_under", label: "Movies under 100m" },
  { id: "airing", label: "Currently airing" },
  { id: "short", label: "Under 13 episodes" },
  { id: "classics", label: "Pre-2005 classics" },
  { id: "hidden_gems", label: "Hidden gems" },
];

function useDebounced(value, ms = 280) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
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
        placeholder="Search titles, genres, or a vibe like cozy rain school"
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
        {busy ? "..." : "Go"}
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

export function Discover() {
  const { token } = useAuth();
  const { prefs, flag, save } = usePrefs();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const [mode, setMode] = useState("hybrid");
  const [genre, setGenre] = useState(params.get("genre") || "");
  const [type, setType] = useState(params.get("type") || "");
  const [smart, setSmart] = useState("");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(true);
  const [booted, setBooted] = useState(false);
  const [expanded, setExpanded] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [genres, setGenres] = useState(GENRE_SHORTCUTS);
  const [recent, setRecent] = useState([]);
  const [continueWatching, setContinueWatching] = useState([]);
  const [rail, setRail] = useState(null);
  const [almost, setAlmost] = useState([]);
  const [diversity, setDiversity] = useState(prefs.diversity ?? 0.35);
  const inputRef = useRef(null);
  const toast = useToast();
  const debouncedQ = useDebounced(q, 260);

  const browsing = Boolean(q || genre || type || smart);

  useEffect(() => setDiversity(prefs.diversity ?? 0.35), [prefs.diversity]);

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
      setAlmost([]);
      return;
    }
    api("/api/library/continue?limit=6", { token })
      .then(setContinueWatching)
      .catch(() => setContinueWatching([]));
    api("/api/discover/almost?limit=8", { token })
      .then((d) => setAlmost(d.items || []))
      .catch(() => setAlmost([]));
  }, [token]);

  const loadRail = useCallback(
    (strength) => {
      if (!flag("explore_boost")) return;
      const suffix = strength == null ? "" : `&diversity=${strength}`;
      api(`/api/discover/rail?limit=18${suffix}`, { token })
        .then(setRail)
        .catch(() => setRail(null));
    },
    [token, flag]
  );

  useEffect(() => {
    loadRail(null);
  }, [loadRail]);

  const load = useCallback(
    async ({ query = q, g = genre, t = type, s = smart, p = 1, append = false } = {}) => {
      setBusy(true);
      try {
        let data;
        if (s) {
          data = await api(`/api/discover/smart?filter=${s}&limit=24&minutes=180`, { token });
        } else if (g || t) {
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
        setExpanded(data.expanded_terms || []);
        setPage(p);
        setBooted(true);
        if (!append && data.items.length === 0 && query.trim()) {
          toast.say(`No matches for "${query.trim()}". Try a shorter keyword or a genre chip.`);
        }
      } catch (err) {
        toast.say(err.message);
        setBooted(true);
      } finally {
        setBusy(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [q, genre, type, smart, mode, token]
  );

  useEffect(() => {
    const g = params.get("genre") || "";
    const t = params.get("type") || "";
    const s = params.get("smart") || "";
    const query = params.get("q") || "";
    setGenre(g);
    setType(t);
    setSmart(s);
    setQ(query);
    load({ query, g, t, s, p: 1 });
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

  function syncParams({ query = "", g = "", t = "", s = "" } = {}) {
    const next = new URLSearchParams();
    if (query.trim()) next.set("q", query.trim());
    if (g) next.set("genre", g);
    if (t) next.set("type", t);
    if (s) next.set("smart", s);
    setParams(next, { replace: true });
  }

  async function rate(animeId, score) {
    if (!token) return toast.say("Sign in to rate");
    try {
      await api("/api/ratings", { method: "POST", token, body: { anime_id: animeId, score } });
      sfx.rate();
      toast.say(`Saved ${score} out of 10 and marked completed`);
    } catch (err) {
      toast.say(err.message);
    }
    return undefined;
  }

  async function dismiss(anime, reason) {
    if (!token) return toast.say("Sign in to tune your feed");
    try {
      await api("/api/signals/feedback", {
        method: "POST",
        token,
        body: { anime_id: anime.id, reason },
      });
      setItems((prev) => prev.filter((a) => a.id !== anime.id));
      setRail((prev) =>
        prev ? { ...prev, items: prev.items.filter((r) => r.anime.id !== anime.id) } : prev
      );
      toast.say(`Hidden. Ranking will lean away from that.`);
    } catch (err) {
      toast.say(err.message);
    }
    return undefined;
  }

  async function addToShelf(anime) {
    if (!token) return toast.say("Sign in to use your shelf");
    try {
      await api(`/api/watchlist/${anime.id}`, { method: "POST", token });
      toast.say(`${anime.title} is on your shelf`);
    } catch (err) {
      toast.say(err.message);
    }
    return undefined;
  }

  async function tickContinue(animeId) {
    try {
      const data = await api(`/api/library/${animeId}/tick`, { method: "POST", token });
      if (data.status === "completed") sfx.complete();
      else sfx.tick();
      toast.say(
        data.status === "completed"
          ? `Finished ${data.anime?.title || "title"}`
          : `Now on ep ${data.progress}`
      );
      setContinueWatching(await api("/api/library/continue?limit=6", { token }));
    } catch (err) {
      toast.say(err.message);
    }
  }

  async function surprise() {
    try {
      const data = await api("/api/discover/surprise", { token });
      navigate(`/anime/${data.anime.id}`);
    } catch (err) {
      toast.say(err.message);
    }
  }

  const railItems = rail?.items?.map((r) => r.anime) || [];
  const gridItems = browsing ? items : railItems.length ? railItems : items;

  const { selectedId } = useGridKeys({
    items: gridItems,
    enabled: flag("keyboard_mode"),
    onOpen: (a) => navigate(`/anime/${a.id}`),
    onTick: (a) => tickContinue(a.id),
    onRate: (a, score) => rate(a.id, score),
    onDismiss: dismiss,
  });

  const heading = smart
    ? SMART_FILTERS.find((f) => f.id === smart)?.label || "Smart filter"
    : genre
      ? `${genre} shelf`
      : type
        ? `${type} titles`
        : q.trim()
          ? `Results for "${q.trim()}"`
          : "Tuned for you";

  return (
    <Shell
      mascot={busy ? "searching" : "idle"}
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
            syncParams({ query: q });
          }}
          onPick={(s) => {
            setSuggestions([]);
            setQ(s.title);
            navigate(`/anime/${s.id}`);
          }}
        />
      }
    >
      {!browsing && (
        <section className="feature-hero">
          <div
            className="feature-hero-bg"
            style={{ backgroundImage: `url(${gridItems[0]?.image_url || "/hero-banner.png"})` }}
          />
          <div className="feature-hero-copy">
            <p className="eyebrow">Featured</p>
            <h1>Watch it. Kura keeps the count.</h1>
            <p>
              Start a session while you watch on your own setup and your episode moves on its own.
              Every poster you linger on quietly shapes what shows up next.
            </p>
            <div className="hero-actions">
              <button type="button" className="btn" onClick={() => inputRef.current?.focus()}>
                Start searching
              </button>
              <Link className="btn ghost-neon" to="/recommendations">
                Open For You
              </Link>
              {flag("surprise_me") && (
                <button type="button" className="ghost-btn" onClick={surprise}>
                  <Icon name="dice" size={16} /> Surprise me
                </button>
              )}
            </div>
          </div>
          <div className="feature-hero-mascot" aria-hidden="true">
            <img src="/mascot.png" alt="" />
          </div>
        </section>
      )}

      <section className="panel-head">
        <div>
          <p className="eyebrow">Discover</p>
          <h1>{heading}</h1>
          <p className="lede">
            {!browsing && rail?.personalized
              ? "Ranked from what you rate, finish, and skip past. The slider decides how far it wanders."
              : "Browse the catalog. Rate what you finish so For You can learn your taste."}
          </p>
        </div>
        <div className="head-meta">{busy ? "Searching..." : `${total.toLocaleString()} matches`}</div>
      </section>

      {!browsing && rail?.personalized && token && (
        <div className="rail-controls">
          <label className="slider-label" htmlFor="diversity">
            Safe
            <input
              id="diversity"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={diversity}
              onChange={(e) => setDiversity(Number(e.target.value))}
              onMouseUp={() => {
                loadRail(diversity);
                save({ diversity });
              }}
              onTouchEnd={() => {
                loadRail(diversity);
                save({ diversity });
              }}
              onKeyUp={() => {
                loadRail(diversity);
                save({ diversity });
              }}
            />
            Adventurous
          </label>
          <span className="micro">Diversity {Math.round(diversity * 100)} percent</span>
        </div>
      )}

      <div className="filter-row">
        <button
          type="button"
          className={`chip ${!browsing ? "active" : ""}`}
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
        <span className="filter-divider" aria-hidden="true" />
        {SMART_FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`chip ghost ${smart === f.id ? "active" : ""}`}
            onClick={() => syncParams({ s: smart === f.id ? "" : f.id })}
          >
            {f.label}
          </button>
        ))}
      </div>

      {expanded.length > 0 && (
        <p className="expanded-terms">
          Semantic mode also searched for{" "}
          {expanded.slice(0, 6).map((t) => (
            <span key={t} className="term-chip">
              {t}
            </span>
          ))}
        </p>
      )}

      {continueWatching.length > 0 && !browsing && (
        <section className="recent-rail">
          <h2>Continue watching</h2>
          <div className="continue-row">
            {continueWatching.map((entry) => (
              <ContinueCard key={entry.anime_id} entry={entry} token={token} onTick={tickContinue} />
            ))}
          </div>
        </section>
      )}

      {almost.length > 0 && !browsing && (
        <section className="recent-rail">
          <h2>You almost clicked these</h2>
          <p className="micro">Titles you lingered on and scrolled past anyway.</p>
          <div className="tile-grid compact">
            {almost.slice(0, 6).map((row, i) => (
              <AnimeCard
                key={row.anime.id}
                anime={row.anime}
                token={token}
                surface="almost"
                position={i}
                why={row.why}
                onDismiss={dismiss}
                onAdd={addToShelf}
                selected={selectedId === row.anime.id}
              />
            ))}
          </div>
        </section>
      )}

      {recent.length > 0 && !browsing && (
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
        <p className="pad">Loading vault...</p>
      ) : gridItems.length === 0 && !busy ? (
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
          {(browsing ? items : rail?.items || items.map((a) => ({ anime: a, why: null }))).map(
            (row, i) => {
              const anime = row.anime || row;
              return (
                <AnimeCard
                  key={anime.id}
                  anime={anime}
                  token={token}
                  onRate={rate}
                  onDismiss={dismiss}
                  onAdd={addToShelf}
                  why={row.why}
                  surface={browsing ? "search" : "discover"}
                  position={i}
                  selected={selectedId === anime.id}
                />
              );
            }
          )}
        </section>
      )}

      {(genre || type) && !smart ? (
        <div className="pager">
          <button
            type="button"
            className="ghost-btn"
            disabled={page <= 1 || busy}
            onClick={() => load({ g: genre, t: type, p: page - 1 })}
          >
            Previous
          </button>
          <span>Page {page}</span>
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

      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
