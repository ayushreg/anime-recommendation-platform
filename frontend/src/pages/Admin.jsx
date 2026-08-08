import React, { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Bar, StatTile } from "../components/Charts";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { hours, relativeDay } from "../lib/format";

export function Admin() {
  const { token, user, loading } = useAuth();
  const [data, setData] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [events, setEvents] = useState([]);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    if (!token) return;
    const [overview, tl, log] = await Promise.all([
      api("/api/admin/overview", { token }),
      api("/api/admin/impressions/timeline?days=14", { token }),
      api("/api/vault/events?limit=40", { token }),
    ]);
    setData(overview);
    setTimeline(tl.days || []);
    setEvents(log.events || []);
  }, [token]);

  useEffect(() => {
    if (token) load().catch((e) => toast.say(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (!data) {
    return (
      <Shell>
        <p className="pad">{toast.message || "Reading instance..."}</p>
      </Shell>
    );
  }

  async function toggle(name, enabled) {
    const next = await api("/api/admin/flags", {
      method: "POST",
      token,
      body: { name, enabled },
    });
    setData((prev) => ({ ...prev, flags: next }));
    toast.say(`${name.replace(/_/g, " ")} is now ${enabled ? "on" : "off"}`);
  }

  async function refit() {
    setBusy(true);
    try {
      await api("/api/admin/refit", { method: "POST", token });
      toast.say("Models refitted");
      await load();
    } catch (err) {
      toast.say(err.message);
    } finally {
      setBusy(false);
    }
  }

  const peakQuery = Math.max(...data.top_queries.map((q) => q.hits), 1);
  const peakDay = Math.max(...timeline.map((d) => (d.view || 0) + (d.click || 0)), 1);

  return (
    <Shell mascot="thinking">
      <section className="panel-head">
        <div>
          <p className="eyebrow">Instance</p>
          <h1>Operator dashboard</h1>
          <p className="lede">
            It is your machine, so nothing here is hidden from you. Same numbers Prometheus scrapes
            at /metrics.
          </p>
        </div>
        <button type="button" className="btn" onClick={refit} disabled={busy}>
          {busy ? "Refitting..." : "Refit models now"}
        </button>
      </section>

      <div className="stat-row">
        <StatTile label="Titles" value={data.anime_count.toLocaleString()} />
        <StatTile label="Accounts" value={data.user_count} />
        <StatTile label="Ratings" value={data.rating_count.toLocaleString()} />
        <StatTile label="Impressions" value={data.impression_count.toLocaleString()} />
        <StatTile label="Watch sessions" value={data.session_count} sub={`${data.active_sessions} live`} />
        <StatTile label="Attention" value={hours(data.watch_hours)} />
        <StatTile
          label="Cache hit rate"
          value={`${Math.round((data.cache.hit_rate || 0) * 100)}%`}
          sub={`${data.cache.hits} hits, ${data.cache.misses} misses`}
        />
        <StatTile
          label="Embeddings"
          value={data.embeddings.ready ? `${data.embeddings.dimensions}d` : "cold"}
          sub={`${(data.embeddings.vectors || 0).toLocaleString()} vectors`}
        />
      </div>

      <div className="insight-split">
        <section className="insight-block">
          <h2>Top searches</h2>
          {data.top_queries.length === 0 ? (
            <p className="micro">No searches logged yet.</p>
          ) : (
            <div className="bar-list">
              {data.top_queries.map((q) => (
                <Bar key={q.query} label={q.query} value={q.hits} max={peakQuery} />
              ))}
            </div>
          )}
        </section>

        <section className="insight-block">
          <h2>Signal volume (14 days)</h2>
          {timeline.length === 0 ? (
            <p className="micro">Nothing logged in that window.</p>
          ) : (
            <div className="bar-list">
              {timeline.map((d) => (
                <Bar
                  key={d.day}
                  label={d.day}
                  value={(d.view || 0) + (d.click || 0)}
                  max={peakDay}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="insight-block">
        <h2>Feature flags</h2>
        <p className="micro">
          Writes to feature_flags.local.json next to the API so the choice survives a restart.
        </p>
        <div className="flag-toggle-grid">
          {Object.entries(data.flags).map(([name, on]) => (
            <label key={name} className={`flag-toggle ${on ? "on" : "off"}`}>
              <input type="checkbox" checked={on} onChange={(e) => toggle(name, e.target.checked)} />
              <span>{name.replace(/_/g, " ")}</span>
            </label>
          ))}
        </div>
      </section>

      <section className="insight-block">
        <h2>Event log</h2>
        <p className="micro">
          Appended as JSON lines so your own scripts can tail it. Set KURA_WEBHOOK_URL and the same
          payload gets POSTed to your local endpoint.
        </p>
        {events.length === 0 ? (
          <p className="micro">Nothing logged yet.</p>
        ) : (
          <ul className="event-log">
            {events.map((e, i) => (
              <li key={`${e.ts}-${i}`}>
                <code>{e.kind}</code>
                <span>{e.detail || `anime ${e.anime_id ?? "n/a"}`}</span>
                <em>{relativeDay(e.ts)}</em>
              </li>
            ))}
          </ul>
        )}
      </section>
      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
