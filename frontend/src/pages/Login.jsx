import React, { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export function Login() {
  const { login, register, user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("demo@anime.app");
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/recommendations" replace />;

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, username, password);
      navigate(mode === "login" ? "/recommendations" : "/quiz");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-visual" aria-hidden="true">
        <img src="/hero-vault.png" alt="" className="auth-hero" />
        <img src="/mascot.png" alt="" className="auth-mascot" />
      </div>
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <img src="/logo.png" alt="" width={48} height={48} />
          <p className="eyebrow">Kura</p>
        </div>
        <h1>{mode === "login" ? "Open your vault" : "Create a vault login"}</h1>
        <p className="hint">Demo vault · demo@anime.app / demo1234</p>
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        {mode === "register" && (
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
        )}
        <label>
          Password
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
          />
        </label>
        {error && (
          <p className="toast" role="alert">
            {error}
          </p>
        )}
        <button className="btn block" type="submit" disabled={busy}>
          {busy ? "Working..." : mode === "login" ? "Sign in" : "Register"}
        </button>
        <button
          type="button"
          className="ghost-btn"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account?" : "Have an account?"}
        </button>
        <Link to="/" className="text-link">
          Back to Discover
        </Link>
      </form>
    </div>
  );
}
