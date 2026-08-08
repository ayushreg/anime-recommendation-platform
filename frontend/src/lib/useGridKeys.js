import { useEffect, useState } from "react";

/**
 * Poster-grid keyboard mode: j and k walk the grid, Enter opens, and the
 * single-letter keys act on whatever is selected. Ignores keystrokes while a
 * field has focus so typing a search never ticks an episode.
 */
export function useGridKeys({ items, enabled = true, onOpen, onTick, onRate, onDismiss }) {
  const [index, setIndex] = useState(-1);

  useEffect(() => {
    setIndex((i) => (items.length === 0 ? -1 : Math.min(i, items.length - 1)));
  }, [items.length]);

  useEffect(() => {
    if (!enabled) return undefined;

    function onKey(e) {
      const tag = e.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.target?.isContentEditable) {
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (!items.length) return;

      const key = e.key.toLowerCase();
      if (key === "j" || key === "arrowright") {
        e.preventDefault();
        setIndex((i) => Math.min(items.length - 1, i + 1));
      } else if (key === "k" || key === "arrowleft") {
        e.preventDefault();
        setIndex((i) => Math.max(0, i - 1));
      } else if (index >= 0 && index < items.length) {
        const target = items[index];
        if (e.key === "Enter") {
          e.preventDefault();
          onOpen?.(target);
        } else if (key === "e") {
          e.preventDefault();
          onTick?.(target);
        } else if (key === "r") {
          e.preventDefault();
          onRate?.(target, 9);
        } else if (key === "x") {
          e.preventDefault();
          onDismiss?.(target, "not_interested");
        }
      }
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, index, enabled, onOpen, onTick, onRate, onDismiss]);

  // Keep the selected tile on screen as the cursor moves.
  useEffect(() => {
    if (index < 0 || !items[index]) return;
    const node = document.querySelector(`[data-anime-id="${items[index].id}"]`);
    node?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [index, items]);

  return { index, setIndex, selectedId: index >= 0 ? items[index]?.id : null };
}
