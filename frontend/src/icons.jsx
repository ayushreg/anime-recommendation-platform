import React from "react";

/** Custom stroke icon set for Kura (signal accents on chalk strokes) */
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
  };

  switch (name) {
    case "discover":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="9" />
          <polygon points="12,7 14.5,12 12,17 9.5,12" fill="currentColor" stroke="none" opacity="0.85" />
        </svg>
      );
    case "foryou":
      return (
        <svg {...props}>
          <path d="M4 14c3-6 6-8 8-8s5 2 8 8" />
          <path d="M12 6v12" />
          <circle cx="12" cy="6" r="1.5" fill="currentColor" stroke="none" />
        </svg>
      );
    case "shelf":
      return (
        <svg {...props}>
          <path d="M4 6h16M4 12h16M4 18h16" />
          <path d="M7 6v12M12 6v12M17 6v12" opacity="0.55" />
        </svg>
      );
    case "ratings":
      return (
        <svg {...props}>
          <path d="M12 3.5l2.2 4.5 5 .7-3.6 3.5.9 5L12 15.4 7.5 17.2l.9-5L4.8 8.7l5-.7L12 3.5z" />
        </svg>
      );
    case "search":
      return (
        <svg {...props}>
          <circle cx="11" cy="11" r="6.5" />
          <path d="M16 16l4 4" />
        </svg>
      );
    case "filter":
      return (
        <svg {...props}>
          <path d="M4 7h16M7 12h10M10 17h4" />
        </svg>
      );
    case "local":
      return (
        <svg {...props}>
          <path d="M4 10.5L12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5z" />
        </svg>
      );
    case "similar":
      return (
        <svg {...props}>
          <circle cx="7" cy="12" r="3" />
          <circle cx="17" cy="8" r="3" />
          <circle cx="17" cy="16" r="3" />
          <path d="M9.7 10.6L14.3 8.8M9.7 13.4L14.3 15.2" />
        </svg>
      );
    case "watch":
      return (
        <svg {...props}>
          <rect x="5" y="4" width="14" height="16" rx="1.5" />
          <path d="M9 8h6M9 12h6M9 16h4" />
        </svg>
      );
    case "close":
      return (
        <svg {...props}>
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      );
    case "plus":
      return (
        <svg {...props}>
          <path d="M12 5v14M5 12h14" />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <path d="M5 12.5l4.5 4.5L19 7" />
        </svg>
      );
    case "logout":
      return (
        <svg {...props}>
          <path d="M10 5H6a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h4" />
          <path d="M14 12H8M14 12l3-3M14 12l3 3" />
        </svg>
      );
    case "user":
      return (
        <svg {...props}>
          <circle cx="12" cy="9" r="3.5" />
          <path d="M5 19c1.5-3.5 4-5 7-5s5.5 1.5 7 5" />
        </svg>
      );
    case "arrow":
      return (
        <svg {...props}>
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      );
    case "spark":
      return (
        <svg {...props}>
          <path d="M12 3v4M12 17v4M4.5 6.5l2.8 2.8M16.7 14.7l2.8 2.8M3 12h4M17 12h4M4.5 17.5l2.8-2.8M16.7 9.3l2.8-2.8" />
        </svg>
      );
    case "stack":
      return (
        <svg {...props}>
          <path d="M12 4l8 4-8 4-8-4 8-4z" />
          <path d="M4 12l8 4 8-4M4 16l8 4 8-4" opacity="0.6" />
        </svg>
      );
    case "chart":
      return (
        <svg {...props}>
          <path d="M4 20V6M10 20v-8M16 20v-5M22 20H2" />
          <circle cx="10" cy="9" r="1.4" fill="currentColor" stroke="none" />
        </svg>
      );
    case "calendar":
      return (
        <svg {...props}>
          <rect x="4" y="5" width="16" height="16" rx="2" />
          <path d="M4 10h16M9 3v4M15 3v4" />
        </svg>
      );
    case "friends":
      return (
        <svg {...props}>
          <circle cx="9" cy="9" r="3" />
          <path d="M3 19c1.2-3 3.4-4.5 6-4.5s4.8 1.5 6 4.5" />
          <path d="M16 7.2a3 3 0 0 1 0 5.6M18 19c-.4-1.6-1-2.9-1.8-3.9" opacity="0.6" />
        </svg>
      );
    case "gear":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 3v2.2M12 18.8V21M4.2 7.5l1.9 1.1M17.9 15.4l1.9 1.1M4.2 16.5l1.9-1.1M17.9 8.6l1.9-1.1" />
        </svg>
      );
    case "play":
      return (
        <svg {...props}>
          <polygon points="8,5 19,12 8,19" fill="currentColor" stroke="none" />
        </svg>
      );
    case "more":
      return (
        <svg {...props}>
          <circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none" />
          <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
          <circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none" />
        </svg>
      );
    case "dice":
      return (
        <svg {...props}>
          <rect x="4" y="4" width="16" height="16" rx="3" />
          <circle cx="9" cy="9" r="1.4" fill="currentColor" stroke="none" />
          <circle cx="15" cy="15" r="1.4" fill="currentColor" stroke="none" />
          <circle cx="15" cy="9" r="1.4" fill="currentColor" stroke="none" />
        </svg>
      );
    case "server":
      return (
        <svg {...props}>
          <rect x="3" y="4" width="18" height="7" rx="2" />
          <rect x="3" y="13" width="18" height="7" rx="2" />
          <path d="M7 7.5h.01M7 16.5h.01" />
        </svg>
      );
    case "download":
      return (
        <svg {...props}>
          <path d="M12 4v10M8 11l4 4 4-4M5 19h14" />
        </svg>
      );
    default:
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="8" />
        </svg>
      );
  }
}
