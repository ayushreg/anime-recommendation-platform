import React, { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";

function Shell({ children }) {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api("/api/stats").then(setStats).catch(() => {});
  }, []);

  return (
    <div className="page">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">AR</span>
          <span>
            AnimeRecs
            <small>hybrid ranking engine</small>
          </span>
        </Link>
        <nav>
          <Link to="/">Discover</Link>
          <Link to="/recommendations">For You</Link>
          {user ? (
            <>
              <span className="user-chip">{user.username}</span>
              <button type="button" className="ghost" onClick={logout}>
                Log out
              </button>
            </>
          ) : (
            <Link className="btn" to="/login">
              Sign in
            </Link>
          )}
        </nav>
      </header>
      {stats && (
        <div className="stats-strip">
          <span>
            <strong>{stats.anime_count.toLocaleString()}</strong> titles indexed
          </span>
          <span>
            <strong>{stats.rating_count.toLocaleString()}</strong> ratings
          </span>
          <span>
            cache: <strong>{stats.cache_backend}</strong>
          </span>
        </div>
      )}
      <main>{children}</main>
    </div>
  );
}

function AnimeCard({ anime, onRate, token }) {
  return (
    <article className="card">
      <Link to={`/anime/${anime.id}`} className="poster">
        {anime.image_url ? (
          <img src={anime.image_url} alt={anime.title} loading="lazy" />
        ) : (
          <div className="poster-fallback">{anime.title.slice(0, 1)}</div>
        )}
      </Link>
      <div className="card-body">
        <h3>
          <Link to={`/anime/${anime.id}`}>{anime.title}</Link>
        </h3>
        <p className="meta">
          {[anime.type, anime.year, anime.score ? `★ ${anime.score}` : null]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <p className="genres">{anime.genres || "General"}</p>
        {token && (
          <div className="rate-row">
            {[7, 8, 9, 10].map((score) => (
              <button key={score} type="button" onClick={() => onRate(anime.id, score)}>
                {score}
              </button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function Home() {
  const { token } = useAuth();
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function load(query = "") {
    setBusy(true);
    try {
      const data = await api(`/api/anime/search?q=${encodeURIComponent(query)}&limit=24`);
      setItems(data.items);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load("");
  }, []);

  async function rate(animeId, score) {
    try {
      await api("/api/ratings", {
        method: "POST",
        token,
        body: { anime_id: animeId, score },
      });
      setMessage(`Saved rating ${score}/10`);
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <Shell>
      <section className="hero">
        <h1>
          Find your next watch across{" "}
          <em>thousands</em> of titles
        </h1>
        <p>
          Search uses TF-IDF + cosine similarity. Personalized picks blend content signals with
          collaborative filtering, cached in Redis for speed.
        </p>
        <form
          className="search"
          onSubmit={(e) => {
            e.preventDefault();
            load(q);
          }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Try mecha, romance school, space adventure..."
          />
          <button type="submit" disabled={busy}>
            {busy ? "Searching..." : "Search"}
          </button>
        </form>
        {message && <p className="toast">{message}</p>}
      </section>
      <section className="grid">
        {items.map((anime) => (
          <AnimeCard key={anime.id} anime={anime} token={token} onRate={rate} />
        ))}
      </section>
    </Shell>
  );
}

function Recommendations() {
  const { token, user, loading } = useAuth();
  const [rows, setRows] = useState([]);
  const [cached, setCached] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    api("/api/recommendations?limit=12", { token })
      .then((data) => {
        setRows(data.recommendations);
        setCached(data.cached);
      })
      .catch((err) => setError(err.message));
  }, [token]);

  if (loading) return <Shell><p className="pad">Loading...</p></Shell>;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <Shell>
      <section className="hero compact">
        <h1>For you</h1>
        <p>
          Hybrid recommendations for <strong>{user.username}</strong>
          {cached ? " · served from Redis cache" : " · freshly computed"}
        </p>
        {error && <p className="toast">{error}</p>}
      </section>
      <section className="grid">
        {rows.map((row) => (
          <article className="card" key={row.anime.id}>
            <Link to={`/anime/${row.anime.id}`} className="poster">
              {row.anime.image_url ? (
                <img src={row.anime.image_url} alt={row.anime.title} />
              ) : (
                <div className="poster-fallback">{row.anime.title.slice(0, 1)}</div>
              )}
            </Link>
            <div className="card-body">
              <h3>
                <Link to={`/anime/${row.anime.id}`}>{row.anime.title}</Link>
              </h3>
              <p className="meta">{row.method} · score {row.score}</p>
              <p className="genres">{row.reason}</p>
            </div>
          </article>
        ))}
      </section>
    </Shell>
  );
}

function Detail() {
  const { id } = useParams();
  const { token } = useAuth();
  const [anime, setAnime] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api(`/api/anime/${id}`).then(setAnime).catch((err) => setMessage(err.message));
    api(`/api/anime/${id}/similar`).then(setSimilar).catch(() => {});
  }, [id]);

  async function rate(score) {
    await api("/api/ratings", {
      method: "POST",
      token,
      body: { anime_id: Number(id), score },
    });
    setMessage(`Rated ${score}/10`);
  }

  async function watch() {
    await api(`/api/watchlist/${id}`, { method: "POST", token });
    setMessage("Added to watchlist");
  }

  if (!anime) return <Shell><p className="pad">{message || "Loading..."}</p></Shell>;

  return (
    <Shell>
      <section className="detail">
        <div className="detail-poster">
          {anime.image_url ? (
            <img src={anime.image_url} alt={anime.title} />
          ) : (
            <div className="poster-fallback large">{anime.title.slice(0, 1)}</div>
          )}
        </div>
        <div>
          <h1>{anime.title}</h1>
          <p className="meta">
            {[anime.type, anime.year, anime.episodes ? `${anime.episodes} eps` : null, anime.score ? `★ ${anime.score}` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="genres">{anime.genres}</p>
          <p className="synopsis">{anime.synopsis}</p>
          {token && (
            <div className="actions">
              <button type="button" className="btn" onClick={watch}>
                Watchlist
              </button>
              {[7, 8, 9, 10].map((score) => (
                <button key={score} type="button" onClick={() => rate(score)}>
                  Rate {score}
                </button>
              ))}
            </div>
          )}
          {message && <p className="toast">{message}</p>}
        </div>
      </section>
      <h2 className="section-title">Similar titles</h2>
      <section className="grid">
        {similar.map((item) => (
          <AnimeCard key={item.id} anime={item} token={null} onRate={() => {}} />
        ))}
      </section>
    </Shell>
  );
}

function Login() {
  const { login, register, user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("demo@anime.app");
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");

  if (user) return <Navigate to="/recommendations" replace />;

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      if (mode === "login") await login(email, password);
      else await register(email, username, password);
      navigate("/recommendations");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <Shell>
      <form className="auth-card" onSubmit={submit}>
        <h1>{mode === "login" ? "Welcome back" : "Create account"}</h1>
        <p className="hint">Demo login: demo@anime.app / demo1234</p>
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
        {error && <p className="toast">{error}</p>}
        <button className="btn" type="submit">
          {mode === "login" ? "Sign in" : "Register"}
        </button>
        <button
          type="button"
          className="ghost"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account?" : "Have an account?"}
        </button>
      </form>
    </Shell>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/recommendations" element={<Recommendations />} />
      <Route path="/anime/:id" element={<Detail />} />
      <Route path="/login" element={<Login />} />
    </Routes>
  );
}
