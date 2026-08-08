import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { ContinueCard } from "../components/ContinueCard";
import { EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { WatchHUD } from "../components/WatchHUD";
import { hours } from "../lib/format";
import { usePrefs } from "../lib/prefs";
import { sfx } from "../lib/sound";
import { useWatchSession } from "../lib/useWatchSession";

const BUDGETS = [60, 120, 180, 300];

export function Watching() {
  const { token, user, loading } = useAuth();
  const { prefs, flag } = usePrefs();
  const [params, setParams] = useSearchParams();
  const [rows, setRows] = useState([]);
  const [active, setActive] = useState([]);
  const [tonight, setTonight] = useState(null);
  const [budget, setBudget] = useState(180);
  const [timerFor, setTimerFor] = useState(null);
  const toast = useToast();

  const view = params.get("view") || "queue";

  const timer = useWatchSession({
    animeId: timerFor?.id,
    token,
    idleTimeout: prefs.idle_timeout_seconds || 180,
    enabled: flag("watch_timer"),
  });

  const load = useCallback(async () => {
    if (!token) return;
    const data = await api("/api/library?status=watching", { token });
    setRows(data);
    api("/api/watch/active", { token })
      .then(setActive)
      .catch(() => setActive([]));
  }, [token]);

  useEffect(() => {
    if (token) load().catch((e) => toast.say(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token || view !== "tonight") return;
    api(`/api/watch/tonight?minutes=${budget}`, { token })
      .then(setTonight)
      .catch(() => setTonight(null));
  }, [token, view, budget]);

  useEffect(() => {
    if (timer.lastTick > 0) {
      sfx.tick();
      toast.say(`Timer moved you to episode ${timer.progress}`);
      load().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timer.lastTick]);

  // Picking a title opens its session. Kept above the auth guards so the hook
  // order never changes between renders.
  useEffect(() => {
    if (timerFor && !timer.session) timer.start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timerFor]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  async function tick(animeId) {
    const data = await api(`/api/library/${animeId}/tick`, { method: "POST", token });
    if (data.status === "completed") sfx.complete();
    else sfx.tick();
    toast.say(data.status === "completed" ? "Marked completed" : `Ep ${data.progress}`);
    await load();
  }

  async function startTimer(anime) {
    if (timer.session) await timer.stop();
    setTimerFor(anime);
  }

  const totalSeconds = rows.reduce((sum, r) => sum + (r.watch_seconds || 0), 0);

  return (
    <Shell mascot={timer.running ? "watching" : "idle"}>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Watching</p>
          <h1>Currently watching</h1>
          <p className="lede">
            Run the session timer while you watch on your own setup and Kura moves the episode for
            you. Nothing plays here. It counts attention, not video.
          </p>
        </div>
        <span className="head-meta">
          {rows.length} in progress · {hours(totalSeconds / 3600)} tracked
        </span>
      </section>

      <div className="filter-row">
        <button
          type="button"
          className={`chip ${view === "queue" ? "active" : ""}`}
          onClick={() => setParams({})}
        >
          Queue
        </button>
        <button
          type="button"
          className={`chip ${view === "tonight" ? "active" : ""}`}
          onClick={() => setParams({ view: "tonight" })}
        >
          Finishable tonight
        </button>
      </div>

      {timerFor && flag("watch_timer") && (
        <WatchHUD
          anime={timerFor}
          timer={timer}
          autoTick={prefs.auto_tick}
          onStart={timer.start}
          onTickNow={async () => {
            await tick(timerFor.id);
            timer.dismissPrompt();
          }}
          onStop={async () => {
            await timer.stop();
            setTimerFor(null);
            await load();
            toast.say("Session closed and saved");
          }}
        />
      )}

      {active.length > 0 && !timerFor && (
        <div className="notice">
          <strong>{active.length} session</strong> still open from another device or tab. Opening a
          timer here takes over. Last write wins.
        </div>
      )}

      {view === "tonight" ? (
        <>
          <div className="filter-row slim">
            <span className="micro">Time I actually have</span>
            {BUDGETS.map((b) => (
              <button
                key={b}
                type="button"
                className={`chip ghost ${budget === b ? "active" : ""}`}
                onClick={() => setBudget(b)}
              >
                {b < 120 ? `${b} min` : `${b / 60} h`}
              </button>
            ))}
          </div>
          {!tonight || tonight.items.length === 0 ? (
            <EmptyState
              title="Nothing closes in that window"
              body="Either the backlog is heavy or the budget is tight. Try a longer window."
              action={
                <button type="button" className="btn" onClick={() => setBudget(300)}>
                  Give me five hours
                </button>
              }
            />
          ) : (
            <div className="continue-row">
              {tonight.items.map((row) => (
                <article className="watch-card" key={row.anime.id}>
                  <Link to={`/anime/${row.anime.id}`}>
                    <img src={row.anime.image_url || "/poster-fallback.png"} alt="" />
                  </Link>
                  <div>
                    <h3>
                      <Link to={`/anime/${row.anime.id}`}>{row.anime.title}</Link>
                    </h3>
                    <p className="meta">
                      {row.episodes_left} left · about {row.minutes_left} min to close it
                    </p>
                  </div>
                  <div className="watch-actions">
                    <button
                      type="button"
                      className="btn compact"
                      onClick={() => startTimer(row.anime)}
                    >
                      Start timer
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      ) : rows.length === 0 ? (
        <EmptyState
          title="Nothing in progress"
          body="Open a title and hit Start watching, or run a session timer to begin auto tracking."
          action={
            <Link className="btn" to="/">
              Find something to watch
            </Link>
          }
        />
      ) : (
        <div className="continue-row">
          {rows.map((entry) => (
            <ContinueCard
              key={entry.anime_id}
              entry={entry}
              token={token}
              onTick={tick}
              onOpenTimer={startTimer}
            />
          ))}
        </div>
      )}

      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
