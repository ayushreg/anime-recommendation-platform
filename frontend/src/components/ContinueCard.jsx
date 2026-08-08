import React from "react";
import { Link } from "react-router-dom";
import { STATUS_LABELS, hours, progressPct } from "../lib/format";

export function ContinueCard({ entry, token, onTick, onOpenTimer }) {
  const anime = entry.anime;
  if (!anime) return null;
  const total = anime.episodes || "?";
  const watched = entry.watch_seconds || 0;

  return (
    <article className="watch-card">
      <Link to={`/anime/${anime.id}`}>
        <img
          src={anime.image_url || "/poster-fallback.png"}
          alt=""
          onError={(e) => {
            e.currentTarget.onerror = null;
            e.currentTarget.src = "/poster-fallback.png";
          }}
        />
      </Link>
      <div>
        <h3>
          <Link to={`/anime/${anime.id}`}>{anime.title}</Link>
        </h3>
        <p className="meta">
          Ep {entry.progress || 0} / {total} · {STATUS_LABELS[entry.status] || entry.status}
          {entry.is_rewatching ? " · rewatch" : ""}
        </p>
        <div
          className="progress-bar"
          role="progressbar"
          aria-valuenow={progressPct(entry)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${anime.title} progress`}
        >
          <span style={{ width: `${progressPct(entry)}%` }} />
        </div>
        {watched > 0 && <p className="micro">{hours(watched / 3600)} tracked</p>}
      </div>
      {token && (
        <div className="watch-actions">
          <button type="button" className="btn compact" onClick={() => onTick(anime.id)}>
            +1 ep
          </button>
          {onOpenTimer ? (
            <button type="button" className="ghost-btn" onClick={() => onOpenTimer(anime)}>
              Timer
            </button>
          ) : (
            <Link className="ghost-btn" to={`/anime/${anime.id}`}>
              Open
            </Link>
          )}
        </div>
      )}
    </article>
  );
}
