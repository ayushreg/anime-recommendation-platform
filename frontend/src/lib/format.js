export const STATUS_LABELS = {
  plan_to_watch: "Plan to watch",
  watching: "Watching",
  completed: "Completed",
  on_hold: "On hold",
  dropped: "Dropped",
};

export const SEASON_LABELS = {
  winter: "Winter",
  spring: "Spring",
  summer: "Summer",
  fall: "Fall",
};

export function clock(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

export function hours(value) {
  const n = Number(value || 0);
  if (n < 1) return `${Math.round(n * 60)} min`;
  return `${n.toFixed(1)} h`;
}

export function progressPct(entry) {
  const total = entry?.anime?.episodes;
  const prog = entry?.progress || 0;
  if (!total || total <= 0) return 0;
  return Math.min(100, Math.round((prog / total) * 100));
}

export function relativeDay(value) {
  if (!value) return "";
  const then = new Date(value);
  const diff = Math.round((Date.now() - then.getTime()) / 86400000);
  if (diff <= 0) return "today";
  if (diff === 1) return "yesterday";
  if (diff < 7) return `${diff} days ago`;
  if (diff < 30) return `${Math.round(diff / 7)} weeks ago`;
  return then.toLocaleDateString();
}

export function titleInitial(title) {
  return (title || "?").trim().slice(0, 1).toUpperCase();
}

export function splitTags(raw, max = 4) {
  return (raw || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, max);
}
