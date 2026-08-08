import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, loginRequest } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("anime_token"));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(token));

  useEffect(() => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);

    // Only a real rejection ends the session. A rate limit, a restarting API,
    // or a dropped connection gets retried instead of throwing away a login.
    async function resolveUser() {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          const me = await api("/api/auth/me", { token });
          if (!cancelled) setUser(me);
          return;
        } catch (err) {
          if (err?.status === 401 || err?.status === 403) {
            if (!cancelled) {
              localStorage.removeItem("anime_token");
              setToken(null);
              setUser(null);
            }
            return;
          }
          await new Promise((resolve) => setTimeout(resolve, 400 * (attempt + 1)));
        }
      }
    }

    resolveUser().finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      async login(email, password) {
        const data = await loginRequest(email, password);
        localStorage.setItem("anime_token", data.access_token);
        setToken(data.access_token);
      },
      async register(email, username, password) {
        await api("/api/auth/register", {
          method: "POST",
          body: { email, username, password },
        });
        const data = await loginRequest(email, password);
        localStorage.setItem("anime_token", data.access_token);
        setToken(data.access_token);
      },
      logout() {
        localStorage.removeItem("anime_token");
        setToken(null);
        setUser(null);
      },
    }),
    [token, user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
