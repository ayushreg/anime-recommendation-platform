import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../icons";
import { sfx } from "../lib/sound";

const PAGES = [
  { id: "go-discover", label: "Go to Discover", path: "/", hint: "g d" },
  { id: "go-watching", label: "Go to Watching", path: "/watching", hint: "g w" },
  { id: "go-foryou", label: "Go to For You", path: "/recommendations", hint: "g f" },
  { id: "go-shelf", label: "Go to Shelf", path: "/shelf", hint: "g s" },
  { id: "go-library", label: "Go to Library", path: "/library" },
  { id: "go-collections", label: "Go to Collections", path: "/collections" },
  { id: "go-insights", label: "Go to Insights", path: "/insights", hint: "g i" },
  { id: "go-seasons", label: "Go to Seasons", path: "/seasons" },
  { id: "go-social", label: "Go to Friends", path: "/social" },
  { id: "go-settings", label: "Go to Settings", path: "/settings" },
  { id: "go-admin", label: "Go to Instance", path: "/admin" },
  { id: "go-quiz", label: "Take the taste quiz", path: "/quiz" },
];

/**
 * Ctrl+K. Titles come from the live suggest endpoint, pages and actions are
 * local, and everything is one list so muscle memory does not have to care
 * which is which.
 */
export function CommandPalette({ open, onClose, onToast }) {
  const navigate = useNavigate();
  const { token } = useAuth();
  const [q, setQ] = useState("");
  const [titles, setTitles] = useState([]);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setTitles([]);
    setCursor(0);
    const t = setTimeout(() => inputRef.current?.focus(), 20);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open || q.trim().length < 2) {
      setTitles([]);
      return undefined;
    }
    const controller = new AbortController();
    const t = setTimeout(() => {
      api(`/api/anime/suggest?q=${encodeURIComponent(q.trim())}`, { signal: controller.signal })
        .then((d) => setTitles(d.items || []))
        .catch(() => {});
    }, 160);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [q, open]);

  const actions = useMemo(() => {
    const term = q.trim().toLowerCase();
    const pages = PAGES.filter((p) => !term || p.label.toLowerCase().includes(term)).map((p) => ({
      key: p.id,
      kind: "page",
      label: p.label,
      hint: p.hint,
      run: () => navigate(p.path),
    }));

    const extras = [];
    if (token) {
      extras.push({
        key: "surprise",
        kind: "action",
        label: "Surprise me with something new",
        run: async () => {
          try {
            const data = await api("/api/discover/surprise", { token });
            navigate(`/anime/${data.anime.id}`);
          } catch (err) {
            onToast?.(err.message);
          }
        },
      });
      extras.push({
        key: "tonight",
        kind: "action",
        label: "What can I finish tonight",
        run: () => navigate("/watching?view=tonight"),
      });
    }
    if (term) {
      extras.push({
        key: "search",
        kind: "action",
        label: `Search the vault for "${q.trim()}"`,
        run: () => navigate(`/?q=${encodeURIComponent(q.trim())}`),
      });
    }

    const found = titles.map((t) => ({
      key: `title-${t.id}`,
      kind: "title",
      label: t.title,
      sub: [t.type, t.year].filter(Boolean).join(" · "),
      image: t.image_url,
      run: () => navigate(`/anime/${t.id}`),
    }));

    return [...found, ...extras, ...pages].slice(0, 24);
  }, [q, titles, navigate, token, onToast]);

  useEffect(() => {
    setCursor((c) => Math.min(c, Math.max(0, actions.length - 1)));
  }, [actions.length]);

  if (!open) return null;

  const runAt = (index) => {
    const action = actions[index];
    if (!action) return;
    sfx.open();
    onClose();
    action.run();
  };

  const onKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => (c + 1) % Math.max(1, actions.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => (c - 1 + actions.length) % Math.max(1, actions.length));
    } else if (e.key === "Enter") {
      e.preventDefault();
      runAt(cursor);
    } else if (e.key === "Tab") {
      // Keep focus inside the dialog.
      e.preventDefault();
    }
  };

  return (
    <div className="palette-backdrop" onMouseDown={onClose} role="presentation">
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="palette-input">
          <Icon name="search" size={18} />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Jump to a title, a page, or an action"
            aria-label="Command palette search"
            aria-controls="palette-list"
            autoComplete="off"
          />
          <kbd>esc</kbd>
        </div>
        <ul className="palette-list" id="palette-list" ref={listRef} role="listbox">
          {actions.length === 0 && <li className="palette-empty">Nothing matches that yet</li>}
          {actions.map((action, index) => (
            <li key={action.key}>
              <button
                type="button"
                role="option"
                aria-selected={index === cursor}
                className={index === cursor ? "active" : ""}
                onMouseEnter={() => setCursor(index)}
                onClick={() => runAt(index)}
              >
                {action.image ? (
                  <img src={action.image} alt="" className="palette-thumb" />
                ) : (
                  <span className={`palette-kind kind-${action.kind}`}>
                    {action.kind === "page" ? "go" : action.kind === "action" ? "do" : "tv"}
                  </span>
                )}
                <span className="palette-label">{action.label}</span>
                {action.sub && <small>{action.sub}</small>}
                {action.hint && <kbd>{action.hint}</kbd>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
