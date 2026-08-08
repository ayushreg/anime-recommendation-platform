"""Unit tests for the pure logic: no database, no Redis, no network."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from datetime import datetime, timedelta, timezone

from app.migrate import DEFAULT_RUNTIME_BY_TYPE, franchise_key_for
from app.models import Anime
from app.services.attention import AttentionRow, pretty_tag, rerank
from app.services.library import episode_seconds_for
from app.services.ordering import is_adult
from app.services.recommender import _decay
from app.services.taste import QUIZ, score_answers


def _anime(**kwargs) -> Anime:
    defaults = dict(id=1, title="Test", genres="Action", themes="", type="TV")
    defaults.update(kwargs)
    return Anime(**defaults)


class TestFranchiseKeys:
    def test_strips_season_and_format_words(self):
        assert franchise_key_for("Attack on Titan Season 3 Part 2") == franchise_key_for(
            "Attack on Titan"
        )

    def test_stops_at_a_subtitle(self):
        assert franchise_key_for("Fullmetal Alchemist: Brotherhood").startswith(
            "fullmetal alchemist"
        )

    def test_distinct_shows_stay_distinct(self):
        assert franchise_key_for("One Piece") != franchise_key_for("One Punch Man")

    def test_never_returns_empty(self):
        assert franchise_key_for("2")
        assert franchise_key_for("")== ""


class TestAdultFilter:
    def test_flags_adult_tags(self):
        assert is_adult(_anime(genres="adult audience only, erotica, hentai"))
        assert is_adult(_anime(genres="comedy", themes="borderline porn"))

    def test_leaves_ordinary_titles_alone(self):
        assert not is_adult(_anime(genres="Action, Adventure", themes="Friendship"))
        assert not is_adult(_anime(genres="", themes=""))


class TestEpisodeLength:
    def test_prefers_the_catalog_runtime(self):
        assert episode_seconds_for(_anime(duration_minutes=47), None) == 47 * 60

    def test_falls_back_by_type(self):
        assert episode_seconds_for(_anime(type="Movie"), None) == (
            DEFAULT_RUNTIME_BY_TYPE["Movie"] * 60
        )

    def test_never_returns_zero(self):
        assert episode_seconds_for(_anime(type="Unknown", duration_minutes=0), None) >= 60


class TestRatingDecay:
    def test_today_counts_fully(self):
        assert _decay(datetime.now(timezone.utc)) > 0.99

    def test_old_ratings_fade(self):
        old = datetime.now(timezone.utc) - timedelta(days=240)
        assert _decay(old) < 0.3

    def test_handles_naive_timestamps(self):
        assert 0 < _decay(datetime.utcnow()) <= 1.0

    def test_missing_timestamp_is_neutral(self):
        assert _decay(None) == 1.0


class TestAttentionScore:
    def _row(self, **kwargs):
        defaults = dict(
            anime_id=1,
            views=0,
            hovers=0,
            clicks=0,
            dwell_ms=0,
            watch_seconds=0,
            progress=0,
            rating=None,
            completed=False,
        )
        defaults.update(kwargs)
        return AttentionRow(**defaults)

    def test_nothing_scores_zero(self):
        assert self._row().score == 0.0

    def test_finishing_beats_scrolling(self):
        scrolled = self._row(views=20, dwell_ms=4000)
        finished = self._row(views=2, clicks=1, watch_seconds=7200, rating=9, completed=True)
        assert finished.score > scrolled.score

    def test_stays_bounded(self):
        huge = self._row(views=1, clicks=1, dwell_ms=10**7, watch_seconds=10**6, rating=10, completed=True)
        assert 0.0 <= huge.score <= 1.0


class TestRerank:
    def test_fatigue_sinks_a_title_you_keep_skipping(self):
        fresh = _anime(id=1, title="Fresh", genres="Action")
        stale = _anime(id=2, title="Stale", genres="Action")
        ranked = rerank(
            [fresh, stale],
            base_scores={1: 0.5, 2: 0.5},
            affinity={"Action": 0.9},
            views={2: 10},
            penalties={},
            diversity=0.2,
        )
        assert ranked[0][0].id == 1

    def test_diversity_rewards_untouched_tags(self):
        known = _anime(id=1, title="Known", genres="Action")
        novel = _anime(id=2, title="Novel", genres="Sports")
        ranked = rerank(
            [known, novel],
            base_scores={1: 0.5, 2: 0.5},
            affinity={"Action": 0.9},
            views={},
            penalties={},
            diversity=1.0,
        )
        assert ranked[0][0].id == 2

    def test_every_row_gets_a_reason(self):
        ranked = rerank(
            [_anime(id=1)],
            base_scores={1: 0.5},
            affinity={},
            views={},
            penalties={},
        )
        assert ranked[0][2]


class TestQuiz:
    def test_every_question_has_choices_with_tags(self):
        assert len(QUIZ) >= 10
        for question in QUIZ:
            assert question["prompt"]
            assert len(question["choices"]) >= 2
            for choice in question["choices"]:
                assert choice["tags"].strip()

    def test_answers_become_normalized_weights(self):
        weights = score_answers([("energy", "loud"), ("world", "elsewhere")])
        assert weights
        assert max(weights.values()) == 1.0
        assert all(0 < v <= 1 for v in weights.values())

    def test_unknown_answers_are_ignored(self):
        assert score_answers([("nope", "nope")]) == {}


class TestPrettyTag:
    def test_merges_casing_variants(self):
        assert pretty_tag("action") == pretty_tag("Action") == "Action"

    def test_keeps_small_words_lowercase(self):
        assert pretty_tag("slice of life") == "Slice of Life"

    def test_handles_hyphens(self):
        assert pretty_tag("sci-fi") == "Sci-Fi"
