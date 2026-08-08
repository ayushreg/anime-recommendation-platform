"""The one place in Kura that talks to the open internet.

Everything else in this codebase reads Postgres. This module is the only
exception, and it is read-only in both directions: Kura pulls airing schedules
and public lists, and never pushes a single byte back to anybody's tracker.

Two providers, picked for different reasons:

* **AniList** is a real GraphQL API rather than a scraper, it hands back an exact
  UTC instant for the next episode of every airing show, and every row carries an
  `idMal`, which is the key the offline catalog is already built on. It is the
  primary source for both airing data and list syncing.
* **Jikan** proxies MyAnimeList by scraping it, which makes it the flakier of the
  two, so it is used only for the MAL list link and its own error text is passed
  straight through to the UI when it fails.

Every function here raises `LiveUnavailable` rather than letting an httpx error
escape, so a caller can turn any network problem into one clear message.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.services.cache import cache_get, cache_set

# AniList format -> the `type` vocabulary the offline catalog already uses.
FORMAT_TO_TYPE = {
    "TV": "TV",
    "TV_SHORT": "TV",
    "MOVIE": "Movie",
    "SPECIAL": "Special",
    "OVA": "OVA",
    "ONA": "ONA",
    "MUSIC": "Music",
}

ANILIST_STATUS_MAP = {
    "COMPLETED": "completed",
    "CURRENT": "watching",
    "PAUSED": "on_hold",
    "DROPPED": "dropped",
    "PLANNING": "plan_to_watch",
    "REPEATING": "watching",
}

# MyAnimeList numbers its shelves. These are the codes its own list page uses.
MAL_STATUS_BY_CODE = {
    1: "watching",
    2: "completed",
    3: "on_hold",
    4: "dropped",
    6: "plan_to_watch",
}

MAL_STATUS_MAP = {
    "completed": "completed",
    "watching": "watching",
    "on_hold": "on_hold",
    "on-hold": "on_hold",
    "dropped": "dropped",
    "plan_to_watch": "plan_to_watch",
    "plantowatch": "plan_to_watch",
}

_HTML = re.compile(r"<[^>]+>")

# One query serves the upcoming grid and the airing countdown; only the status
# variable changes. isAdult is filtered at the source so adult rows never even
# reach this machine, which matches how the offline catalog is treated.
MEDIA_PAGE_QUERY = """
query ($page: Int, $perPage: Int, $status: MediaStatus) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage }
    media(type: ANIME, status: $status, sort: POPULARITY_DESC, isAdult: false) {
      idMal
      title { romaji english }
      description(asHtml: false)
      format
      episodes
      duration
      season
      seasonYear
      startDate { year month day }
      endDate { year month day }
      nextAiringEpisode { episode airingAt }
      coverImage { large }
      studios(isMain: true) { nodes { name } }
      genres
      popularity
    }
  }
}
"""

USER_LIST_QUERY = """
query ($name: String) {
  MediaListCollection(userName: $name, type: ANIME) {
    lists {
      entries {
        status
        score(format: POINT_10)
        progress
        repeat
        media { idMal title { romaji english } }
      }
    }
  }
}
"""


class LiveUnavailable(RuntimeError):
    """A live source could not be reached, or answered with an error.

    Carries a message written for a person, because it is shown verbatim in the
    UI. "MyAnimeList refused the connection" beats "sync failed".
    """


# ------------------------------------------------------------------ transport


def _anilist(query: str, variables: dict[str, Any]) -> dict:
    try:
        with httpx.Client(timeout=settings.live_timeout_seconds) as client:
            resp = client.post(
                settings.anilist_url,
                json={"query": query, "variables": variables},
                headers={"Accept": "application/json"},
            )
    except Exception as exc:
        raise LiveUnavailable(
            "Could not reach AniList. Check this machine's connection and try again."
        ) from exc

    if resp.status_code == 429:
        raise LiveUnavailable("AniList is rate limiting this machine. Try again in a minute.")

    # AniList explains itself in the body even when it answers 4xx: a bad
    # username comes back as 404 "User not found", and a locked profile as 404
    # "Private User". Those two need to read differently on the settings page,
    # so parse the body before looking at the status code.
    try:
        body = resp.json()
    except ValueError as exc:
        if resp.status_code >= 400:
            raise LiveUnavailable(f"AniList answered {resp.status_code}.") from exc
        raise LiveUnavailable("AniList sent something that was not JSON.") from exc

    if body.get("errors"):
        first = (body["errors"] or [{}])[0]
        raise LiveUnavailable(str(first.get("message") or "AniList rejected that query."))
    if resp.status_code >= 400:
        raise LiveUnavailable(f"AniList answered {resp.status_code}.")
    return body.get("data") or {}


def _jikan(path: str, params: dict[str, Any] | None = None) -> dict:
    url = f"{settings.jikan_base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        with httpx.Client(timeout=settings.live_timeout_seconds) as client:
            resp = client.get(url, params=params or {})
    except Exception as exc:
        raise LiveUnavailable(
            "Could not reach Jikan. Check this machine's connection and try again."
        ) from exc

    if resp.status_code == 429:
        raise LiveUnavailable("Jikan is rate limiting this machine. Try again in a minute.")
    if resp.status_code == 404:
        raise LiveUnavailable("That username has no public list on MyAnimeList.")

    if resp.status_code >= 400:
        # Jikan explains itself well when its MyAnimeList scrape fails, and that
        # is exactly the case a user needs to see, so pass its wording through.
        detail = ""
        try:
            detail = str((resp.json() or {}).get("message") or "")
        except ValueError:
            detail = ""
        raise LiveUnavailable(detail or f"Jikan answered {resp.status_code}.")

    try:
        return resp.json() or {}
    except ValueError as exc:
        raise LiveUnavailable("Jikan sent something that was not JSON.") from exc


# ---------------------------------------------------------------- normalizing


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    return _HTML.sub(" ", text).replace("&nbsp;", " ").strip() or None


def _fuzzy_date(node: dict | None) -> date | None:
    """AniList dates are partial for anything far out: 2026 with no day yet."""
    if not node or not node.get("year"):
        return None
    try:
        return date(int(node["year"]), int(node.get("month") or 1), int(node.get("day") or 1))
    except (TypeError, ValueError):
        return None


def normalize_media(media: dict) -> dict | None:
    """One AniList media node -> the shape the catalog and airing table want.

    Returns None for rows with no `idMal`, because that id is the only reliable
    way to line a live row up against the offline dump. Without it we would be
    matching on title text and inventing duplicates.
    """
    mal_id = media.get("idMal")
    if not mal_id:
        return None

    titles = media.get("title") or {}
    romaji = (titles.get("romaji") or titles.get("english") or "").strip()
    if not romaji:
        return None

    next_ep = media.get("nextAiringEpisode") or {}
    airing_at = next_ep.get("airingAt")
    studios = [n.get("name") for n in ((media.get("studios") or {}).get("nodes") or []) if n]

    return {
        "mal_id": int(mal_id),
        "title": romaji[:512],
        "title_english": (titles.get("english") or None),
        "synopsis": _clean(media.get("description")),
        "genres": ", ".join((media.get("genres") or [])[:8]),
        "studios": ", ".join(studios[:4]),
        "episodes": media.get("episodes"),
        "duration_minutes": media.get("duration"),
        "type": FORMAT_TO_TYPE.get(media.get("format") or "", "TV"),
        "season": (media.get("season") or "").lower() or None,
        "year": media.get("seasonYear"),
        "image_url": (media.get("coverImage") or {}).get("large"),
        "next_episode": next_ep.get("episode"),
        "next_episode_at": (
            datetime.fromtimestamp(int(airing_at), tz=timezone.utc) if airing_at else None
        ),
        "start_date": _fuzzy_date(media.get("startDate")),
        "end_date": _fuzzy_date(media.get("endDate")),
        "source_popularity": int(media.get("popularity") or 0),
    }


# -------------------------------------------------------------------- fetches


def _fetch_media_page(status: str, page: int, per_page: int) -> tuple[list[dict], bool]:
    data = _anilist(
        MEDIA_PAGE_QUERY, {"page": page, "perPage": per_page, "status": status}
    )
    node = data.get("Page") or {}
    rows = [normalize_media(m) for m in (node.get("media") or [])]
    has_next = bool((node.get("pageInfo") or {}).get("hasNextPage"))
    return [r for r in rows if r], has_next


def fetch_airing(status: str, *, limit: int = 100, use_cache: bool = True) -> list[dict]:
    """Pull `limit` titles for one AniList status, most popular first.

    `status` is AniList's vocabulary: RELEASING for shows mid-run,
    NOT_YET_RELEASED for the upcoming grid.
    """
    key = f"live:media:{status}:{limit}"
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            return cached

    per_page = min(50, max(1, limit))
    rows: list[dict] = []
    page = 1
    while len(rows) < limit:
        batch, has_next = _fetch_media_page(status, page, per_page)
        rows.extend(batch)
        if not has_next or not batch:
            break
        page += 1

    rows = rows[:limit]
    cache_set(key, _jsonable(rows), settings.live_cache_ttl_seconds)
    return rows


def _jsonable(rows: list[dict]) -> list[dict]:
    """Dates and datetimes do not survive the JSON round trip into Redis."""
    out = []
    for row in rows:
        copy = dict(row)
        for field in ("next_episode_at", "start_date", "end_date"):
            value = copy.get(field)
            if isinstance(value, (datetime, date)):
                copy[field] = value.isoformat()
        out.append(copy)
    return out


def revive(rows: list[dict]) -> list[dict]:
    """Inverse of `_jsonable`, for rows that came back out of the cache."""
    out = []
    for row in rows:
        copy = dict(row)
        raw = copy.get("next_episode_at")
        if isinstance(raw, str):
            parsed = datetime.fromisoformat(raw)
            copy["next_episode_at"] = (
                parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            )
        for field in ("start_date", "end_date"):
            value = copy.get(field)
            if isinstance(value, str):
                copy[field] = date.fromisoformat(value[:10])
        out.append(copy)
    return out


MEDIA_BY_ID_QUERY = """
query ($ids: [Int]) {
  Page(page: 1, perPage: 50) {
    media(idMal_in: $ids, type: ANIME) {
      idMal
      title { romaji english }
      description(asHtml: false)
      format
      episodes
      duration
      season
      seasonYear
      startDate { year month day }
      endDate { year month day }
      nextAiringEpisode { episode airingAt }
      coverImage { large }
      studios(isMain: true) { nodes { name } }
      genres
      popularity
    }
  }
}
"""


def fetch_media_by_mal_ids(mal_ids: list[int]) -> list[dict]:
    """Look up specific titles by MyAnimeList id, 50 at a time.

    The offline dump is a subset, so a real tracker list always contains titles
    this vault has never heard of. Rather than dropping those rows on import,
    they get fetched by the exact id the list already gave us.
    """
    wanted = [int(i) for i in mal_ids if i]
    rows: list[dict] = []
    for start in range(0, len(wanted), 50):
        chunk = wanted[start : start + 50]
        data = _anilist(MEDIA_BY_ID_QUERY, {"ids": chunk})
        for media in ((data.get("Page") or {}).get("media") or []):
            row = normalize_media(media)
            if row:
                rows.append(row)
    return rows


def fetch_anilist_list(username: str) -> list[dict]:
    """Every anime entry on a public AniList profile."""
    try:
        data = _anilist(USER_LIST_QUERY, {"name": username})
    except LiveUnavailable as exc:
        # AniList's own wording for these two is accurate but bare, and they are
        # by far the most likely things to go wrong when somebody types a name.
        message = str(exc)
        if message == "User not found":
            raise LiveUnavailable(f"AniList has no user called {username}.") from exc
        if message == "Private User":
            raise LiveUnavailable(
                f"{username} exists on AniList, but their list is private. "
                "Kura can only read public lists."
            ) from exc
        raise

    collection = data.get("MediaListCollection")
    if collection is None:
        raise LiveUnavailable(f"No public AniList profile for {username}.")

    entries: list[dict] = []
    for group in collection.get("lists") or []:
        for entry in group.get("entries") or []:
            media = entry.get("media") or {}
            titles = media.get("title") or {}
            entries.append(
                {
                    "mal_id": media.get("idMal"),
                    "title": titles.get("english") or titles.get("romaji"),
                    "status": ANILIST_STATUS_MAP.get(entry.get("status") or ""),
                    "progress": entry.get("progress") or 0,
                    "score": entry.get("score") or None,
                    "rewatches": entry.get("repeat") or 0,
                }
            )
    if not entries:
        raise LiveUnavailable(
            f"AniList answered, but {username} has no anime entries or the list is private."
        )
    return entries


def _mal_direct(username: str) -> list[dict]:
    """Read a public list from the JSON endpoint MyAnimeList's own list page calls.

    This is the same request your browser makes when you open someone's list, so
    it needs no app registration, no token, and no third party in the middle. It
    is also the only MAL path that currently works: Jikan proxies MyAnimeList by
    scraping it, and that scrape is regularly refused upstream.
    """
    entries: list[dict] = []
    offset = 0
    while offset <= 3000:  # MAL pages 300 at a time; this is past any real list
        try:
            with httpx.Client(timeout=settings.live_timeout_seconds) as client:
                resp = client.get(
                    f"{settings.mal_list_url.rstrip('/')}/{username}/load.json",
                    params={"offset": offset, "status": 7},
                    headers={
                        # MAL serves this endpoint to browsers; a default httpx
                        # agent gets turned away.
                        "User-Agent": settings.mal_user_agent,
                        "Accept": "application/json",
                        "Referer": f"{settings.mal_list_url.rstrip('/')}/{username}",
                    },
                )
        except Exception as exc:
            raise LiveUnavailable(
                "Could not reach MyAnimeList from this machine. Kura stays usable offline."
            ) from exc

        if resp.status_code == 400:
            # What MAL answers for a name that does not exist, and for a list
            # whose owner has made it private.
            raise LiveUnavailable(
                f"MyAnimeList would not open a list for {username}. Check the spelling, "
                "and check that the list is public under Profile > List Settings."
            )
        if resp.status_code == 429:
            raise LiveUnavailable("MyAnimeList is rate limiting this machine. Try again shortly.")
        if resp.status_code >= 400:
            raise LiveUnavailable(f"MyAnimeList answered {resp.status_code}.")

        try:
            rows = resp.json()
        except ValueError as exc:
            raise LiveUnavailable(
                "MyAnimeList returned a page instead of list data, which usually means "
                "that list is not public."
            ) from exc

        if isinstance(rows, dict):
            message = ((rows.get("errors") or [{}])[0]).get("message") or "unknown error"
            raise LiveUnavailable(f"MyAnimeList said: {message}.")
        if not rows:
            break

        for row in rows:
            entries.append(
                {
                    "mal_id": row.get("anime_id"),
                    # Romaji first: the catalog's `title` column is romaji, and
                    # the matcher checks the English column against this same
                    # string anyway, so this loses nothing and matches more.
                    "title": row.get("anime_title") or row.get("anime_title_eng"),
                    "status": MAL_STATUS_BY_CODE.get(int(row.get("status") or 0)),
                    "progress": row.get("num_watched_episodes") or 0,
                    # MAL writes 0 for "not scored"; only 1..10 mean anything.
                    "score": row.get("score") or None,
                    "rewatches": row.get("num_watched_times") or 0,
                }
            )
        offset += 300

    return entries


def _mal_via_jikan(username: str) -> list[dict]:
    """Fallback path. Kept because it needs no browser-shaped request."""
    entries: list[dict] = []
    page = 1
    while page <= 8:
        body = _jikan(f"users/{username}/animelist", {"page": page})
        rows = body.get("data") or []
        if not rows:
            break
        for row in rows:
            node = row.get("entry") or row.get("anime") or row
            entries.append(
                {
                    "mal_id": node.get("mal_id"),
                    "title": node.get("title"),
                    "status": MAL_STATUS_MAP.get(
                        str(row.get("status") or "").strip().lower().replace(" ", "_")
                    ),
                    "progress": row.get("episodes_watched") or 0,
                    "score": row.get("score") or None,
                }
            )
        if not (body.get("pagination") or {}).get("has_next_page"):
            break
        page += 1
    return entries


def fetch_mal_list(username: str) -> list[dict]:
    """Every anime entry on a public MyAnimeList profile.

    Tries MyAnimeList itself first and falls back to Jikan. If the direct read
    fails for a reason the user can act on, a wrong name or a private list, that
    message wins: retrying through a proxy would only produce a vaguer version
    of the same answer.
    """
    try:
        entries = _mal_direct(username)
    except LiveUnavailable as direct_error:
        if "would not open a list" in str(direct_error):
            raise
        try:
            entries = _mal_via_jikan(username)
        except LiveUnavailable:
            raise direct_error from None

    if not entries:
        raise LiveUnavailable(
            f"{username} has a readable MyAnimeList profile, but no anime on it yet."
        )
    return entries


PROVIDER_FETCHERS = {
    "anilist": fetch_anilist_list,
    "mal": fetch_mal_list,
}

PROVIDER_LABELS = {
    "anilist": "AniList",
    "mal": "MyAnimeList",
}


def reachability() -> dict[str, Any]:
    """Cheap probe for the settings page: is the open internet usable at all?"""
    try:
        _anilist("query { Viewer { id } }", {})
        return {"reachable": True, "detail": "AniList answered."}
    except LiveUnavailable as exc:
        message = str(exc)
        # An unauthenticated Viewer query is *supposed* to come back empty. That
        # answer still proves the round trip worked, which is all we asked.
        if "not authenticated" in message.lower():
            return {"reachable": True, "detail": "AniList answered."}
        return {"reachable": False, "detail": message}
