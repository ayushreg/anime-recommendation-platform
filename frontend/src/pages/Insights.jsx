import React, { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Bar, StatTile, StreakHeatmap, TasteRadar } from "../components/Charts";
import { EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { hours } from "../lib/format";

export function Insights() {
  const { token, user, loading } = useAuth();
  const [streak, setStreak] = useState(null);
  const [vault, setVault] = useState(null);
  const [taste, setTaste] = useState([]);
  const [neighbours, setNeighbours] = useState([]);
  const [attention, setAttention] = useState([]);

  useEffect(() => {
    if (!token) return;
    api("/api/watch/streak?days=182", { token })
      .then(setStreak)
      .catch(() => {});
    api("/api/insights/vault", { token })
      .then(setVault)
      .catch(() => {});
    api("/api/insights/taste?limit=8", { token })
      .then(setTaste)
      .catch(() => {});
    api("/api/insights/similar-users?limit=4", { token })
      .then(setNeighbours)
      .catch(() => {});
    api("/api/signals/attention?limit=10", { token })
      .then(setAttention)
      .catch(() => {});
  }, [token]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  const peakAttention = Math.max(...attention.map((a) => a.score), 0.0001);

  return (
    <Shell mascot="thinking">
      <section className="panel-head">
        <div>
          <p className="eyebrow">Insights</p>
          <h1>What your vault says about you</h1>
          <p className="lede">
            Every number here comes from rows this instance already holds. Nothing is sent anywhere.
          </p>
        </div>
      </section>

      {streak && (
        <section className="insight-block">
          <h2>Watch streak</h2>
          <div className="stat-row">
            <StatTile
              label="Current streak"
              value={`${streak.current_streak} days`}
              sub={streak.current_streak > 0 ? "keep it going" : "start one today"}
              tone={streak.current_streak >= 7 ? "hot" : ""}
            />
            <StatTile label="Longest run" value={`${streak.longest_streak} days`} />
            <StatTile label="This week" value={hours(streak.week_hours)} />
            <StatTile label="All time" value={hours(streak.total_hours)} />
          </div>
          <StreakHeatmap days={streak.days} weeks={26} />
        </section>
      )}

      {vault && (
        <section className="insight-block">
          <h2>Vault health</h2>
          <div className="stat-row">
            <StatTile label="Backlog" value={vault.backlog} sub={`${hours(vault.backlog_hours)} to clear`} />
            <StatTile label="In progress" value={vault.watching} />
            <StatTile label="Finished" value={vault.completed} />
            <StatTile
              label="Abandonment"
              value={`${Math.round(vault.abandonment_rate * 100)}%`}
              sub="dropped or on hold"
              tone={vault.abandonment_rate > 0.3 ? "warn" : ""}
            />
            <StatTile label="Average score" value={vault.average_score || "n/a"} />
            <StatTile label="Episodes" value={vault.episodes_watched.toLocaleString()} />
          </div>
          {vault.longest_backlog_title && (
            <p className="micro">
              Heaviest single commitment left: <strong>{vault.longest_backlog_title}</strong>
            </p>
          )}
        </section>
      )}

      <div className="insight-split">
        <section className="insight-block">
          <h2>Taste DNA</h2>
          <p className="micro">Weighted by ratings and watch time, not by what you scrolled past.</p>
          <TasteRadar slices={taste} />
        </section>

        <section className="insight-block">
          <h2>Attention scores</h2>
          <p className="micro">
            One number per title from views, clicks, dwell, watch seconds, and whether you finished.
          </p>
          {attention.length === 0 ? (
            <p className="micro">Browse a little and this fills in.</p>
          ) : (
            <div className="bar-list">
              {attention.map((row) => (
                <Bar
                  key={row.anime_id}
                  label={row.title || `#${row.anime_id}`}
                  value={Number((row.score / peakAttention).toFixed(2))}
                  max={1}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="insight-block">
        <h2>People who rate like you</h2>
        {neighbours.length === 0 ? (
          <EmptyState
            title="No neighbours yet"
            body="Once a couple of accounts on this instance rate the same shows you do, they show up here."
            action={
              <Link className="btn" to="/">
                Rate a few titles
              </Link>
            }
          />
        ) : (
          <div className="neighbour-grid">
            {neighbours.map((n) => (
              <article key={n.user_id} className="neighbour-card">
                <header>
                  <strong>{n.username}</strong>
                  <span className="score-pill">
                    {Math.round(n.affinity * 100)}% match
                  </span>
                </header>
                <p className="micro">{n.shared_titles} titles you have both rated</p>
                <div className="neighbour-picks">
                  {n.picks.map((p) => (
                    <Link key={p.id} to={`/anime/${p.id}`} title={p.title}>
                      <img src={p.image_url || "/poster-fallback.png"} alt={p.title} />
                    </Link>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </Shell>
  );
}
