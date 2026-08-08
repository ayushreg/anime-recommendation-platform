import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../icons";
import { AnimeCard } from "../components/AnimeCard";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { WatchHUD } from "../components/WatchHUD";
import { STATUS_LABELS, clock, hours, relativeDay } from "../lib/format";
import { usePrefs } from "../lib/prefs";
import { sfx } from "../lib/sound";
import { applyTint, extractTint } from "../lib/tint";
import { useWatchSession } from "../lib/useWatchSession";

function MarkerEditor({ markers, onSave, runtime }) {
  const [draft, setDraft] = useState(markers);
  useEffect(() => setDraft(markers), [markers]);
  if (!draft) return null;

  const field = (key, label) => (
    <label key={key}>
      {label}
      <input
        type="number"
        min="0"
        max="7200"
        value={draft[key]}
        onChange={(e) => setDraft({ ...draft, [key]: Number(e.target.value) })}
      />
      <small>{clock(draft[key])}</small>
    </label>
  );

  return (
    <div className="marker-editor">
      <p className="micro">
        Rough intro and outro timestamps. The timer uses them to estimate how much of an episode is
        actually story, which keeps auto tick honest on shows with a ninety second opening.
      </p>
      <div className="marker-fields">
        {field("intro_start_s", "Intro starts")}
        {field("intro_end_s", "Intro ends")}
        {field("outro_start_s", "Outro starts")}
      </div>
      <div className="hero-actions">
        <button type="button" className="btn compact" onClick={() => onSave(draft)}>
          Save markers
        </button>
        <span className="micro">Episode runtime about {Math.round(runtime / 60)} min</span>
      </div>
    </div>
  );
}

