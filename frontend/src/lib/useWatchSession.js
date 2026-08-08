import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

const HEARTBEAT_EVERY = 15; // seconds of wall clock between posts
const IDLE_EVENTS = ["mousemove", "keydown", "pointerdown", "wheel", "touchstart"];

function deviceId() {
  try {
    let id = localStorage.getItem("kura_device");
    if (!id) {
      id = `web-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem("kura_device", id);
    }
    return id;
  } catch {
    return "web";
  }
}

function deviceLabel() {
  if (typeof navigator === "undefined") return "This device";
  const ua = navigator.userAgent || "";
  if (/Android|iPhone|iPad/i.test(ua)) return "Phone or tablet";
  if (/Mac/i.test(ua)) return "Mac";
  if (/Windows/i.test(ua)) return "Windows";
  return "This device";
}

/**
 * The watch timer.
 *
 * The browser is the only thing that knows whether you are actually watching,
 * so it does the counting: a second only counts when the tab is visible, the
 * window has focus, and you have moved something in the last few minutes.
 * Every fifteen seconds it tells the server how many of those seconds were
 * real. Nothing plays here, nothing is streamed, nothing is scraped.
 */
export function useWatchSession({ animeId, token, idleTimeout = 180, enabled = true }) {
  const [session, setSession] = useState(null);
  const [running, setRunning] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [episodeSeconds, setEpisodeSeconds] = useState(1440);
  const [secondsToNext, setSecondsToNext] = useState(1440);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("watching");
  const [pausedReason, setPausedReason] = useState("");
  const [prompt, setPrompt] = useState(null);
  const [conflict, setConflict] = useState(false);
  const [lastTick, setLastTick] = useState(0);
  const [error, setError] = useState("");

  const pending = useRef(0);
  const sinceBeat = useRef(0);
  const lastInput = useRef(Date.now());
  const sessionRef = useRef(null);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    const mark = () => {
      lastInput.current = Date.now();
    };
    IDLE_EVENTS.forEach((name) => window.addEventListener(name, mark, { passive: true }));
    return () => IDLE_EVENTS.forEach((name) => window.removeEventListener(name, mark));
  }, []);

  const sendBeat = useCallback(
    async (idle) => {
      const current = sessionRef.current;
      if (!current || !token) return;
      const gained = Math.round(pending.current);
      pending.current = 0;
      try {
        const data = await api("/api/watch/heartbeat", {
          method: "POST",
          token,
          body: { session_id: current.id, active_seconds: gained, idle: Boolean(idle) },
        });
        setEpisodeSeconds(data.episode_seconds);
        setSecondsToNext(data.seconds_to_next);
        setProgress(data.progress);
        setStatus(data.status);
        setConflict(Boolean(data.conflict));
        setPrompt(data.prompt || null);
        if (data.ticked) setLastTick((n) => n + data.ticked);
        if (data.status === "completed") setRunning(false);
      } catch (err) {
        setError(err.message);
      }
    },
    [token]
  );

  // One tick per second. Cheap, and it keeps the countdown honest.
  useEffect(() => {
    if (!running || !session) return undefined;
    const id = setInterval(() => {
      const hidden = typeof document !== "undefined" && document.hidden;
      const unfocused = typeof document !== "undefined" && !document.hasFocus();
      const idleFor = (Date.now() - lastInput.current) / 1000;
      const idle = idleFor > idleTimeout;

      if (hidden) setPausedReason("Tab is in the background");
      else if (unfocused) setPausedReason("Window is not focused");
      else if (idle) setPausedReason(`No input for ${Math.round(idleFor / 60)} min`);
      else setPausedReason("");

      const counting = !hidden && !unfocused && !idle;
      if (counting) {
        pending.current += 1;
        setSeconds((s) => s + 1);
        setSecondsToNext((s) => Math.max(0, s - 1));
      }

      sinceBeat.current += 1;
      if (sinceBeat.current >= HEARTBEAT_EVERY) {
        sinceBeat.current = 0;
        sendBeat(!counting);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [running, session, idleTimeout, sendBeat]);

  const start = useCallback(async () => {
    if (!token || !animeId || !enabled) return null;
    setError("");
    try {
      const data = await api("/api/watch/session", {
        method: "POST",
        token,
        body: {
          anime_id: Number(animeId),
          device_id: deviceId(),
          device_label: deviceLabel(),
          source: "timer",
        },
      });
      setSession(data.session);
      setSeconds(data.session.active_seconds || 0);
      setEpisodeSeconds(data.episode_seconds);
      setSecondsToNext(data.seconds_to_next);
      setProgress(data.progress);
      setStatus(data.status);
      setConflict(Boolean(data.conflict));
      lastInput.current = Date.now();
      sinceBeat.current = 0;
      pending.current = 0;
      setRunning(true);
      return data.session;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, [animeId, token, enabled]);

  const stop = useCallback(async () => {
    const current = sessionRef.current;
    setRunning(false);
    if (!current || !token) return;
    if (pending.current > 0) await sendBeat(false);
    try {
      await api(`/api/watch/session/${current.id}/stop`, { method: "POST", token });
    } catch {
      /* the session ages out on its own if this never lands */
    }
    setSession(null);
  }, [token, sendBeat]);

  const pause = useCallback(() => setRunning(false), []);
  const resume = useCallback(() => {
    lastInput.current = Date.now();
    setRunning(true);
  }, []);

  // Flush whatever is buffered if the tab is closed mid-session.
  useEffect(() => {
    const onHide = () => {
      if (sessionRef.current && pending.current > 0) sendBeat(false);
    };
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [sendBeat]);

  // Leaving the page ends the session so it does not sit open forever.
  useEffect(() => () => {
    const current = sessionRef.current;
    if (current && token) {
      api(`/api/watch/session/${current.id}/stop`, { method: "POST", token }).catch(() => {});
    }
  }, [token]);

  return {
    session,
    running,
    seconds,
    episodeSeconds,
    secondsToNext,
    progress,
    status,
    pausedReason,
    prompt,
    conflict,
    lastTick,
    error,
    start,
    stop,
    pause,
    resume,
    dismissPrompt: () => setPrompt(null),
  };
}
