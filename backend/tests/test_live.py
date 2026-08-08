"""Live data: normalizing, error wording, and the flag gate.

Nothing here touches the network. The provider payloads below are trimmed
copies of real AniList and Jikan responses, so a shape change upstream shows up
as a failing assertion rather than an empty grid in the browser.
"""

# Database and flag environment come from conftest.py.

from datetime import date, datetime, timezone

import httpx
import pytest

from app.services import live

# One AniList media node, trimmed to the fields the query actually asks for.
MEDIA = {
    "idMal": 21,
    "title": {"romaji": "ONE PIECE", "english": "One Piece"},
    "description": "Gol D. Roger was known as the <b>Pirate King</b>.<br>The story.",
    "format": "TV",
    "episodes": None,
    "duration": 24,
    "season": "FALL",
    "seasonYear": 1999,
    "startDate": {"year": 1999, "month": 10, "day": 20},
    "endDate": {"year": None, "month": None, "day": None},
    "nextAiringEpisode": {"episode": 1173, "airingAt": 1786_000_000},
    "coverImage": {"large": "https://s4.anilist.co/cover.jpg"},
    "studios": {"nodes": [{"name": "Toei Animation"}]},
    "genres": ["Action", "Adventure", "Comedy"],
    "popularity": 12345,
}


class TestNormalizeMedia:
    def test_maps_a_full_node(self):
        row = live.normalize_media(MEDIA)
        assert row["mal_id"] == 21
        assert row["title"] == "ONE PIECE"
        assert row["title_english"] == "One Piece"
        assert row["genres"] == "Action, Adventure, Comedy"
        assert row["studios"] == "Toei Animation"
        assert row["type"] == "TV"
        assert row["season"] == "fall"
        assert row["next_episode"] == 1173
        assert row["start_date"] == date(1999, 10, 20)

    def test_strips_html_out_of_the_synopsis(self):
        # AniList returns markup even with asHtml: false.
        assert "<b>" not in live.normalize_media(MEDIA)["synopsis"]
        assert "Pirate King" in live.normalize_media(MEDIA)["synopsis"]

    def test_airing_time_is_utc_aware(self):
        airs = live.normalize_media(MEDIA)["next_episode_at"]
        assert airs.tzinfo is not None
        assert airs == datetime.fromtimestamp(1786_000_000, tz=timezone.utc)

    def test_partial_dates_survive(self):
        """Anything far out has a year and no day yet."""
        row = live.normalize_media({**MEDIA, "startDate": {"year": 2027, "month": 4, "day": None}})
        assert row["start_date"] == date(2027, 4, 1)

    def test_unannounced_date_is_none_not_epoch(self):
        row = live.normalize_media({**MEDIA, "startDate": {"year": None}})
        assert row["start_date"] is None

    def test_rows_without_a_mal_id_are_dropped(self):
        """idMal is the only key that lines a live row up with the catalog."""
        assert live.normalize_media({**MEDIA, "idMal": None}) is None

    def test_untitled_rows_are_dropped(self):
        assert live.normalize_media({**MEDIA, "title": {"romaji": "", "english": ""}}) is None

    def test_missing_countdown_is_none(self):
        row = live.normalize_media({**MEDIA, "nextAiringEpisode": None})
        assert row["next_episode_at"] is None
        assert row["next_episode"] is None

    def test_format_falls_back_to_tv(self):
        assert live.normalize_media({**MEDIA, "format": "SOMETHING_NEW"})["type"] == "TV"
        assert live.normalize_media({**MEDIA, "format": "MOVIE"})["type"] == "Movie"


class TestCacheRoundTrip:
    def test_dates_survive_json(self):
        """Redis holds JSON, so dates have to go out and come back intact."""
        rows = [live.normalize_media(MEDIA)]
        revived = live.revive(live._jsonable(rows))
        assert revived[0]["start_date"] == rows[0]["start_date"]
        assert revived[0]["next_episode_at"] == rows[0]["next_episode_at"]
        assert revived[0]["next_episode_at"].tzinfo is not None


def _transport(status, payload):
    return httpx.MockTransport(lambda request: httpx.Response(status, json=payload))


@pytest.fixture
def mock_http(monkeypatch):
    """Swap httpx.Client for one that answers from a canned response."""

    def install(status, payload):
        real = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = _transport(status, payload)
            return real(*args, **kwargs)

        monkeypatch.setattr(httpx, "Client", factory)

    return install


class TestErrorWording:
    """The whole feature is "type a username", so these messages are the UI."""

    def test_unknown_user_names_the_username(self, mock_http):
        mock_http(404, {"errors": [{"message": "User not found"}], "data": None})
        with pytest.raises(live.LiveUnavailable) as exc:
            live.fetch_anilist_list("ghost")
        assert "ghost" in str(exc.value)

    def test_private_list_says_so(self, mock_http):
        mock_http(404, {"errors": [{"message": "Private User"}], "data": None})
        with pytest.raises(live.LiveUnavailable) as exc:
            live.fetch_anilist_list("someone")
        assert "private" in str(exc.value).lower()

    def test_graphql_error_body_beats_the_status_code(self, mock_http):
        """A 4xx with an explanation should surface the explanation."""
        mock_http(400, {"errors": [{"message": "Something specific"}]})
        with pytest.raises(live.LiveUnavailable) as exc:
            live._anilist("query {}", {})
        assert "Something specific" in str(exc.value)

    def test_rate_limit_is_its_own_message(self, mock_http):
        mock_http(429, {})
        with pytest.raises(live.LiveUnavailable) as exc:
            live._anilist("query {}", {})
        assert "rate limit" in str(exc.value).lower()

    def test_jikan_passes_its_own_explanation_through(self, mock_http):
        """Jikan explains a failed MyAnimeList scrape better than we could."""
        mock_http(504, {"message": "Jikan failed to connect to MyAnimeList"})
        with pytest.raises(live.LiveUnavailable) as exc:
            live.fetch_mal_list("someone")
        assert "MyAnimeList" in str(exc.value)

    def test_empty_public_list_is_an_error_not_a_silent_zero(self, mock_http):
        mock_http(200, {"data": {"MediaListCollection": {"lists": []}}})
        with pytest.raises(live.LiveUnavailable):
            live.fetch_anilist_list("someone")


class TestListMapping:
    def test_maps_anilist_statuses_to_shelf_buckets(self, mock_http):
        mock_http(
            200,
            {
                "data": {
                    "MediaListCollection": {
                        "lists": [
                            {
                                "entries": [
                                    {
                                        "status": "CURRENT",
                                        "score": 8,
                                        "progress": 12,
                                        "repeat": 1,
                                        "media": {"idMal": 21, "title": {"romaji": "ONE PIECE"}},
                                    },
                                    {
                                        "status": "PLANNING",
                                        "score": 0,
                                        "progress": 0,
                                        "repeat": 0,
                                        "media": {"idMal": 5, "title": {"romaji": "Cowboy Bebop"}},
                                    },
                                ]
                            }
                        ]
                    }
                }
            },
        )
        entries = live.fetch_anilist_list("someone")
        assert [e["status"] for e in entries] == ["watching", "plan_to_watch"]
        assert entries[0]["progress"] == 12
        assert entries[0]["rewatches"] == 1


class TestFlagGate:
    """Live data is on out of the box; the flag is a kill switch, not a setup step."""

    def test_live_data_ships_on(self):
        import json
        from pathlib import Path

        shipped = json.loads(
            (Path(__file__).resolve().parent.parent / "app" / "feature_flags.json").read_text()
        )
        assert shipped["live_data"] is True
