import React from "react";

const LINES = {
  idle: "Your vault buddy",
  searching: "Digging through the shelves",
  celebrating: "Another one finished",
  watching: "Timer is running",
  thinking: "Rebuilding your picks",
  empty: "Nothing here yet",
};

/**
 * The mascot reacts to what the app is doing. It is one image with a state
 * class, so the personality costs a few lines of CSS rather than a sprite sheet.
 */
export function Mascot({ state = "idle", size = 64, showLine = true, className = "" }) {
  return (
    <div className={`mascot mascot-${state} ${className}`.trim()} aria-hidden="true">
      <img src="/mascot-chibi.png" alt="" width={size} height={size} />
      {showLine && <span>{LINES[state] || LINES.idle}</span>}
    </div>
  );
}

export function EmptyState({ title, body, action, state = "empty" }) {
  return (
    <div className="empty">
      <Mascot state={state} size={96} showLine={false} className="empty-mascot" />
      <h2>{title}</h2>
      <p>{body}</p>
      {action}
    </div>
  );
}
