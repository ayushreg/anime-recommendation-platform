import { useCallback, useEffect, useRef } from "react";
import { track } from "./impressions";

// A poster has to hold still on screen this long before it counts as seen.
// Anything shorter is a fast scroll, not attention.
const VIEW_AFTER_MS = 900;

/**
 * Watches a poster and reports how long it actually spent on screen.
 *
 * The view fires on a timer while the tile is visible rather than when it
 * leaves, because a tile you stare at without scrolling is the strongest
 * signal there is and waiting for an exit event would miss it entirely.
 * Leaving early cancels the timer, so flicking past a grid logs nothing.
 */
export function useImpression({ animeId, surface = "discover", position = 0 }) {
  const ref = useRef(null);
  const shownAt = useRef(0);
  const timerRef = useRef(null);
  const reported = useRef(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || !animeId || typeof IntersectionObserver === "undefined") return undefined;

    reported.current = false;
    shownAt.current = 0;

    const report = () => {
      if (reported.current || !shownAt.current) return;
      reported.current = true;
      track({
        anime_id: animeId,
        surface,
        kind: "view",
        dwell_ms: performance.now() - shownAt.current,
        position,
      });
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          if (!shownAt.current) shownAt.current = performance.now();
          if (!timerRef.current && !reported.current) {
            timerRef.current = setTimeout(report, VIEW_AFTER_MS);
          }
          return;
        }
        if (timerRef.current) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
        // Long enough on screen to count even though it just left.
        if (shownAt.current && performance.now() - shownAt.current >= VIEW_AFTER_MS) report();
        shownAt.current = 0;
      },
      { threshold: 0.4 }
    );

    observer.observe(node);
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      if (shownAt.current && performance.now() - shownAt.current >= VIEW_AFTER_MS) report();
      observer.disconnect();
    };
  }, [animeId, surface, position]);

  const hoverStart = useRef(0);

  const onMouseEnter = useCallback(() => {
    hoverStart.current = performance.now();
  }, []);

  const onMouseLeave = useCallback(() => {
    if (!hoverStart.current) return;
    const dwell = performance.now() - hoverStart.current;
    hoverStart.current = 0;
    // Hovering for a full second is deliberate. Anything less is the cursor
    // passing through on its way somewhere else.
    if (dwell > 1000) {
      track({ anime_id: animeId, surface, kind: "hover", dwell_ms: dwell, position });
    }
  }, [animeId, surface, position]);

  const onOpen = useCallback(() => {
    const dwell = hoverStart.current ? performance.now() - hoverStart.current : 0;
    track({ anime_id: animeId, surface, kind: "click", dwell_ms: dwell, position });
  }, [animeId, surface, position]);

  return { ref, onMouseEnter, onMouseLeave, onOpen };
}
