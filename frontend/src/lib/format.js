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

/**
 * "in 2d 4h", "in 51m", "airing now". Deliberately coarse above a day: nobody
 * needs the seconds on something eleven days out, and a ticking second hand on
 * forty cards is a lot of re-renders for no information.
 */
export function countdown(seconds) {
  if (seconds == null) return null;
  const total = Math.max(0, Math.floor(seconds));
  if (total < 60) return "airing now";
  const days = Math.floor(total / 86400);
  const hrs = Math.floor((total % 86400) / 3600);
  const mins = Math.floor((total % 3600) / 60);
  if (days > 0) return `in ${days}d ${hrs}h`;
  if (hrs > 0) return `in ${hrs}h ${mins}m`;
  return `in ${mins}m`;
}

/**
 * Render a bare "YYYY-MM-DD" as that calendar day.
 *
 * `new Date("2027-01-01")` is parsed as UTC midnight, so anyone west of
 * Greenwich renders it as the last day of the previous year. A premiere date
 * has no time attached, so it should be read in local terms from the start.
 */
export function plainDate(value) {
  if (!value) return null;
  const [y, m, d] = String(value).slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** "Sat 9 Aug, 23:30" in the viewer's own timezone. */
export function airTime(iso) {
  if (!iso) return null;
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return null;
  return when.toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
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
