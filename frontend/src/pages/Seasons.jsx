import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { AnimeCard } from "../components/AnimeCard";
import { EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { SEASON_LABELS } from "../lib/format";

const ORDER = ["winter", "spring", "summer", "fall"];

export function Seasons() {
  const { token } = useAuth();
  const [buckets, setBuckets] = useState([]);
  const [picked, setPicked] = useState(null);
  const [titles, setTitles] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/discover/seasons?since_year=2005")
      .then((d) => {
        setBuckets(d.buckets || []);
        const first = (d.buckets || [])[0];
        if (first) setPicked({ year: first.year, season: first.season });
      })
      .catch(() => setBuckets([]));
  }, []);

  useEffect(() => {
    if (!picked) return;
    setBusy(true);
    api(`/api/discover/season/${picked.year}/${picked.season}?limit=48`)
      .then((d) => setTitles(d.items || []))
      .catch(() => setTitles([]))
      .finally(() => setBusy(false));
  }, [picked]);

  const byYear = useMemo(() => {
    const grouped = new Map();
    for (const b of buckets) {
      if (!grouped.has(b.year)) grouped.set(b.year, {});
      grouped.get(b.year)[b.season] = b.count;
    }
    return [...grouped.entries()].sort((a, b) => b[0] - a[0]);
  }, [buckets]);

  return (
    <Shell mascot={busy ? "searching" : "idle"}>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Seasons</p>
          <h1>Season calendar</h1>
          <p className="lede">
            Every season in the catalog, by year. For what is airing right now, try Upcoming.
          </p>
        </div>
        {picked && (
          <span className="head-meta">
            {SEASON_LABELS[picked.season]} {picked.year} · {titles.length} titles
          </span>
        )}
      </section>

      {byYear.length === 0 ? (
        <EmptyState
          title="No season data yet"
          body="Run the seed once with a network connection and the season fields fill in."
        />
      ) : (
        <div className="season-grid" role="grid" aria-label="Seasons by year">
          {byYear.map(([year, seasons]) => (
            <div className="season-year" key={year} role="row">
              <span className="season-year-label">{year}</span>
              {ORDER.map((season) => {
                const count = seasons[season] || 0;
                const isPicked = picked?.year === year && picked?.season === season;
                return (
                  <button
                    key={season}
                    type="button"
                    role="gridcell"
                    className={`season-cell ${isPicked ? "active" : ""} ${count ? "" : "empty"}`}
                    disabled={!count}
                    onClick={() => setPicked({ year, season })}
                    aria-label={`${SEASON_LABELS[season]} ${year}, ${count} titles`}
                  >
                    <em>{SEASON_LABELS[season]}</em>
                    <strong>{count}</strong>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {picked && (
        <>
          <h2 className="section-title">
            {SEASON_LABELS[picked.season]} {picked.year}
          </h2>
          <section className="tile-grid stagger">
            {titles.map((anime, i) => (
              <AnimeCard
                key={anime.id}
                anime={anime}
                token={token}
                surface="seasons"
                position={i}
              />
            ))}
          </section>
        </>
      )}
    </Shell>
  );
}
