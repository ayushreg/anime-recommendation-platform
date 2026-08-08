import React from "react";

/**
 * Kura's icon set.
 *
 * House rules, so twenty-eight glyphs read as one family:
 *
 * - 24x24 box, artwork inside 3..21, so nothing touches the edge
 * - 1.75 stroke, round caps and joins, no sub-pixel diagonals
 * - one filled "signal" dot per icon at most, used to mark the thing the icon
 *   is actually about (the pin on a map, the eye of a timer). It is the motif
 *   that ties the set to the brand, and it stops being a motif if every shape
 *   gets one
 * - shapes sit on whole or half pixels at 24px so they stay crisp unscaled
 */

const ACCENT = { fill: "currentColor", stroke: "none" };

export function Icon({ name, size = 20, className = "" }) {
  const props = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.75,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    className: `icon icon-${name} ${className}`.trim(),
    "aria-hidden": true,
    focusable: false,
  };

  switch (name) {
    // ------------------------------------------------------------- navigation
    case "discover":
      // Compass: the needle is the accent.
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M15.2 8.8l-1.9 4.4-4.4 1.9 1.9-4.4z" {...ACCENT} />
        </svg>
      );
    case "watch":
      // Play inside a ring, with the ring left open at the top like a dial.
      return (
        <svg {...props}>
          <path d="M12 3.5a8.5 8.5 0 1 1-6 2.5" />
          <path d="M10.3 9.2l4.6 2.8-4.6 2.8z" {...ACCENT} />
        </svg>
      );
    case "foryou":
      // Sparkline rising to a marked point: "tuned for you".
      return (
        <svg {...props}>
          <path d="M4 16.5l4-4.5 3.2 3 5.3-6.5" />
          <circle cx="17.2" cy="8.2" r="2.1" {...ACCENT} />
        </svg>
      );
    case "stack":
      // Layered shelves.
      return (
        <svg {...props}>
          <path d="M12 4l7.5 3.6L12 11.2 4.5 7.6z" />
          <path d="M4.5 12L12 15.6 19.5 12" />
          <path d="M4.5 16.4L12 20l7.5-3.6" opacity="0.5" />
        </svg>
      );
    case "chart":
      return (
        <svg {...props}>
          <path d="M4 19.5V4.5M4 19.5h16" />
          <path d="M8 19.5v-5M12.5 19.5v-9M17 19.5v-3.5" />
          <circle cx="12.5" cy="10.5" r="1.6" {...ACCENT} />
        </svg>
      );
    case "calendar":
      return (
        <svg {...props}>
          <rect x="3.75" y="5.75" width="16.5" height="14.5" rx="2.5" />
          <path d="M3.75 10.25h16.5M8.5 3.5v4M15.5 3.5v4" />
          <rect x="7.25" y="13" width="3" height="3" rx="0.75" {...ACCENT} />
        </svg>
      );
    case "broadcast":
      // Transmitting: a source with two arcs each side.
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="2.1" {...ACCENT} />
          <path d="M8.6 8.6a4.8 4.8 0 0 0 0 6.8M15.4 15.4a4.8 4.8 0 0 0 0-6.8" />
          <path d="M5.9 5.9a8.6 8.6 0 0 0 0 12.2M18.1 18.1a8.6 8.6 0 0 0 0-12.2" opacity="0.45" />
        </svg>
      );
    case "shelf":
      // Books standing on a shelf, one leaning.
      return (
        <svg {...props}>
          <path d="M4 19.5h16" />
          <path d="M6.5 19.5V8.5h3v11M12 19.5V6.5h3v13" />
          <path d="M17.6 19.5l1.7-8.4 2 .4-1.6 8" opacity="0.75" />
        </svg>
      );
    case "ratings":
      // Star, single filled shape: a rating is the one thing you assert.
      return (
        <svg {...props}>
          <path
            d="M12 4.2l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 9.9l5.4-.8z"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "friends":
      return (
        <svg {...props}>
          <circle cx="9.5" cy="8.75" r="3.25" />
          <path d="M3.5 19.5c.9-3.2 3.2-4.9 6-4.9s5.1 1.7 6 4.9" />
          <path d="M16.4 6.2a3.25 3.25 0 0 1 0 5.1M17.5 15.1c1.4.9 2.4 2.4 3 4.4" opacity="0.55" />
        </svg>
      );

    // ----------------------------------------------------------------- actions
    case "search":
      return (
        <svg {...props}>
          <circle cx="10.75" cy="10.75" r="6.25" />
          <path d="M15.4 15.4l4.1 4.1" />
        </svg>
      );
    case "filter":
      return (
        <svg {...props}>
          <path d="M4 6.5h16M7 12h10M10 17.5h4" />
        </svg>
      );
    case "plus":
      return (
        <svg {...props}>
          <path d="M12 5.5v13M5.5 12h13" />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      );
    case "close":
      return (
        <svg {...props}>
          <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
        </svg>
      );
    case "more":
      return (
        <svg {...props}>
          <circle cx="6" cy="12" r="1.5" {...ACCENT} />
          <circle cx="12" cy="12" r="1.5" {...ACCENT} />
          <circle cx="18" cy="12" r="1.5" {...ACCENT} />
        </svg>
      );
    case "arrow":
      return (
        <svg {...props}>
          <path d="M4.5 12h14M13 6.5l5.5 5.5-5.5 5.5" />
        </svg>
      );
    case "play":
      return (
        <svg {...props}>
          <path d="M8 5.5l11 6.5-11 6.5z" strokeLinejoin="round" />
        </svg>
      );
    case "download":
      return (
        <svg {...props}>
          <path d="M12 4v10.5M7.5 10.5L12 15l4.5-4.5" />
          <path d="M4.5 17.5v1a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-1" />
        </svg>
      );
    case "dice":
      // Chance: the pips are the accent.
      return (
        <svg {...props}>
          <rect x="4.25" y="4.25" width="15.5" height="15.5" rx="3.5" />
          <circle cx="9" cy="9" r="1.35" {...ACCENT} />
          <circle cx="15" cy="15" r="1.35" {...ACCENT} />
          <circle cx="12" cy="12" r="1.35" {...ACCENT} />
        </svg>
      );
    case "spark":
      // Four-point star for anything "generated".
      return (
        <svg {...props}>
          <path d="M12 3.8c.7 4.2 2.2 5.7 6.4 6.4-4.2.7-5.7 2.2-6.4 6.4-.7-4.2-2.2-5.7-6.4-6.4 4.2-.7 5.7-2.2 6.4-6.4z" />
          <circle cx="18.4" cy="18" r="1.5" {...ACCENT} />
        </svg>
      );
    case "similar":
      return (
        <svg {...props}>
          <circle cx="9" cy="12" r="5.25" />
          <circle cx="15" cy="12" r="5.25" opacity="0.55" />
        </svg>
      );
    case "link":
      return (
        <svg {...props}>
          <path d="M10.2 13.8a3.9 3.9 0 0 0 5.6 0l2.6-2.6a3.9 3.9 0 0 0-5.6-5.6l-1.2 1.2" />
          <path d="M13.8 10.2a3.9 3.9 0 0 0-5.6 0l-2.6 2.6a3.9 3.9 0 0 0 5.6 5.6l1.2-1.2" />
        </svg>
      );

    // ------------------------------------------------------------------ system
    case "user":
      return (
        <svg {...props}>
          <circle cx="12" cy="8.75" r="3.5" />
          <path d="M5 19.5c1.1-3.4 3.7-5.1 7-5.1s5.9 1.7 7 5.1" />
        </svg>
      );
    case "gear":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="3.1" />
          <path d="M12 3.6v2.3M12 18.1v2.3M20.4 12h-2.3M5.9 12H3.6M17.9 6.1l-1.6 1.6M7.7 16.3l-1.6 1.6M17.9 17.9l-1.6-1.6M7.7 7.7L6.1 6.1" />
        </svg>
      );
    case "logout":
      return (
        <svg {...props}>
          <path d="M14.5 4.5h-7a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h7" />
          <path d="M11.5 12h8M16.5 8.5l3.5 3.5-3.5 3.5" />
        </svg>
      );
    case "server":
      return (
        <svg {...props}>
          <rect x="3.75" y="4.75" width="16.5" height="6" rx="2" />
          <rect x="3.75" y="13.25" width="16.5" height="6" rx="2" />
          <circle cx="7.75" cy="7.75" r="1.25" {...ACCENT} />
          <circle cx="7.75" cy="16.25" r="1.25" {...ACCENT} />
        </svg>
      );
    case "local":
      // A machine with a pulse: this instance, running here.
      return (
        <svg {...props}>
          <rect x="3.5" y="5" width="17" height="11" rx="2.25" />
          <path d="M8.5 20h7" />
          <path d="M7 11h2.2l1.3-2.2 1.8 4 1.4-1.8H17" {...{ fill: "none" }} />
        </svg>
      );

    default:
      // A visible placeholder beats a silent gap when a name is misspelled.
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="8" opacity="0.4" />
        </svg>
      );
  }
}
