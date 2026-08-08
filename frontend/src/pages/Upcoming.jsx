import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { CharacterSpot, EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { Icon } from "../icons";
import { airTime, countdown, plainDate, relativeDay, titleInitial } from "../lib/format";
import { usePrefs } from "../lib/prefs";

const TABS = [
  { id: "radar", label: "Your radar", hint: "Airing and announced titles that touch your shelf" },
  { id: "schedule", label: "This week", hint: "Episodes landing in the next seven days" },
  { id: "upcoming", label: "Upcoming", hint: "Announced, not yet aired" },
];

const ENDPOINTS = {
  radar: "/api/live/radar?limit=40",
  schedule: "/api/live/schedule?days=7&limit=60",
  upcoming: "/api/live/upcoming?limit=48",
};

/**
 * One airing title. The countdown is rendered from `seconds_until`, which the
 * server computed, so a laptop with a wrong clock still shows the right gap.
 */
function AiringCard({ item, token, onAdd }) {
  const { anime } = item;
  const soon = countdown(item.seconds_until);
  const exact = airTime(item.next_episode_at);

  return (
    <article className="airing-card">
      <Link to={`/anime/${anime.id}`} className="airing-poster">
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
            <span>{titleInitial(anime.title)}</span>
          </div>
        )}
        {soon && (
          <span className={`airing-pill ${item.seconds_until < 86400 ? "imminent" : ""}`}>
            {soon}
          </span>
        )}
      </Link>

      <div className="airing-body">
        <h3>
          <Link to={`/anime/${anime.id}`}>{anime.title}</Link>
        </h3>

        {item.next_episode ? (
          <p className="meta">
            Episode {item.next_episode}
            {item.episodes_total ? ` of ${item.episodes_total}` : ""}
            {exact ? ` · ${exact}` : ""}
          </p>
        ) : (
          <p className="meta">
            {item.start_date
              ? `Starts ${plainDate(item.start_date)}`
              : "Release date not announced"}
          </p>
        )}

        {item.why && <p className="reason why">{item.why}</p>}

        {item.in_library ? (
          <span className="airing-tag on-shelf">
            <Icon name="shelf" size={13} /> on your shelf
          </span>
        ) : (
          token && (
            <button type="button" className="ghost-btn tiny" onClick={() => onAdd(item)}>
              Add to plan to watch
            </button>
          )
        )}
      </div>
    </article>
  );
}

export function Upcoming() {
  const { token, user, loading } = useAuth();
  const { flag } = usePrefs();
  const [tab, setTab] = useState("radar");
  const [data, setData] = useState({ items: [], total: 0 });
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();

  const live = flag("live_data", true);

  const loadStatus = useCallback(() => {
    api("/api/live/status", { token })
      .then(setStatus)
      .catch(() => setStatus(null));
  }, [token]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (!live || !token) return;
    setBusy(true);
    setError("");
    api(ENDPOINTS[tab], { token })
      .then((d) => setData(d))
      .catch((err) => {
        setData({ items: [], total: 0 });
        setError(err.message);
      })
      .finally(() => setBusy(false));
  }, [tab, live, token]);

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      const result = await api("/api/live/refresh", { method: "POST", token });
      const added = (result.releasing?.created || 0) + (result.upcoming?.created || 0);
      toast.say(
        `Pulled ${result.releasing?.seen || 0} airing and ${result.upcoming?.seen || 0} upcoming` +
          (added ? `, ${added} new to this vault` : "")
      );
      loadStatus();
      const fresh = await api(ENDPOINTS[tab], { token });
      setData(fresh);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function addToShelf(item) {
    try {
      await api(`/api/library/${item.anime.id}`, {
        method: "PUT",
        token,
        body: { status: "plan_to_watch" },
      });
      setData((prev) => ({
        ...prev,
        items: prev.items.map((row) =>
          row.anime.id === item.anime.id
            ? { ...row, in_library: true, library_status: "plan_to_watch" }
            : row
        ),
      }));
      toast.say(`${item.anime.title} is on your shelf`);
    } catch (err) {
      toast.say(err.message);
    }
  }

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  const active = TABS.find((t) => t.id === tab);

  return (
    <Shell mascot={busy ? "searching" : "idle"}>
      <section className="panel-head with-spot">
        <div>
          <p className="eyebrow">Upcoming</p>
          <h1>What is airing next</h1>
          <p className="lede">
            Live airing schedules, pulled from AniList and kept in your own database.
            Countdowns are exact to the minute.
          </p>
        </div>
        <div className="panel-head-actions">
          <CharacterSpot mood="watching" caption="On the lookout" />
          {live && (
            <button type="button" className="btn compact" onClick={refresh} disabled={busy}>
              <Icon name="broadcast" size={16} /> {busy ? "Checking..." : "Check for updates"}
            </button>
          )}
        </div>
      </section>

      {!live ? (
        <EmptyState
          title="Live data is switched off"
          body="An operator has switched live data off for this instance. Turn the live_data flag back on to use this page."
          action={
            <Link className="btn" to="/settings">
              Open settings
            </Link>
          }
        />
      ) : (
        <>
          <div className="filter-row" role="tablist" aria-label="Upcoming views">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className={`chip ${tab === t.id ? "active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <p className="micro">{active?.hint}</p>

          {status?.refreshed_at && (
            <p className={`micro live-stamp ${data.stale ? "stale" : ""}`}>
              <Icon name="broadcast" size={13} /> Last checked {relativeDay(status.refreshed_at)}
              {" · "}
              {status.releasing} airing, {status.upcoming} upcoming in this vault
              {data.stale && " · worth refreshing"}
            </p>
          )}

          {error && (
            <p className="toast" role="alert">
              {error}
            </p>
          )}

          {busy && data.items.length === 0 ? (
            <div className="skeleton-grid" aria-hidden="true">
              {Array.from({ length: 10 }, (_, i) => (
                <div className="skeleton-card" key={i}>
                  <div className="skeleton poster" />
                  <div className="skeleton line" />
                  <div className="skeleton line short" />
                </div>
              ))}
            </div>
          ) : !busy && data.items.length === 0 ? (
            <EmptyState
              title={
                status?.refreshed_at ? "Nothing here yet" : "No live data pulled yet"
              }
              body={
                status?.refreshed_at
                  ? "Rate and finish a few more titles and your radar fills in. The other two tabs do not need any history."
                  : "Hit Check for updates and Kura will pull the current airing schedule into your vault."
              }
            />
          ) : (
            <section className="airing-grid stagger">
              {data.items.map((item) => (
                <AiringCard
                  key={item.anime.id}
                  item={item}
                  token={token}
                  onAdd={addToShelf}
                />
              ))}
            </section>
          )}
        </>
      )}

      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
