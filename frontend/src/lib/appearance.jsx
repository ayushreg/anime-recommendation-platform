import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "kura.appearance";

export const ACCENTS = [
  { id: "rose", label: "Signal rose", swatch: "#ff2d6a" },
  { id: "aqua", label: "Vault aqua", swatch: "#3de7ff" },
  { id: "gold", label: "Late-night gold", swatch: "#ffc14a" },
  { id: "violet", label: "Neon violet", swatch: "#a78bfa" },
];

export const ATMOSPHERES = [
  { id: "default", label: "Neon vault", hint: "Magenta and cyan wash" },
  { id: "deep", label: "Deep shelf", hint: "Quieter, darker room" },
  { id: "aurora", label: "Aurora", hint: "Bigger color bloom" },
  { id: "ink", label: "Ink", hint: "Flat stage for posters" },
];

export const MOTION = [
  { id: "full", label: "Full", hint: "Float, stagger, page enters" },
  { id: "calm", label: "Calm", hint: "Softer and slower" },
  { id: "off", label: "Still", hint: "Respect reduced-motion feel" },
];

const DEFAULTS = {
  accent: "rose",
  atmosphere: "default",
  motion: "full",
  showMascot: true,
  showCompanion: true,
  denserCards: false,
};

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}

function applyDom(appearance) {
  const root = document.documentElement;
  root.dataset.accent = appearance.accent;
  root.dataset.atmosphere = appearance.atmosphere;
  root.dataset.motion = appearance.motion;
  root.dataset.mascot = appearance.showMascot ? "on" : "off";
  root.dataset.companion = appearance.showCompanion ? "on" : "off";
  root.dataset.density = appearance.denserCards ? "compact" : "comfy";
}

const AppearanceContext = createContext(null);

export function AppearanceProvider({ children }) {
  const [appearance, setAppearance] = useState(readStored);

  useEffect(() => {
    applyDom(appearance);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(appearance));
    } catch {
      /* private mode */
    }
  }, [appearance]);

  const patch = useCallback((next) => {
    setAppearance((prev) => ({ ...prev, ...next }));
  }, []);

  const reset = useCallback(() => setAppearance({ ...DEFAULTS }), []);

  const value = useMemo(
    () => ({ appearance, patch, reset, defaults: DEFAULTS }),
    [appearance, patch, reset]
  );

  return <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>;
}

export function useAppearance() {
  return (
    useContext(AppearanceContext) || {
      appearance: DEFAULTS,
      patch: () => {},
      reset: () => {},
      defaults: DEFAULTS,
    }
  );
}
