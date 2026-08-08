import React from "react";
import { Icon } from "../icons";
import { clock } from "../lib/format";

/**
 * The visible half of the watch timer.
 *
 * It states plainly what it is counting and why it stopped counting, because a
 * timer that silently pauses is worse than no timer at all.
 */
export function WatchHUD({
  anime,
  timer,
  onTickNow,
  onStop,
  onStart,
  autoTick,
  compact = false,
}) {
  const { running, seconds, episodeSeconds, secondsToNext, progress, pausedReason, conflict, prompt } =
    timer;
  const pct = episodeSeconds
    ? Math.min(100, Math.round(((episodeSeconds - secondsToNext) / episodeSeconds) * 100))
    : 0;

  if (!timer.session) {
    return (
      <div className={`watch-hud idle ${compact ? "compact" : ""}`}>
        <div className="hud-copy">
          <strong>Watch session</strong>
          <p>
            Start the timer while you watch on your own setup. Kura counts only the seconds this
            tab is visible, focused, and you are not idle, then moves your episode when enough
            time has passed.
          </p>
        </div>
        <button type="button" className="btn" onClick={onStart}>
          <Icon name="play" size={16} /> Start session
        </button>
      </div>
    );
  }

  return (
    <div className={`watch-hud ${running && !pausedReason ? "live" : "held"} ${compact ? "compact" : ""}`}>
      <div className="hud-dial" aria-hidden="true">
        <span className="hud-ring" style={{ "--pct": `${pct}%` }} />
        <strong>{clock(secondsToNext)}</strong>
        <small>to ep {progress + 1}</small>
      </div>

      <div className="hud-copy">
        <p className="hud-title">
          {anime?.title || "Watching"}
          <span className={`hud-dot ${running && !pausedReason ? "on" : "off"}`} />
          {running && !pausedReason ? "counting" : "paused"}
        </p>
        <p className="micro">
          {clock(seconds)} counted this session · episode length {Math.round(episodeSeconds / 60)} min
          {autoTick ? " · auto tick on" : " · auto tick off"}
        </p>
        {pausedReason && <p className="hud-warn">Paused: {pausedReason.toLowerCase()}</p>}
        {conflict && (
          <p className="hud-warn">
            Another device is running a session for this title. Last write wins.
          </p>
        )}
        {prompt && (
          <div className="hud-prompt">
            <span>{prompt}</span>
            <button type="button" className="btn compact" onClick={onTickNow}>
              Yes, mark it
            </button>
            <button type="button" className="ghost-btn" onClick={timer.dismissPrompt}>
              Not yet
            </button>
          </div>
        )}
      </div>

      <div className="hud-actions">
        {running ? (
          <button type="button" className="ghost-btn" onClick={timer.pause}>
            Hold
          </button>
        ) : (
          <button type="button" className="btn compact" onClick={timer.resume}>
            Resume
          </button>
        )}
        <button type="button" className="ghost-btn" onClick={onTickNow}>
          +1 ep
        </button>
        <button type="button" className="ghost-btn danger" onClick={onStop}>
          End
        </button>
      </div>
    </div>
  );
}
