import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../icons";
import { AnimeCard } from "../components/AnimeCard";
import { EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { useGridKeys } from "../lib/useGridKeys";
import { usePrefs } from "../lib/prefs";
import { sfx } from "../lib/sound";

const VARIANTS = [
  { id: "hybrid", label: "Hybrid", blurb: "Content neighbours blended with people who rate like you" },
  { id: "content", label: "Content", blurb: "Pure TF-IDF similarity to what you rated highly" },
  { id: "collaborative", label: "Neighbours", blurb: "Only what correlated accounts scored well" },
  { id: "popularity", label: "Popular", blurb: "No personalization at all, the control group" },
];

export function Recommendations() {
  const { token, user, loading } = useAuth();
  const { prefs, save, flag } = usePrefs();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [cached, setCached] = useState(false);
  const [variant, setVariant] = useState(prefs.ranking_variant || "hybrid");
  const [diversity, setDiversity] = useState(prefs.diversity ?? 0.35);
  const [nextUp, setNextUp] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [showMetrics, setShowMetrics] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    setVariant(prefs.ranking_variant || "hybrid");
    setDiversity(prefs.diversity ?? 0.35);
  }, [prefs.ranking_variant, prefs.diversity]);

  const refresh = useCallback(
    async (nextVariant = variant, nextDiversity = diversity) => {
      if (!token) return;
      setBusy(true);
      try {
        const data = await api(
          `/api/recommendations?limit=24&variant=${nextVariant}&diversity=${nextDiversity}`,
          { token }
        );
        setRows(data.recommendations);
        setCached(data.cached);
      } catch (err) {
        toast.say(err.message);
      } finally {
        setBusy(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, variant, diversity]
  );

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token) return;
    api("/api/insights/next-up?limit=6", { token })
      .then(setNextUp)
      .catch(() => setNextUp([]));
    api("/api/signals/summary", { token })
      .then(setMetrics)
      .catch(() => setMetrics(null));
  }, [token]);

  const items = rows.map((r) => r.anime);

  const { selectedId } = useGridKeys({
    items,
    enabled: flag("keyboard_mode"),
    onOpen: (a) => navigate(`/anime/${a.id}`),
    onRate: (a, score) => rate(a.id, score),
    onDismiss: (a, reason) => dismiss(a, reason),
  });

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading your vault...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  async function rate(animeId, score) {
    try {
      await api("/api/ratings", { method: "POST", token, body: { anime_id: animeId, score } });
      sfx.rate();
      toast.say(`Saved ${score} out of 10`);
      await refresh();
    } catch (err) {
      toast.say(err.message);
    }
  }

  async function dismiss(anime, reason) {
    try {
      await api("/api/signals/feedback", {
        method: "POST",
        token,
        body: { anime_id: anime.id, reason },
      });
      setRows((prev) => prev.filter((r) => r.anime.id !== anime.id));
      toast.say("Hidden, and the next batch will lean away from it");
    } catch (err) {
      toast.say(err.message);
    }
  }

  async function pickVariant(next) {
    setVariant(next);
    await save({ ranking_variant: next });
    await refresh(next, diversity);
  }

  const active = VARIANTS.find((v) => v.id === variant);

  return (
    <Shell mascot={busy ? "thinking" : "idle"}>
      <section className="panel-head">
        <div>
          <p className="eyebrow">For You</p>
          <h1>Picks for {user.username}</h1>
          <p className="lede">
            {active?.blurb}
            {cached ? " · served from Redis" : " · scored just now"}
          </p>
        </div>
        <button type="button" className="btn" onClick={() => refresh()} disabled={busy}>
          <Icon name="spark" size={16} /> Refresh
        </button>
      </section>

      <div className="rail-controls wrap">
        <div className="filter-row slim">
          <span className="micro">Ranking</span>
          {VARIANTS.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`chip ghost ${variant === v.id ? "active" : ""}`}
              onClick={() => pickVariant(v.id)}
            >
              {v.label}
            </button>
          ))}
        </div>
        <label className="slider-label" htmlFor="rec-diversity">
          Safe
          <input
            id="rec-diversity"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={diversity}
            onChange={(e) => setDiversity(Number(e.target.value))}
            onMouseUp={() => {
              save({ diversity });
              refresh(variant, diversity);
            }}
            onTouchEnd={() => {
              save({ diversity });
              refresh(variant, diversity);
            }}
            onKeyUp={() => {
              save({ diversity });
              refresh(variant, diversity);
            }}
          />
          Adventurous
        </label>
        <button
          type="button"
          className="ghost-btn tiny"
          onClick={() => setShowMetrics((v) => !v)}
          aria-expanded={showMetrics}
        >
          {showMetrics ? "Hide" : "Show"} signal panel
        </button>
      </div>

      {showMetrics && metrics && (
        <section className="metrics-panel">
          <h2>What the ranker is reading</h2>
          <div className="metric-grid">
            <div>
              <strong>{metrics.views.toLocaleString()}</strong>
              <span>posters seen (30 days)</span>
            </div>
            <div>
              <strong>{metrics.clicks.toLocaleString()}</strong>
              <span>opened</span>
            </div>
            <div>
              <strong>{(metrics.click_through_rate * 100).toFixed(1)}%</strong>
              <span>click through</span>
            </div>
            <div>
              <strong>{Math.round(metrics.average_dwell_ms)} ms</strong>
              <span>average dwell</span>
            </div>
            <div>
              <strong>{metrics.hidden_titles}</strong>
              <span>hidden titles</span>
            </div>
            <div>
              <strong>{metrics.dismissals}</strong>
              <span>dismissals</span>
            </div>
          </div>
          {Object.keys(metrics.dampened_genres || {}).length > 0 && (
            <p className="micro">
              Currently damped:{" "}
              {Object.entries(metrics.dampened_genres)
                .map(([tag, n]) => `${tag} (${n})`)
                .join(", ")}
            </p>
          )}
          <p className="micro">
            Surfaces:{" "}
            {Object.entries(metrics.surfaces || {})
              .map(([surface, n]) => `${surface} ${n}`)
              .join(" · ")}
          </p>
        </section>
      )}

      {nextUp.length > 0 && (
        <section className="recent-rail">
          <h2>What people watched next</h2>
          <p className="micro">
            A bigram over the order accounts on this instance finished things in.
          </p>
          <div className="tile-grid compact">
            {nextUp.map((row, i) => (
              <AnimeCard
                key={row.anime.id}
                anime={row.anime}
                token={token}
                reason={row.reason}
                method={row.method}
                surface="for_you"
                position={i}
                onDismiss={dismiss}
              />
            ))}
          </div>
        </section>
      )}

      {rows.length === 0 ? (
        <EmptyState
          title="Rate a few titles first"
          body="Score shows you liked, or take the sixty second taste quiz and skip the cold start."
          action={
            <div className="hero-actions">
              <Link className="btn" to="/quiz">
                Take the quiz
              </Link>
              <Link className="ghost-btn" to="/">
                Go discover
              </Link>
            </div>
          }
        />
      ) : (
        <section className="tile-grid">
          {rows.map((row, i) => (
            <AnimeCard
              key={row.anime.id}
              anime={row.anime}
              token={token}
              reason={row.reason}
              method={row.method}
              onRate={rate}
              onDismiss={dismiss}
              surface="for_you"
              position={i}
              selected={selectedId === row.anime.id}
            />
          ))}
        </section>
      )}

      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