export function Detail() {
  const { id } = useParams();
  const { token } = useAuth();
  const { prefs, flag } = usePrefs();
  const heroRef = useRef(null);
  const [anime, setAnime] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [franchise, setFranchise] = useState(null);
  const [myScore, setMyScore] = useState(null);
  const [entry, setEntry] = useState(null);
  const [note, setNote] = useState({ body: "", is_shared: false });
  const [noteDirty, setNoteDirty] = useState(false);
  const [markers, setMarkers] = useState(null);
  const [showMarkers, setShowMarkers] = useState(false);
  const [collections, setCollections] = useState([]);
  const [timerOpen, setTimerOpen] = useState(false);
  const toast = useToast();

  const timer = useWatchSession({
    animeId: id,
    token,
    idleTimeout: prefs.idle_timeout_seconds || 180,
    enabled: flag("watch_timer"),
  });

  const refreshLibrary = useCallback(async () => {
    if (!token) return;
    const rows = await api("/api/library", { token });
    setEntry(rows.find((r) => r.anime_id === Number(id)) || null);
  }, [token, id]);

  useEffect(() => {
    api(`/api/anime/${id}`)
      .then(setAnime)
      .catch((err) => toast.say(err.message));
    api(`/api/anime/${id}/similar`)
      .then(setSimilar)
      .catch(() => {});
    api(`/api/discover/franchise/${id}`)
      .then((d) => setFranchise(d.entries.length > 1 ? d : null))
      .catch(() => setFranchise(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!anime || !prefs.poster_tint || !flag("poster_tint")) return;
    let alive = true;
    extractTint(anime, anime.image_url).then((tint) => {
      if (alive) applyTint(heroRef.current, tint);
    });
    return () => {
      alive = false;
    };
  }, [anime, prefs.poster_tint, flag]);

  useEffect(() => {
    if (!token) {
      setEntry(null);
      setMyScore(null);
      return;
    }
    api("/api/ratings/me", { token })
      .then((rows) => setMyScore(rows.find((r) => r.anime_id === Number(id))?.score ?? null))
      .catch(() => {});
    api(`/api/notes/${id}`, { token })
      .then((n) => {
        setNote(n);
        setNoteDirty(false);
      })
      .catch(() => {});
    api(`/api/watch/markers/${id}`, { token })
      .then(setMarkers)
      .catch(() => {});
    api("/api/collections", { token })
      .then(setCollections)
      .catch(() => setCollections([]));
    refreshLibrary().catch(() => {});
  }, [token, id, refreshLibrary]);

  useEffect(() => {
    if (timer.lastTick > 0) {
      sfx.tick();
      toast.say(`Timer moved you to episode ${timer.progress}`);
      refreshLibrary().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timer.lastTick]);

  async function rate(score) {
    if (!token) return toast.say("Sign in to rate");
    await api("/api/ratings", { method: "POST", token, body: { anime_id: Number(id), score } });
    setMyScore(score);
    sfx.rate();
    toast.say(`Rated ${score} out of 10 and marked completed`);
    await refreshLibrary();
    return undefined;
  }

  async function setStatus(status) {
    if (!token) return toast.say("Sign in to track watching");
    const data = await api(`/api/library/${id}`, {
      method: "PUT",
      token,
      body: { status, progress: entry?.progress ?? 0 },
    });
    setEntry(data);
    toast.say(`Status: ${STATUS_LABELS[data.status] || data.status}`);
    return undefined;
  }

  async function tick() {
    if (!token) return toast.say("Sign in to track episodes");
    const data = await api(`/api/library/${id}/tick`, { method: "POST", token });
    if (data.status === "completed") sfx.complete();
    else sfx.tick();
    toast.say(
      data.status === "completed" ? "Finished. Marked completed" : `Now on episode ${data.progress}`
    );
    await refreshLibrary();
    return undefined;
  }

  async function toggleShelf() {
    if (!token) return toast.say("Sign in to use your shelf");
    if (entry) {
      await api(`/api/watchlist/${id}`, { method: "DELETE", token });
      setEntry(null);
      toast.say("Removed from shelf");
    } else {
      await setStatus("plan_to_watch");
    }
    return undefined;
  }

  async function startRewatch() {
    await api(`/api/watch/rewatch/${id}`, { method: "POST", token });
    toast.say("Rewatch started. Your original finish date stays put.");
    await refreshLibrary();
  }

  async function saveNote() {
    await api(`/api/notes/${id}`, { method: "PUT", token, body: note });
    setNoteDirty(false);
    toast.say("Note saved. Private unless you share it.");
  }

  async function saveMarkers(draft) {
    const saved = await api(`/api/watch/markers/${id}`, { method: "PUT", token, body: draft });
    setMarkers(saved);
    toast.say("Markers saved");
  }

  async function addToCollection(collectionId) {
    if (!collectionId) return;
    await api(`/api/collections/${collectionId}/items`, {
      method: "POST",
      token,
      body: { anime_id: Number(id) },
    });
    toast.say("Added to that list");
  }

  if (!anime) {
    return (
      <Shell>
        <p className="pad">{toast.message || "Loading title..."}</p>
      </Shell>
    );
  }

  const runtime = (anime.duration_minutes || 24) * 60;

  return (
    <Shell mascot={timer.running ? "watching" : "idle"}>
      <section className="detail-hero" ref={heroRef}>
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
            {[
              anime.type,
              anime.season ? `${anime.season} ${anime.year || ""}`.trim() : anime.year,
              anime.episodes ? `${anime.episodes} eps` : null,
              anime.duration_minutes ? `${anime.duration_minutes} min each` : null,
              anime.status,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <div className="tag-row">
            {(anime.genres || "")
              .split(",")
              .map((g) => g.trim())
              .filter(Boolean)
              .slice(0, 8)
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
            {flag("watch_timer") && token && (
              <button
                type="button"
                className="ghost-btn"
                onClick={() => {
                  setTimerOpen(true);
                  if (!timer.session) timer.start();
                }}
              >
                <Icon name="play" size={16} /> Session timer
              </button>
            )}
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
              <span className="score-pill you">
                Your score <strong>{myScore}</strong>
              </span>
            )}
          </div>

          {timerOpen && flag("watch_timer") && token && (
            <WatchHUD
              anime={anime}
              timer={timer}
              compact
              autoTick={prefs.auto_tick}
              onStart={timer.start}
              onTickNow={async () => {
                await tick();
                timer.dismissPrompt();
              }}
              onStop={async () => {
                await timer.stop();
                setTimerOpen(false);
                await refreshLibrary();
                toast.say("Session closed and saved");
              }}
            />
          )}

          {entry && (
            <div className="rate-panel">
              <span>
                Tracking · {STATUS_LABELS[entry.status] || entry.status}
                {anime.episodes
                  ? ` · Ep ${entry.progress || 0}/${anime.episodes}`
                  : entry.progress
                    ? ` · Ep ${entry.progress}`
                    : ""}
                {entry.rewatches > 0 ? ` · ${entry.rewatches} rewatch` : ""}
                {entry.watch_seconds ? ` · ${hours(entry.watch_seconds / 3600)} tracked` : ""}
              </span>
              {entry.completed_at && (
                <p className="micro">First finished {relativeDay(entry.completed_at)}</p>
              )}
              <div className="progress-bar" aria-hidden="true">
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
              <div className="panel-row">
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
                {entry.status === "completed" && !entry.is_rewatching && (
                  <button type="button" className="ghost-btn" onClick={startRewatch}>
                    Start a rewatch
                  </button>
                )}
                {collections.length > 0 && (
                  <label className="sort-label">
                    Add to list
                    <select
                      className="status-select"
                      value=""
                      onChange={(e) => addToCollection(Number(e.target.value))}
                    >
                      <option value="">Choose a list</option>
                      {collections.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.emoji} {c.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
            </div>
          )}

          <div className="rate-panel">
            <span>Rate (auto-completes)</span>
            <div className="rate-strip large" role="group" aria-label={`Rate ${anime.title}`}>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((s) => (
                <button
                  key={s}
                  type="button"
                  className={myScore === s ? "active" : ""}
                  aria-label={`Rate ${s} out of 10`}
                  aria-pressed={myScore === s}
                  onClick={() => rate(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {token && (
            <div className="rate-panel">
              <span>Private note</span>
              <textarea
                className="note-box"
                rows={3}
                value={note.body}
                placeholder="Where you left off, who recommended it, whatever you want to remember."
                onChange={(e) => {
                  setNote({ ...note, body: e.target.value });
                  setNoteDirty(true);
                }}
              />
              <div className="panel-row">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={note.is_shared}
                    onChange={(e) => {
                      setNote({ ...note, is_shared: e.target.checked });
                      setNoteDirty(true);
                    }}
                  />
                  Let friends see this note
                </label>
                <button
                  type="button"
                  className="btn compact"
                  onClick={saveNote}
                  disabled={!noteDirty}
                >
                  Save note
                </button>
                {flag("watch_timer") && (
                  <button
                    type="button"
                    className="ghost-btn tiny"
                    onClick={() => setShowMarkers((v) => !v)}
                    aria-expanded={showMarkers}
                  >
                    {showMarkers ? "Hide" : "Edit"} intro and outro
                  </button>
                )}
              </div>
              {showMarkers && (
                <MarkerEditor markers={markers} onSave={saveMarkers} runtime={runtime} />
              )}
            </div>
          )}
        </div>
      </section>

      {franchise && (
        <>
          <h2 className="section-title">
            <Icon name="stack" size={22} /> Rest of the franchise
          </h2>
          <section className="tile-grid compact">
            {franchise.entries
              .filter((e) => e.id !== anime.id)
              .slice(0, 8)
              .map((item, i) => (
                <AnimeCard key={item.id} anime={item} surface="franchise" position={i} />
              ))}
          </section>
        </>
      )}

      <h2 className="section-title">
        <Icon name="similar" size={22} /> Similar titles
      </h2>
      <section className="tile-grid">
        {similar.map((item, i) => (
          <AnimeCard key={item.id} anime={item} surface="similar" position={i} token={token} />
        ))}
      </section>
      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
