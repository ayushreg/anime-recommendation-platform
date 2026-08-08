import React from "react";
import { useAppearance } from "../lib/appearance";

const LINES = {
  idle: "Your vault buddy",
  searching: "Digging through the shelves",
  celebrating: "Another one finished",
  watching: "Timer is running",
  thinking: "Rebuilding your picks",
  empty: "Nothing here yet",
};

const SRC = {
  idle: "/mascot-bust.png",
  searching: "/mascot-search.png",
  celebrating: "/mascot-celebrate.png",
  watching: "/mascot-watch.png",
  thinking: "/mascot-think.png",
  empty: "/mascot-empty.png",
};

/**
 * The mascot reacts to what the app is doing. Each mood has its own art so
 * the personality is visible without a sprite sheet.
 */
export function Mascot({ state = "idle", size = 64, showLine = true, className = "" }) {
  const { appearance } = useAppearance();
  if (!appearance.showMascot) return null;

  const src = SRC[state] || SRC.idle;

  return (
    <div className={`mascot mascot-${state} ${className}`.trim()} aria-hidden="true">
      <img src={src} alt="" width={size} height={size} />
      {showLine && <span>{LINES[state] || LINES.idle}</span>}
    </div>
  );
}

export function EmptyState({ title, body, action, state = "empty" }) {
  return (
    <div className="empty">
      <Mascot state={state} size={112} showLine={false} className="empty-mascot" />
      <h2>{title}</h2>
      <p>{body}</p>
      {action}
    </div>
  );
}

/** Soft character vignette for page headers and sparse surfaces. */
export function CharacterSpot({ mood = "idle", caption, className = "" }) {
  const { appearance } = useAppearance();
  if (!appearance.showCompanion) return null;

  const src = SRC[mood] || SRC.idle;

  return (
    <aside className={`character-spot ${className}`.trim()} aria-hidden="true">
      <img src={src} alt="" />
      {caption ? <span>{caption}</span> : null}
    </aside>
  );
}
