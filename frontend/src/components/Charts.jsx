import React from "react";
import { hours } from "../lib/format";

const DAY_MS = 86400000;

/**
 * Contribution-graph heatmap of watch minutes per day.
 * Columns are weeks, rows are weekdays, exactly like the graph everyone
 * already knows how to read.
 */
export function StreakHeatmap({ days = [], weeks = 26 }) {
  const byDay = new Map(days.map((d) => [d.day, d]));
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Start on the Sunday that begins the earliest visible week.
  const start = new Date(today.getTime() - (weeks * 7 - 1) * DAY_MS);
  start.setDate(start.getDate() - start.getDay());

  const cells = [];
  let peak = 0;
  for (const d of days) peak = Math.max(peak, d.seconds || 0);

  for (let w = 0; w < weeks; w += 1) {
    const column = [];
    for (let d = 0; d < 7; d += 1) {
      const date = new Date(start.getTime() + (w * 7 + d) * DAY_MS);
      const key = date.toISOString().slice(0, 10);
      const row = byDay.get(key);
      const seconds = row?.seconds || 0;
      const level = seconds === 0 ? 0 : Math.min(4, Math.ceil((seconds / (peak || 1)) * 4));
      column.push({
        key,
        level,
        seconds,
        episodes: row?.episodes || 0,
        future: date > today,
      });
    }
    cells.push(column);
  }

  const cell = 12;
  const gap = 3;
  const width = weeks * (cell + gap);
  const height = 7 * (cell + gap);

  return (
    <div className="heatmap">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={`Watch activity for the last ${weeks} weeks`}
        preserveAspectRatio="xMinYMid meet"
      >
        {cells.map((column, w) =>
          column.map((c, d) => (
            <rect
              key={c.key}
              x={w * (cell + gap)}
              y={d * (cell + gap)}
              width={cell}
              height={cell}
              rx={2.5}
              className={`heat heat-${c.future ? "future" : c.level}`}
            >
              <title>
                {c.future
                  ? c.key
                  : `${c.key}: ${c.episodes} episodes, ${hours(c.seconds / 3600)}`}
              </title>
            </rect>
          ))
        )}
      </svg>
      <div className="heat-legend">
        <span>quiet</span>
        {[0, 1, 2, 3, 4].map((l) => (
          <i key={l} className={`heat heat-${l}`} />
        ))}
        <span>binge</span>
      </div>
    </div>
  );
}

/**
 * Taste radar. Weights come from ratings and watch time, never from clicks,
 * so the shape reflects what you finished rather than what you scrolled past.
 */
export function TasteRadar({ slices = [], size = 340 }) {
  const data = slices.slice(0, 8);
  if (data.length < 3) {
    return <p className="micro">Rate a few more titles and the shape will fill in.</p>;
  }

  // The labels sit outside the rings, so the drawing area is inset far enough
  // that a long tag name still lands inside the viewBox.
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 74;
  const step = (Math.PI * 2) / data.length;
  const peak = Math.max(...data.map((d) => d.weight), 0.0001);

  const point = (index, value) => {
    const angle = index * step - Math.PI / 2;
    const r = radius * Math.max(0.08, value / peak);
    return [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r];
  };

  const polygon = data.map((d, i) => point(i, d.weight).join(",")).join(" ");

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width="100%"
      className="radar"
      role="img"
      aria-label="Your taste profile by tag"
    >
      {[0.25, 0.5, 0.75, 1].map((ring) => (
        <circle key={ring} cx={cx} cy={cy} r={radius * ring} className="radar-ring" />
      ))}
      {data.map((d, i) => {
        const [x, y] = point(i, peak);
        return <line key={d.tag} x1={cx} y1={cy} x2={x} y2={y} className="radar-spoke" />;
      })}
      <polygon points={polygon} className="radar-shape" />
      {data.map((d, i) => {
        const angle = i * step - Math.PI / 2;
        const x = cx + Math.cos(angle) * (radius + 18);
        const y = cy + Math.sin(angle) * (radius + 18);
        const horizontal = Math.abs(Math.cos(angle));
        return (
          <text
            key={d.tag}
            x={x}
            y={y}
            className="radar-label"
            textAnchor={horizontal < 0.3 ? "middle" : Math.cos(angle) > 0 ? "start" : "end"}
            dominantBaseline="middle"
          >
            {d.tag.length > 16 ? `${d.tag.slice(0, 15)}...` : d.tag}
          </text>
        );
      })}
    </svg>
  );
}

export function StatTile({ label, value, sub, tone = "" }) {
  return (
    <div className={`stat-tile ${tone}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}

export function Bar({ label, value, max, suffix = "" }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <div className="bar-track">
        <span style={{ width: `${pct}%` }} />
      </div>
      <span className="bar-value">
        {value}
        {suffix}
      </span>
    </div>
  );
}
