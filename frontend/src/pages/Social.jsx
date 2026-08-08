import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { relativeDay } from "../lib/format";
import { usePrefs } from "../lib/prefs";

const KIND_COPY = {
  rated: "rated",
  completed: "finished",
  watch_started: "started watching",
  collection_add: "filed",
  recommended: "passed along",
  rewatch_started: "started a rewatch of",
};

export function Social() {
  const { token, user, loading } = useAuth();
  const { prefs, save, flag } = usePrefs();
  const [me, setMe] = useState(null);
  const [friends, setFriends] = useState([]);
  const [feed, setFeed] = useState([]);
  const [board, setBoard] = useState(null);
  const [inbox, setInbox] = useState([]);
  const [code, setCode] = useState("");
  const toast = useToast();

  const load = useCallback(async () => {
    if (!token) return;
    const [card, list, activity, leaderboard, mail] = await Promise.all([
      api("/api/social/me", { token }),
      api("/api/social/friends", { token }),
      api("/api/social/feed?limit=30", { token }),
      api("/api/social/leaderboard", { token }),
      api("/api/social/inbox", { token }),
    ]);
    setMe(card);
    setFriends(list);
    setFeed(activity);
    setBoard(leaderboard);
    setInbox(mail);
  }, [token]);

  useEffect(() => {
    if (token) load().catch((e) => toast.say(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (!flag("social")) {
    return (
      <Shell>
        <EmptyState
          title="Social is switched off"
          body="This instance has the social flag disabled. Flip it in Settings or feature_flags.json."
          action={
            <Link className="btn" to="/settings">
              Open settings
            </Link>
          }
        />
      </Shell>
    );
  }

  async function follow(e) {
    e.preventDefault();
    try {
      const friend = await api("/api/social/follow", {
        method: "POST",
        token,
        body: { friend_code: code.trim() },
      });
      setCode("");
      toast.say(`Now following ${friend.username}`);
      await load();
    } catch (err) {
      toast.say(err.message);
    }
  }

  async function unfollow(friendId) {
    await api(`/api/social/follow/${friendId}`, { method: "DELETE", token });
    toast.say("Unfollowed");
    await load();
  }

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Friends</p>
          <h1>People on this instance</h1>
          <p className="lede">
            Nothing federates anywhere. These are the accounts sharing this machine, which is
            exactly who you want when the household argues about what to watch.
          </p>
        </div>
      </section>

      {me && (
        <section className="insight-block">
          <h2>Your code</h2>
          <div className="code-row">
            <code className="friend-code">{me.friend_code}</code>
            <button
              type="button"
              className="ghost-btn"
              onClick={() => {
                navigator.clipboard?.writeText(me.friend_code || "");
                toast.say("Code copied");
              }}
            >
              Copy
            </button>
            <label className="check">
              <input
                type="checkbox"
                checked={prefs.share_activity}
                onChange={(e) => save({ share_activity: e.target.checked })}
              />
              Share my activity and hours
            </label>
          </div>
          <form className="inline-form" onSubmit={follow}>
            <label className="grow">
              Follow someone
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="KURA-XXXXXXXX"
                required
              />
            </label>
            <button className="btn" type="submit">
              Follow
            </button>
          </form>
        </section>
      )}

      {board && board.rows.length > 0 && (
        <section className="insight-block">
          <h2>Hours this week</h2>
          <ol className="leaderboard">
            {board.rows.map((row, i) => (
              <li key={row.user_id} className={row.is_you ? "you" : ""}>
                <span className="rank">{i + 1}</span>
                <span className="who">
                  {row.username}
                  {row.is_you ? " (you)" : ""}
                </span>
                <div className="bar-track">
                  <span
                    style={{
                      width: `${
                        board.rows[0].hours > 0
                          ? Math.round((row.hours / board.rows[0].hours) * 100)
                          : 0
                      }%`,
                    }}
                  />
                </div>
                <span className="bar-value">{row.hours} h</span>
              </li>
            ))}
          </ol>
          {board.opted_out > 0 && (
            <p className="micro">{board.opted_out} account opted out of sharing.</p>
          )}
        </section>
      )}

      <div className="insight-split">
        <section className="insight-block">
          <h2>Activity</h2>
          {feed.length === 0 ? (
            <p className="micro">Nothing yet. Rate or finish something and it lands here.</p>
          ) : (
            <ul className="feed">
              {feed.map((row) => (
                <li key={row.id}>
                  {row.anime?.image_url && (
                    <Link to={`/anime/${row.anime.id}`}>
                      <img src={row.anime.image_url} alt="" />
                    </Link>
                  )}
                  <div>
                    <p>
                      <strong>{row.username}</strong> {KIND_COPY[row.kind] || row.kind}{" "}
                      {row.anime ? (
                        <Link to={`/anime/${row.anime.id}`}>{row.anime.title}</Link>
                      ) : (
                        row.detail
                      )}
                    </p>
                    <span className="micro">{relativeDay(row.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="insight-block">
          <h2>Following</h2>
          {friends.length === 0 ? (
            <p className="micro">Paste a friend code above to follow someone on this instance.</p>
          ) : (
            <ul className="friend-list">
              {friends.map((f) => (
                <li key={f.user_id}>
                  <div>
                    <strong>{f.username}</strong>
                    <span className="micro">
                      {f.hours_this_week} h this week · {f.completed} finished
                    </span>
                  </div>
                  <button
                    type="button"
                    className="ghost-btn tiny danger"
                    onClick={() => unfollow(f.user_id)}
                  >
                    Unfollow
                  </button>
                </li>
              ))}
            </ul>
          )}

          <h2 style={{ marginTop: "1.4rem" }}>Sent your way</h2>
          {inbox.length === 0 ? (
            <p className="micro">No recommendations waiting.</p>
          ) : (
            <ul className="feed">
              {inbox.map((row) => (
                <li key={row.id}>
                  {row.anime?.image_url && (
                    <Link to={`/anime/${row.anime.id}`}>
                      <img src={row.anime.image_url} alt="" />
                    </Link>
                  )}
                  <div>
                    <p>
                      <strong>{row.username}</strong> thinks you should watch{" "}
                      {row.anime ? (
                        <Link to={`/anime/${row.anime.id}`}>{row.anime.title}</Link>
                      ) : (
                        row.detail
                      )}
                    </p>
                    <span className="micro">{relativeDay(row.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
