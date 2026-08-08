import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { AnimeCard } from "../components/AnimeCard";
import { EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { STATUS_LABELS, hours, progressPct } from "../lib/format";
import { sfx } from "../lib/sound";

export function Shelf() {
  const { token, user, loading } = useAuth();
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("recent");
  const toast = useToast();

  const load = useCallback(async () => {
    const path = filter === "all" ? "/api/library" : `/api/library?status=${filter}`;
    setItems(await api(path, { token }));
  }, [filter, token]);

  useEffect(() => {
    if (token) load().catch((e) => toast.say(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, filter]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  async function remove(id) {
    await api(`/api/watchlist/${id}`, { method: "DELETE", token });
    setItems((prev) => prev.filter((a) => a.anime_id !== id));
    toast.say("Removed from shelf");
  }

  async function setStatus(id, status) {
    await api(`/api/library/${id}`, { method: "PUT", token, body: { status } });
    toast.say(`Moved to ${STATUS_LABELS[status] || status}`);
    await load();
  }

  async function tick(id) {
    const data = await api(`/api/library/${id}/tick`, { method: "POST", token });
    if (data.status === "completed") sfx.complete();
    else sfx.tick();
    await load();
  }

  const sorted = [...items].sort((a, b) => {
    if (sort === "title") return (a.anime?.title || "").localeCompare(b.anime?.title || "");
    if (sort === "progress") return progressPct(b) - progressPct(a);
    if (sort === "time") return (b.watch_seconds || 0) - (a.watch_seconds || 0);
    return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
  });

  const trackedHours = items.reduce((sum, r) => sum + (r.watch_seconds || 0), 0) / 3600;

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Shelf</p>
          <h1>Your list</h1>
          <p className="lede">
            Plan, watch, hold, drop, or finish. Tracked on this machine against your account.
          </p>
        </div>
        <span className="head-meta">
          {items.length} titles · {hours(trackedHours)} tracked
        </span>
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
        <label className="sort-label" style={{ marginLeft: "auto" }}>
          Sort
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="recent">Recently touched</option>
            <option value="progress">Closest to done</option>
            <option value="time">Most time spent</option>
            <option value="title">Title</option>
          </select>
        </label>
      </div>

      {sorted.length === 0 ? (
        <EmptyState
          title="Shelf is empty"
          body="On any title page, add to shelf or start watching to queue it here."
          action={
            <Link className="btn" to="/">
              Browse catalog
            </Link>
          }
        />
      ) : (
        <div className="continue-row">
          {sorted.map((entry) => (
            <article className="watch-card" key={entry.anime_id}>
              <Link to={`/anime/${entry.anime_id}`}>
                <img
                  src={entry.anime?.image_url || "/poster-fallback.png"}
                  alt=""
                  onError={(e) => {
                    e.currentTarget.onerror = null;
                    e.currentTarget.src = "/poster-fallback.png";
                  }}
                />
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
                  {entry.rewatches > 0 ? ` · ${entry.rewatches} rewatch` : ""}
                </p>
                <div className="progress-bar" aria-hidden="true">
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
                  <button type="button" className="btn compact" onClick={() => tick(entry.anime_id)}>
                    +1 ep
                  </button>
                )}
                <button
                  type="button"
                  className="ghost-btn danger"
                  onClick={() => remove(entry.anime_id)}
                >
                  Remove
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}

export function Library() {
  const { token, user, loading } = useAuth();
  const [rows, setRows] = useState([]);
  const [sort, setSort] = useState("score");

  useEffect(() => {
    if (!token) return;
    api("/api/ratings/me", { token })
      .then(setRows)
      .catch(() => setRows([]));
  }, [token]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
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
          <p className="lede">
            These scores train the hybrid ranker, and recent ones count for more than old ones.
          </p>
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
          body="Rate titles from Discover or a detail page. Use 7 to 10 for shows you want more of."
          action={
            <Link className="btn" to="/">
              Start rating
            </Link>
          }
        />
      ) : (
        <section className="tile-grid">
          {sorted.map((r, i) =>
            r.anime ? (
              <AnimeCard
                key={r.anime_id}
                anime={r.anime}
                userScore={r.score}
                surface="library"
                position={i}
              />
            ) : null
          )}
        </section>
      )}
    </Shell>
  );
}
