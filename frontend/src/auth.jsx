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
    setLoading(true);
    api("/api/auth/me", { token })
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("anime_token");
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
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
