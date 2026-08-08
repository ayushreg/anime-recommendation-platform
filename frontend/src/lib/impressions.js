/**
 * Impression batching.
 *
 * A poster grid can render sixty tiles in one scroll. Sending a request per
 * tile would be absurd, so events queue here and flush on a timer, when the
 * queue gets long, or when the tab goes away.
 */

import { beacon } from "../api";

const FLUSH_MS = 4000;
const MAX_QUEUE = 40;

let queue = [];
let timer = null;
let authToken = null;
let enabled = true;

export function configureImpressions({ token, on }) {
  authToken = token || null;
  if (typeof on === "boolean") enabled = on;
}

function flush() {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  if (!queue.length || !authToken || !enabled) {
    queue = [];
    return;
  }
  const events = queue.slice(0, 200);
  queue = [];
  beacon("/api/signals/impressions", { events }, authToken);
}

function schedule() {
  if (timer) return;
  timer = setTimeout(flush, FLUSH_MS);
}

export function track(event) {
  if (!enabled || !authToken || !event?.anime_id) return;
  queue.push({
    anime_id: event.anime_id,
    surface: event.surface || "discover",
    kind: event.kind || "view",
    dwell_ms: Math.max(0, Math.round(event.dwell_ms || 0)),
    position: Math.max(0, Math.round(event.position || 0)),
  });
  if (queue.length >= MAX_QUEUE) flush();
  else schedule();
}

export function flushImpressions() {
  flush();
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("pagehide", flush);
}
