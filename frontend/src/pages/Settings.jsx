import React, { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../icons";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { relativeDay } from "../lib/format";
import { usePrefs } from "../lib/prefs";
import { ACCENTS, ATMOSPHERES, MOTION, useAppearance } from "../lib/appearance";
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
  const { prefs, flags, save, flag } = usePrefs();
  const { appearance, patch, reset } = useAppearance();
  const [hidden, setHidden] = useState([]);
  const [aniList, setAniList] = useState("");
  const [busy, setBusy] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [linkForm, setLinkForm] = useState({ provider: "anilist", username: "" });
  const [liveStatus, setLiveStatus] = useState(null);
  const fileRef = useRef(null);
  const toast = useToast();

  const liveOn = flag("live_data", true);

  useEffect(() => {
    if (!token) return;
    api("/api/signals/hidden", { token })
      .then(setHidden)
      .catch(() => setHidden([]));
  }, [token]);

  useEffect(() => {
    if (!token || !liveOn) return;
    api("/api/connect/accounts", { token })
      .then(setAccounts)
      .catch(() => setAccounts([]));
    api("/api/live/status", { token })
      .then(setLiveStatus)
      .catch(() => setLiveStatus(null));
  }, [token, liveOn]);

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

  async function linkAccount(e) {
    e.preventDefault();
    if (!linkForm.username.trim()) return;
    setBusy("link");
    try {
      const { account, result } = await api("/api/connect/accounts", {
        method: "POST",
        token,
        body: { provider: linkForm.provider, username: linkForm.username.trim() },
      });
      setAccounts((prev) => [...prev.filter((a) => a.provider !== account.provider), account]);
      setLinkForm((f) => ({ ...f, username: "" }));
      sfx.complete();
      toast.say(
        `${account.provider_label} linked: ${result.matched} matched, ${result.skipped} with no catalog match`
      );
    } catch (err) {
      toast.say(err.message);
    } finally {
      setBusy("");
    }
  }

  async function syncAccount(provider) {
    setBusy(`sync-${provider}`);
    try {
      const { account, result } = await api(`/api/connect/accounts/${provider}/sync`, {
        method: "POST",
        token,
      });
      setAccounts((prev) => prev.map((a) => (a.provider === provider ? account : a)));
      toast.say(`Synced: ${result.matched} matched, ${result.skipped} skipped`);
    } catch (err) {
      // The account row carries the reason now, so re-read it to show the why.
      api("/api/connect/accounts", { token }).then(setAccounts).catch(() => {});
      toast.say(err.message);
    } finally {
      setBusy("");
    }
  }

  async function unlinkAccount(provider) {
    await api(`/api/connect/accounts/${provider}`, { method: "DELETE", token });
    setAccounts((prev) => prev.filter((a) => a.provider !== provider));
    toast.say("Unlinked. Everything it imported stays in your vault.");
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

      <section className="insight-block appearance-block">
        <div className="appearance-head">
          <div>
            <h2>Appearance</h2>
            <p className="micro">
              Accents, atmosphere, and motion live on this device so guests get them too.
            </p>
          </div>
          <img src="/mascot-bust.png" alt="" className="appearance-preview" />
        </div>

        <Row label="Accent" hint="The signal color used for active nav, buttons, and focus rings.">
          <div className="swatch-row" role="radiogroup" aria-label="Accent color">
            {ACCENTS.map((a) => (
              <button
                key={a.id}
                type="button"
                role="radio"
                aria-checked={appearance.accent === a.id}
                className={`swatch ${appearance.accent === a.id ? "active" : ""}`}
                style={{ "--swatch": a.swatch }}
                title={a.label}
                onClick={() => patch({ accent: a.id })}
              >
                <span className="sr-only">{a.label}</span>
              </button>
            ))}
          </div>
        </Row>

        <Row label="Atmosphere" hint="How loud the background gradients get.">
          <div className="choice-grid">
            {ATMOSPHERES.map((a) => (
              <button
                key={a.id}
                type="button"
                className={`choice-card ${appearance.atmosphere === a.id ? "active" : ""}`}
                onClick={() => patch({ atmosphere: a.id })}
              >
                <strong>{a.label}</strong>
                <span>{a.hint}</span>
              </button>
            ))}
          </div>
        </Row>

        <Row label="Motion" hint="Overrides OS reduced-motion when you pick Still.">
          <div className="choice-grid compact">
            {MOTION.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`choice-card ${appearance.motion === m.id ? "active" : ""}`}
                onClick={() => patch({ motion: m.id })}
              >
                <strong>{m.label}</strong>
                <span>{m.hint}</span>
              </button>
            ))}
          </div>
        </Row>

        <Row label="Show rail mascot" hint="The mood character under Jump to.">
          <input
            type="checkbox"
            checked={appearance.showMascot}
            onChange={(e) => patch({ showMascot: e.target.checked })}
          />
        </Row>
        <Row label="Show page companions" hint="Character spots on headers and empty states.">
          <input
            type="checkbox"
            checked={appearance.showCompanion}
            onChange={(e) => patch({ showCompanion: e.target.checked })}
          />
        </Row>
        <Row label="Compact poster grids" hint="Tighter gaps and denser shelves.">
          <input
            type="checkbox"
            checked={appearance.denserCards}
            onChange={(e) => patch({ denserCards: e.target.checked })}
          />
        </Row>
        <Row label="Reset look">
          <button type="button" className="ghost-btn" onClick={reset}>
            Restore defaults
          </button>
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
        <h2>Connected accounts</h2>
        <p className="micro">
          Kura stores a username and reads a public list. There is no password field here and
          no way for this to write anything back to a tracker. Unlinking leaves everything it
          imported in your vault.
        </p>

        {!liveOn ? (
          <p className="micro" style={{ marginTop: "0.7rem" }}>
            An operator has switched the <strong>live_data</strong> flag off for this
            instance. Turn it back on from the <Link to="/admin">instance dashboard</Link>.
          </p>
        ) : (
          <>
            {accounts.length > 0 && (
              <div style={{ marginTop: "0.8rem" }}>
                {accounts.map((a) => (
                  <div className="linked-account" key={a.provider}>
                    <span className={`sync-dot ${a.last_status}`} aria-hidden="true" />
                    <div className="grow">
                      <strong>
                        {a.provider_label} · {a.external_username}
                      </strong>
                      <p className="micro">
                        {a.last_status === "ok" &&
                          `Synced ${relativeDay(a.last_synced_at)} · ${a.last_detail}`}
                        {a.last_status === "error" && a.last_detail}
                        {a.last_status === "never" && "Not synced yet"}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="ghost-btn tiny"
                      onClick={() => syncAccount(a.provider)}
                      disabled={busy === `sync-${a.provider}`}
                    >
                      {busy === `sync-${a.provider}` ? "Syncing..." : "Sync now"}
                    </button>
                    <button
                      type="button"
                      className="ghost-btn tiny danger"
                      onClick={() => unlinkAccount(a.provider)}
                    >
                      Unlink
                    </button>
                  </div>
                ))}
              </div>
            )}

            <form className="setting-row" onSubmit={linkAccount}>
              <div>
                <strong>Link a list</strong>
                <p className="micro">
                  Just a public username, on either service. Nothing is written back, and
                  your list stays yours: unlinking keeps everything it imported.
                </p>
              </div>
              <div className="setting-control">
                <select
                  value={linkForm.provider}
                  onChange={(e) => setLinkForm((f) => ({ ...f, provider: e.target.value }))}
                >
                  <option value="anilist">AniList</option>
                  <option value="mal">MyAnimeList</option>
                </select>
                <input
                  value={linkForm.username}
                  onChange={(e) => setLinkForm((f) => ({ ...f, username: e.target.value }))}
                  placeholder="username"
                />
                <button className="btn compact" type="submit" disabled={busy === "link"}>
                  <Icon name="link" size={16} /> {busy === "link" ? "Linking..." : "Link"}
                </button>
              </div>
            </form>

            {liveStatus && (
              <p className="micro live-stamp">
                <Icon name="broadcast" size={13} />
                {liveStatus.refreshed_at
                  ? `Airing data last checked ${relativeDay(liveStatus.refreshed_at)} · ${
                      liveStatus.releasing
                    } airing, ${liveStatus.upcoming} upcoming`
                  : "No airing data pulled yet"}
                {" · "}
                <Link to="/upcoming">Open Upcoming</Link>
              </p>
            )}
          </>
        )}
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
              A one-off copy. To keep a list in sync, link the account above instead.
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
