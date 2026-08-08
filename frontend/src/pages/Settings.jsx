import React, { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../icons";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { usePrefs } from "../lib/prefs";
import { sfx } from "../lib/sound";

function Row({ label, hint, children }) {
  return (
    <div className="setting-row">
      <div>
        <strong>{label}</strong>
        {hint && <p className="micro">{hint}</p>}
      </div>
      <div className="setting-control">{children}</div>
    </div>
  );
}

export function Settings() {
  const { token, user, loading } = useAuth();
  const { prefs, flags, save } = usePrefs();
  const [hidden, setHidden] = useState([]);
  const [aniList, setAniList] = useState("");
  const [busy, setBusy] = useState("");
  const fileRef = useRef(null);
  const toast = useToast();

  useEffect(() => {
    if (!token) return;
    api("/api/signals/hidden", { token })
      .then(setHidden)
      .catch(() => setHidden([]));
  }, [token]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  async function unhide(animeId) {
    await api(`/api/signals/feedback/${animeId}`, { method: "DELETE", token });
    setHidden((prev) => prev.filter((h) => h.anime_id !== animeId));
    toast.say("Back in rotation");
  }

  async function exportVault() {
    setBusy("export");
    try {
      const data = await api("/api/vault/export", { token });
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `kura-vault-${user.username}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.say("Vault exported to your downloads");
    } catch (err) {
      toast.say(err.message);
    } finally {
      setBusy("");
    }
  }

  async function importVault(file) {
    setBusy("import");
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const result = await api("/api/vault/import", {
        method: "POST",
        token,
        body: { payload, overwrite: true },
      });
      toast.say(
        `Matched ${result.matched}, imported ${result.ratings_imported} ratings and ${result.library_imported} shelf rows`
      );
    } catch (err) {
      toast.say(err.message);
    } finally {
      setBusy("");
    }
  }

  async function importMal(file) {
    setBusy("mal");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/vault/import/mal", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || "Import failed");
      }
      const result = await res.json();
      sfx.complete();
      toast.say(
        `MyAnimeList import: ${result.matched} matched, ${result.skipped} had no catalog match`
      );
    } catch (err) {
      toast.say(err.message);
    } finally {
      setBusy("");
    }
  }

  async function importAniList(e) {
    e.preventDefault();
    if (!aniList.trim()) return;
    setBusy("anilist");
    try {
      const result = await api("/api/vault/import/anilist", {
        method: "POST",
        token,
        body: { username: aniList.trim() },
      });
      toast.say(`AniList import: ${result.matched} matched, ${result.skipped} skipped`);
    } catch (err) {
      toast.say(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>How Kura behaves</h1>
          <p className="lede">
            Everything on this page changes only your account on this instance.
          </p>
        </div>
      </section>

      <section className="insight-block">
        <h2>Watch timer</h2>
        <Row
          label="Auto tick episodes"
          hint="When a session accumulates one episode of attention, move the counter without asking."
        >
          <input
            type="checkbox"
            checked={prefs.auto_tick}
            onChange={(e) => save({ auto_tick: e.target.checked })}
          />
        </Row>
        <Row label="Typical TV episode" hint="Used when the catalog has no runtime for a title.">
          <input
            type="number"
            min="3"
            max="180"
            value={prefs.episode_minutes_tv}
            onChange={(e) => save({ episode_minutes_tv: Number(e.target.value) })}
          />
          <span className="micro">minutes</span>
        </Row>
        <Row label="Typical movie">
          <input
            type="number"
            min="10"
            max="400"
            value={prefs.episode_minutes_movie}
            onChange={(e) => save({ episode_minutes_movie: Number(e.target.value) })}
          />
          <span className="micro">minutes</span>
        </Row>
        <Row
          label="Idle cutoff"
          hint="No mouse, key, or touch for this long and the timer stops counting."
        >
          <input
            type="number"
            min="30"
            max="1800"
            step="30"
            value={prefs.idle_timeout_seconds}
            onChange={(e) => save({ idle_timeout_seconds: Number(e.target.value) })}
          />
          <span className="micro">seconds</span>
        </Row>
      </section>

      <section className="insight-block">
        <h2>Ranking and chrome</h2>
        <Row label="Diversity" hint="Low plays it safe, high pushes tags you have barely touched.">
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={prefs.diversity}
            onChange={(e) => save({ diversity: Number(e.target.value) })}
          />
          <span className="micro">{Math.round(prefs.diversity * 100)}%</span>
        </Row>
        <Row label="Default ranking">
          <select
            value={prefs.ranking_variant}
            onChange={(e) => save({ ranking_variant: e.target.value })}
          >
            <option value="hybrid">Hybrid</option>
            <option value="content">Content only</option>
            <option value="collaborative">Neighbours only</option>
            <option value="popularity">Popularity (control)</option>
          </select>
        </Row>
        <Row label="Tint the interface from poster art">
          <input
            type="checkbox"
            checked={prefs.poster_tint}
            onChange={(e) => save({ poster_tint: e.target.checked })}
          />
        </Row>
        <Row label="Interface sounds" hint="Synthesised in the browser. No audio files, no downloads.">
          <input
            type="checkbox"
            checked={prefs.sound_enabled}
            onChange={(e) => {
              save({ sound_enabled: e.target.checked });
              if (e.target.checked) setTimeout(() => sfx.open(), 80);
            }}
          />
        </Row>
        <Row label="Taste quiz">
          <Link className="ghost-btn" to="/quiz">
            {prefs.quiz_done ? "Retake the quiz" : "Take the quiz"}
          </Link>
        </Row>
      </section>

      <section className="insight-block">
        <h2>Your data</h2>
        <Row label="Export everything" hint="Ratings, shelf, lists, and notes as one readable JSON file.">
          <button type="button" className="btn compact" onClick={exportVault} disabled={busy === "export"}>
            <Icon name="download" size={16} /> {busy === "export" ? "Working..." : "Export"}
          </button>
        </Row>
        <Row label="Restore a Kura export">
          <input
            ref={fileRef}
            type="file"
            accept="application/json"
            onChange={(e) => e.target.files?.[0] && importVault(e.target.files[0])}
          />
        </Row>
        <Row
          label="Import a MyAnimeList XML export"
          hint="The file MAL hands you from its export page. Matched by MAL id first, then title."
        >
          <input
            type="file"
            accept=".xml,text/xml,application/xml,application/gzip"
            onChange={(e) => e.target.files?.[0] && importMal(e.target.files[0])}
          />
        </Row>
        <form className="setting-row" onSubmit={importAniList}>
          <div>
            <strong>Import a public AniList profile</strong>
            <p className="micro">
              Optional and network dependent. If this machine is offline the rest of Kura carries on
              without it.
            </p>
          </div>
          <div className="setting-control">
            <input
              value={aniList}
              onChange={(e) => setAniList(e.target.value)}
              placeholder="anilist username"
            />
            <button className="btn compact" type="submit" disabled={busy === "anilist"}>
              {busy === "anilist" ? "Fetching..." : "Import"}
            </button>
          </div>
        </form>
      </section>

      {hidden.length > 0 && (
        <section className="insight-block">
          <h2>Hidden titles</h2>
          <p className="micro">
            These are filtered out of recommendations and the discover rail. Put one back any time.
          </p>
          <ul className="hidden-list">
            {hidden.map((h) => (
              <li key={h.anime_id}>
                <img src={h.image_url || "/poster-fallback.png"} alt="" />
                <div>
                  <Link to={`/anime/${h.anime_id}`}>{h.title}</Link>
                  <span className="micro">{h.reason.replace(/_/g, " ")}</span>
                </div>
                <button type="button" className="ghost-btn tiny" onClick={() => unhide(h.anime_id)}>
                  Unhide
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="insight-block">
        <h2>Instance flags</h2>
        <p className="micro">
          Read from feature_flags.json on the API. Toggle them from the Instance page.
        </p>
        <div className="flag-grid">
          {Object.entries(flags).map(([name, on]) => (
            <span key={name} className={`flag-pill ${on ? "on" : "off"}`}>
              {name.replace(/_/g, " ")}
            </span>
          ))}
        </div>
        <Link className="ghost-btn" to="/admin" style={{ marginTop: "0.8rem" }}>
          <Icon name="server" size={16} /> Open instance dashboard
        </Link>
      </section>

      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
