import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { AnimeCard } from "../components/AnimeCard";
import { EmptyState } from "../components/Mascot";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";

const EMOJI = ["*", "~", "#", "!", "+", "^", "@", "="];

export function Collections() {
  const { token, user, loading } = useAuth();
  const [lists, setLists] = useState([]);
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState("*");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    setLists(await api("/api/collections", { token }));
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

  async function create(e) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api("/api/collections", {
        method: "POST",
        token,
        body: { name: name.trim(), emoji, description: description.trim() || null },
      });
      setName("");
      setDescription("");
      setCreating(false);
      toast.say("List created");
      await load();
    } catch (err) {
      toast.say(err.message);
    }
  }

  async function remove(id) {
    await api(`/api/collections/${id}`, { method: "DELETE", token });
    toast.say("List deleted");
    await load();
  }

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">Lists</p>
          <h1>Collections</h1>
          <p className="lede">
            Statuses answer where you are with a show. Lists answer what mood it belongs to.
          </p>
        </div>
        <button type="button" className="btn" onClick={() => setCreating((v) => !v)}>
          {creating ? "Cancel" : "New list"}
        </button>
      </section>

      {creating && (
        <form className="inline-form" onSubmit={create}>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
          </label>
          <label>
            Marker
            <select value={emoji} onChange={(e) => setEmoji(e.target.value)}>
              {EMOJI.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </label>
          <label className="grow">
            Description
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={400}
              placeholder="What belongs in here"
            />
          </label>
          <button className="btn" type="submit">
            Create
          </button>
        </form>
      )}

      {lists.length === 0 ? (
        <EmptyState
          title="No lists yet"
          body="Make one for comfort rewatches, one for the backlog you keep avoiding, one for whatever."
          action={
            <button type="button" className="btn" onClick={() => setCreating(true)}>
              Create a list
            </button>
          }
        />
      ) : (
        <div className="collection-grid">
          {lists.map((list) => (
            <article key={list.id} className="collection-card">
              <Link to={`/collections/${list.id}`} className="collection-covers">
                {list.covers.length > 0 ? (
                  list.covers.slice(0, 4).map((src, i) => <img key={`${src}-${i}`} src={src} alt="" />)
                ) : (
                  <span className="collection-empty">empty</span>
                )}
              </Link>
              <div className="collection-body">
                <h3>
                  <Link to={`/collections/${list.id}`}>
                    <em className="collection-mark">{list.emoji}</em> {list.name}
                  </Link>
                </h3>
                <p className="micro">{list.description || "No description"}</p>
                <p className="meta">{list.count} titles</p>
              </div>
              <button
                type="button"
                className="ghost-btn danger tiny"
                onClick={() => remove(list.id)}
              >
                Delete
              </button>
            </article>
          ))}
        </div>
      )}
      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}

export function CollectionDetail() {
  const { id } = useParams();
  const { token, user, loading } = useAuth();
  const [list, setList] = useState(null);
  const toast = useToast();

  const load = useCallback(async () => {
    setList(await api(`/api/collections/${id}`, { token }));
  }, [id, token]);

  useEffect(() => {
    if (token) load().catch((e) => toast.say(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (!list) {
    return (
      <Shell>
        <p className="pad">{toast.message || "Loading list..."}</p>
      </Shell>
    );
  }

  async function removeItem(anime) {
    await api(`/api/collections/${id}/items/${anime.id}`, { method: "DELETE", token });
    toast.say(`Removed ${anime.title}`);
    await load();
  }

  return (
    <Shell>
      <section className="panel-head">
        <div>
          <p className="eyebrow">List</p>
          <h1>
            <em className="collection-mark">{list.emoji}</em> {list.name}
          </h1>
          <p className="lede">{list.description || "Add titles from any detail page."}</p>
        </div>
        <span className="head-meta">{list.count} titles</span>
      </section>

      {list.items.length === 0 ? (
        <EmptyState
          title="This list is empty"
          body="Open a title, then pick this list from the Add to list menu."
          action={
            <Link className="btn" to="/">
              Find something
            </Link>
          }
        />
      ) : (
        <section className="tile-grid">
          {list.items.map((anime, i) => (
            <AnimeCard
              key={anime.id}
              anime={anime}
              token={token}
              surface="collection"
              position={i}
              onRemove={removeItem}
              removeLabel="Remove from this list"
            />
          ))}
        </section>
      )}
      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
