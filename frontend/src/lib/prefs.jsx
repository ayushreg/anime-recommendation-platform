import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { configureImpressions } from "./impressions";

const PrefsContext = createContext(null);

const DEFAULTS = {
  diversity: 0.35,
  ranking_variant: "hybrid",
  episode_minutes_tv: 24,
  episode_minutes_movie: 100,
  idle_timeout_seconds: 180,
  auto_tick: true,
  sound_enabled: false,
  poster_tint: true,
  share_activity: true,
  quiz_done: false,
  taste: {},
};

export function PrefsProvider({ children }) {
  const { token } = useAuth();
  const [prefs, setPrefs] = useState(DEFAULTS);
  const [flags, setFlags] = useState({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api("/api/flags")
      .then(setFlags)
      .catch(() => setFlags({}));
  }, []);

  useEffect(() => {
    if (!token) {
      setPrefs(DEFAULTS);
      setReady(true);
      return;
    }
    api("/api/me/preferences", { token })
      .then((data) => setPrefs({ ...DEFAULTS, ...data }))
      .catch(() => setPrefs(DEFAULTS))
      .finally(() => setReady(true));
  }, [token]);

  useEffect(() => {
    configureImpressions({ token, on: flags.impressions !== false });
  }, [token, flags.impressions]);

  const save = useCallback(
    async (patch) => {
      setPrefs((prev) => ({ ...prev, ...patch }));
      if (!token) return null;
      const data = await api("/api/me/preferences", { method: "PUT", token, body: patch });
      setPrefs({ ...DEFAULTS, ...data });
      return data;
    },
    [token]
  );

  // Kept stable across preference changes: callers put `flag` in effect
  // dependency arrays, and a fresh identity every render refetches their data.
  const flag = useCallback(
    (name, fallback = true) => (name in flags ? Boolean(flags[name]) : fallback),
    [flags]
  );

  const value = useMemo(
    () => ({
      prefs,
      flags,
      ready,
      save,
      flag,
      refresh: () =>
        token
          ? api("/api/me/preferences", { token }).then((d) => setPrefs({ ...DEFAULTS, ...d }))
          : Promise.resolve(null),
    }),
    [prefs, flags, ready, save, flag, token]
  );

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs() {
  return useContext(PrefsContext) || { prefs: DEFAULTS, flags: {}, ready: true, flag: () => true };
}
