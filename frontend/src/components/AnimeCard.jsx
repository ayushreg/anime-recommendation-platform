import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../icons";
import { splitTags, titleInitial } from "../lib/format";
import { useImpression } from "../lib/useImpression";
import { usePrefs } from "../lib/prefs";
import { applyTint, extractTint } from "../lib/tint";

function rememberRecent(anime) {
  try {
    const key = "kura_recent";
    const prev = JSON.parse(localStorage.getItem(key) || "[]");
    const next = [
      { id: anime.id, title: anime.title, image_url: anime.image_url },
      ...prev.filter((x) => x.id !== anime.id),
    ].slice(0, 12);
    localStorage.setItem(key, JSON.stringify(next));
  } catch {
    /* ignore */
  }
}

export function readRecent() {
  try {
    return JSON.parse(localStorage.getItem("kura_recent") || "[]");
  } catch {
    return [];
  }
}

function ScoreBadge({ score }) {
  if (score == null) return null;
  return <span className="score-badge">{Number(score).toFixed(1)}</span>;
}

export function AnimeCard({
  anime,
  token,
  onRate,
  onDismiss,
  onAdd,
  onRemove,
  removeLabel = "Remove",
  reason,
  method,
  why,
  userScore,
  surface = "discover",
  position = 0,
  selected = false,
  tags,
}) {
  const { prefs, flag } = usePrefs();
  const cardRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const { ref, onMouseEnter, onMouseLeave, onOpen } = useImpression({
    animeId: anime.id,
    surface,
    position,
  });

  useEffect(() => {
    if (!flag("poster_tint") || !prefs.poster_tint) return;
    let alive = true;
    extractTint(anime, anime.image_url).then((tint) => {
      if (alive) applyTint(cardRef.current, tint);
    });
    return () => {
      alive = false;
    };
  }, [anime, prefs.poster_tint, flag]);

  const setRefs = (node) => {
    cardRef.current = node;
    ref.current = node;
  };

  const open = () => {
    rememberRecent(anime);
    onOpen();
  };

  const genreTags = tags || splitTags(anime.genres, 2);

  return (
    <article
      ref={setRefs}
      className={`tile ${selected ? "is-selected" : ""}`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      data-anime-id={anime.id}
    >
      <Link to={`/anime/${anime.id}`} className="tile-poster" onClick={open}>
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
        <ScoreBadge score={anime.score} />
        {userScore != null && <span className="you-rated">You {userScore}</span>}
      </Link>

      {token && (onDismiss || onAdd || onRemove) && (
        <div className={`tile-tools ${menuOpen ? "open" : ""}`}>
          <button
            type="button"
            className="icon-btn tiny"
            aria-label={`More actions for ${anime.title}`}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <Icon name="more" size={14} />
          </button>
          {menuOpen && (
            <div className="tile-menu" role="menu">
              {onAdd && (
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onAdd(anime); }}>
                  Add to shelf
                </button>
              )}
              {onRemove && (
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onRemove(anime); }}>
                  {removeLabel}
                </button>
              )}
              {onDismiss && (
                <>
                  <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onDismiss(anime, "not_interested"); }}>
                    Not interested
                  </button>
                  <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onDismiss(anime, "seen_it"); }}>
                    Seen it already
                  </button>
                  <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onDismiss(anime, "wrong_vibe"); }}>
                    Wrong vibe
                  </button>
                  <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onDismiss(anime, "too_long"); }}>
                    Too long right now
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      <div className="tile-body">
        <h3>
          <Link to={`/anime/${anime.id}`} onClick={open}>
            {anime.title}
          </Link>
        </h3>
        <p className="meta">
          {[anime.type, anime.year, anime.episodes ? `${anime.episodes} ep` : null]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {(reason || method) && (
          <p className="reason">
            {method && <span className="method-tag">{method}</span>}
            {reason}
          </p>
        )}
        {why && !reason && <p className="reason why">{why}</p>}
        {!reason && !why && <p className="genres">{genreTags.join(" · ")}</p>}
        {token && onRate && (
          <div className="rate-strip" role="group" aria-label={`Rate ${anime.title}`}>
            {[7, 8, 9, 10].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onRate(anime.id, s)}
                // A bare "9" tells a screen reader nothing about what it does.
                aria-label={`Rate ${s} out of 10`}
                title={`Rate ${s} out of 10`}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
