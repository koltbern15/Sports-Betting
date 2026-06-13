"""Tests for ingestion.live_odds — parse a saved Odds API payload (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.live_odds import get_api_key, parse_odds_payload

_FIX = Path(__file__).parent / "fixtures" / "odds_api_sample.json"


def _valid_event():
    """A minimal but well-formed Odds API event (one book, all three markets)."""
    return {
        "id": "evt1",
        "commence_time": "2026-09-07T17:00:00Z",
        "home_team": "Kansas City Chiefs",
        "away_team": "Buffalo Bills",
        "bookmakers": [
            {"key": "draftkings", "title": "DraftKings", "markets": [
                {"key": "spreads", "outcomes": [
                    {"name": "Kansas City Chiefs", "price": -110, "point": -2.5},
                    {"name": "Buffalo Bills", "price": -110, "point": 2.5}]},
                {"key": "totals", "outcomes": [
                    {"name": "Over", "price": -110, "point": 48.5},
                    {"name": "Under", "price": -110, "point": 48.5}]},
                {"key": "h2h", "outcomes": [
                    {"name": "Kansas City Chiefs", "price": -140},
                    {"name": "Buffalo Bills", "price": 120}]}
            ]},
        ],
    }


def _games():
    return parse_odds_payload(json.loads(_FIX.read_text(encoding="utf-8")))


def test_parses_one_game_canonical_teams():
    games = _games()
    assert len(games) == 1
    g = games[0]
    assert g.home_team == "Kansas City Chiefs"
    assert g.away_team == "Buffalo Bills"
    assert g.n_books == 2
    assert g.game_key == "2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs"


def test_consensus_is_median_home_perspective():
    g = _games()[0]
    assert g.cons_spread_home == -2.75
    assert g.cons_total == 48.75
    assert g.cons_ml_home == -145
    assert g.cons_ml_away == 125


def test_best_ml_is_highest_price_per_side():
    g = _games()[0]
    assert g.best_ml_home[0] == "DraftKings"
    assert g.best_ml_home[2] == -140
    assert g.best_ml_away[0] == "FanDuel"
    assert g.best_ml_away[2] == 130


def test_best_spread_home_prefers_more_points_then_price():
    g = _games()[0]
    assert g.best_spread_home[0] == "DraftKings"
    assert g.best_spread_home[1] == -2.5


def test_best_total_over_prefers_lower_line():
    g = _games()[0]
    assert g.best_total_over[0] == "DraftKings"
    assert g.best_total_over[1] == 48.5
    assert g.best_total_under[1] == 49.0


def test_unknown_team_skips_game_not_crash():
    payload = [{
        "id": "x", "commence_time": "2026-09-07T17:00:00Z",
        "home_team": "Springfield Isotopes", "away_team": "Buffalo Bills",
        "bookmakers": [],
    }]
    assert parse_odds_payload(payload) == []


def test_fetch_odds_http_error_is_clean_runtimeerror(monkeypatch):
    """A 401 (bad key) surfaces as a clean RuntimeError, never a raw traceback,
    and the key never appears in the message."""
    import io
    import urllib.error
    import urllib.request

    from ingestion import live_odds

    def _raise(*_a, **_k):
        raise urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, io.BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    with pytest.raises(RuntimeError) as exc:
        live_odds.fetch_odds(api_key="SECRET_DUMMY_KEY")
    msg = str(exc.value)
    assert "401" in msg
    assert "SECRET_DUMMY_KEY" not in msg


# --- Bug 1: robustness — one malformed event/outcome must not sink the snapshot ---

def test_outcome_missing_price_is_skipped_not_crash():
    """An outcome with no 'price' key is dropped; the game still parses."""
    evt = _valid_event()
    # Drop the price from the home moneyline outcome.
    del evt["bookmakers"][0]["markets"][2]["outcomes"][0]["price"]
    games = parse_odds_payload([evt])
    assert len(games) == 1
    g = games[0]
    # Home ML had its only book dropped -> no consensus / best on that side.
    assert g.cons_ml_home is None
    assert g.best_ml_home is None
    # Away ML untouched.
    assert g.cons_ml_away == 120


def test_outcome_price_none_is_skipped_not_crash():
    """price=None is treated the same as missing — skipped, no TypeError."""
    evt = _valid_event()
    evt["bookmakers"][0]["markets"][2]["outcomes"][0]["price"] = None
    games = parse_odds_payload([evt])
    assert len(games) == 1
    assert games[0].cons_ml_home is None
    assert games[0].best_ml_home is None


def test_event_missing_commence_time_is_skipped_not_crash():
    """An event with no 'commence_time' is skipped rather than crashing the parse."""
    evt = _valid_event()
    del evt["commence_time"]
    assert parse_odds_payload([evt]) == []


def test_valid_game_survives_alongside_malformed_game():
    """The crucial case: one good game + one broken game -> good game returned,
    no exception propagates out of parse_odds_payload."""
    good = _valid_event()
    bad = _valid_event()
    bad["id"] = "evt2"
    del bad["commence_time"]  # this event is malformed
    games = parse_odds_payload([good, bad])
    assert len(games) == 1
    assert games[0].game_key == "2026-09-07_Buffalo_Bills_at_Kansas_City_Chiefs"
    assert games[0].home_team == "Kansas City Chiefs"


# --- Bug 2: get_api_key coverage (env + .env fallback) ---

def test_get_api_key_from_env_is_stripped(monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "  DUMMY_ENV_KEY  ")
    assert get_api_key() == "DUMMY_ENV_KEY"


def test_get_api_key_from_env_file_strips_quotes(monkeypatch, tmp_path):
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('ODDS_API_KEY="DUMMY_FILE_KEY"\n', encoding="utf-8")
    monkeypatch.setattr("ingestion.live_odds._ENV_FILE", env_file)
    assert get_api_key() == "DUMMY_FILE_KEY"


def test_get_api_key_env_wins_over_env_file(monkeypatch, tmp_path):
    monkeypatch.setenv("ODDS_API_KEY", "DUMMY_ENV_WINS")
    env_file = tmp_path / ".env"
    env_file.write_text("ODDS_API_KEY=DUMMY_FILE_LOSES\n", encoding="utf-8")
    monkeypatch.setattr("ingestion.live_odds._ENV_FILE", env_file)
    assert get_api_key() == "DUMMY_ENV_WINS"


def test_get_api_key_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    # Point _ENV_FILE at a path that does not exist.
    monkeypatch.setattr("ingestion.live_odds._ENV_FILE", tmp_path / "does_not_exist.env")
    assert get_api_key() is None
