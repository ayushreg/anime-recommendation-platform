import React, { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../icons";
import { usePrefs } from "../lib/prefs";
import { setSoundEnabled } from "../lib/sound";
import { CommandPalette } from "./CommandPalette";
import { Mascot } from "./Mascot";

const NAV = [
  { to: "/", icon: "discover", label: "Discover", end: true },
  { to: "/watching", icon: "watch", label: "Watching" },
  { to: "/recommendations", icon: "foryou", label: "For You" },
  { to: "/collections", icon: "stack", label: "Lists", flag: "collections" },
  { to: "/insights", icon: "chart", label: "Insights", flag: "insights" },
  { to: "/seasons", icon: "calendar", label: "Seasons", flag: "seasons" },
  { to: "/shelf", icon: "shelf", label: "Shelf" },
  { to: "/library", icon: "ratings", label: "Library" },
  { to: "/social", icon: "friends", label: "Friends", flag: "social" },
];

const MOBILE_NAV = [
  { to: "/", icon: "discover", label: "Discover", end: true },
  { to: "/watching", icon: "watch", label: "Watching" },
  { to: "/recommendations", icon: "foryou", label: "For You" },
  { to: "/collections", icon: "stack", label: "Lists" },
  { to: "/insights", icon: "chart", label: "Insights" },
];

const GOTO = {
  d: "/",
  w: "/watching",
  f: "/recommendations",
  s: "/shelf",
  i: "/insights",
  l: "/collections",
  c: "/seasons",
};

const SHORTCUTS = [
  ["Ctrl or Cmd + K", "Open the command palette"],
  ["/", "Jump to search"],
  ["g then d / w / f / s / i", "Go to Discover, Watching, For You, Shelf, Insights"],
  ["j / k", "Move between posters"],
  ["Enter", "Open the selected poster"],
  ["e", "Add one episode to the selected title"],
  ["r", "Rate the selected title 9 out of 10"],
  ["x", "Not interested in the selected title"],
  ["?", "Show this list"],
];

function ShortcutSheet({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="palette-backdrop" onMouseDown={onClose} role="presentation">
      <div
        className="shortcut-sheet"
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard shortcuts"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h2>Keyboard</h2>
        <dl>
          {SHORTCUTS.map(([keys, what]) => (
            <div key={keys}>
              <dt>
                {keys.split(" ").map((part, i) =>
                  ["then", "or", "+", "/"].includes(part) ? (
                    <em key={`${part}-${i}`}>{part}</em>
                  ) : (
                    <kbd key={`${part}-${i}`}>{part}</kbd>
                  )
                )}
              </dt>
              <dd>{what}</dd>
            </div>
          ))}
        </dl>
        <button type="button" className="btn block" onClick={onClose}>
          Got it
        </button>
      </div>
    </div>
  );
}

export function Shell({ children, searchSlot, mascot = "idle" }) {
  const { user, logout } = useAuth();
  const { prefs, flag } = usePrefs();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [pendingG, setPendingG] = useState(false);

  useEffect(() => {
    api("/api/stats").then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    setSoundEnabled(Boolean(prefs.sound_enabled) && flag("sound_design"));
  }, [prefs.sound_enabled, flag]);

  useEffect(() => {
    function onKey(e) {
      const tag = e.target?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.target?.isContentEditable;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        if (!flag("command_palette")) return;
        e.preventDefault();
        setPaletteOpen((v) => !v);
        return;
      }
      if (typing) return;

      if (e.key === "?") {
        e.preventDefault();
        setSheetOpen(true);
        return;
      }
      if (!flag("keyboard_mode")) return;
      if (e.key === "g") {
        setPendingG(true);
        setTimeout(() => setPendingG(false), 1200);
        return;
      }
      if (pendingG && GOTO[e.key]) {
        e.preventDefault();
        setPendingG(false);
        navigate(GOTO[e.key]);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, pendingG, flag]);

  const visibleNav = NAV.filter((item) => !item.flag || flag(item.flag));

  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace-main">
        Skip to content
      </a>

      <aside className="rail" aria-label="Primary">
        <Link to="/" className="brand">
          <img src="/logo.png" alt="" className="brand-logo" />
          <span>
            <strong>Kura</strong>
            <small>local vault</small>
          </span>
        </Link>

        <nav className="rail-nav">
          {visibleNav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              <Icon name={item.icon} /> {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="rail-foot">
          <button
            type="button"
            className="palette-trigger"
            onClick={() => setPaletteOpen(true)}
            aria-label="Open command palette"
          >
            <Icon name="search" size={14} /> Jump to
            <kbd>{navigator.platform?.includes("Mac") ? "⌘" : "ctrl"} K</kbd>
          </button>

          <Mascot state={mascot} size={38} className="rail-mascot" />

          {stats && (
            <div className="vault-meter" title="Instance health">
              <div className="meter-label">
                <Icon name="local" size={14} /> Vault
              </div>
              <div className="meter-bars" aria-hidden="true">
                {[0.55, 0.8, 0.45, 0.95, 0.7].map((h, i) => (
                  <span key={i} style={{ "--h": h }} />
                ))}
              </div>
              <p>
                <strong>{stats.anime_count.toLocaleString()}</strong> titles ·{" "}
                <strong>{stats.rating_count.toLocaleString()}</strong> ratings
              </p>
              <p>
                <strong>{stats.watch_hours}</strong> h tracked ·{" "}
                <strong>{stats.impression_count.toLocaleString()}</strong> signals
              </p>
            </div>
          )}

          {user ? (
            <div className="rail-user">
              <Icon name="user" size={16} />
              <span>{user.username}</span>
              <Link className="icon-btn" to="/settings" aria-label="Settings">
                <Icon name="gear" size={16} />
              </Link>
              <button type="button" className="icon-btn" onClick={logout} aria-label="Log out">
                <Icon name="logout" size={16} />
              </button>
            </div>
          ) : (
            <Link className="btn block" to="/login">
              Sign in
            </Link>
          )}
        </div>
      </aside>

      <div className="workspace">
        <header className="workspace-bar">
          {searchSlot || <div />}
          <div className="bar-hint">
            <button type="button" className="ghost-btn tiny" onClick={() => setSheetOpen(true)}>
              <kbd>?</kbd> keys
            </button>
          </div>
        </header>
        <main className="workspace-main" id="workspace-main" tabIndex={-1}>
          {children}
        </main>
      </div>

      <nav className="mobile-nav" aria-label="Sections">
        {MOBILE_NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end}>
            <Icon name={item.icon} size={20} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <ShortcutSheet open={sheetOpen} onClose={() => setSheetOpen(false)} />
    </div>
  );
}
