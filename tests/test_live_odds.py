"""Tests for ingestion.live_odds — parse a saved Odds API payload (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.live_odds import parse_odds_payload

_FIX = Path(__file__).parent / "fixtures" / "odds_api_sample.json"


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
