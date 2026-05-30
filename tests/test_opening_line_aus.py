"""Tests for ingestion.opening_line_aus — parse the xlsx fixture."""

from __future__ import annotations

from pathlib import Path

from ingestion.opening_line_aus import parse_aus_xlsx

_FIX = Path(__file__).parent / "fixtures" / "aus_sample.xlsx"


def test_parses_two_games_skips_empty():
    recs = parse_aus_xlsx(_FIX)
    # Row C has no opener -> skipped; A and B remain
    assert len(recs) == 2


def test_row_a_values():
    recs = parse_aus_xlsx(_FIX)
    a = next(r for r in recs if r.home_team == "Dallas Cowboys")
    assert a.season == 2015
    assert a.game_date == "2015-09-13"
    assert a.away_team == "New York Giants"
    assert a.open_spread_home == -3.5
    assert a.open_total == 47.5
    assert a.open_ml_home == -200
    assert a.open_ml_away == 160
    assert a.source == "aus"


def test_super_bowl_season_rolls_back():
    recs = parse_aus_xlsx(_FIX)
    b = next(r for r in recs if r.home_team == "Carolina Panthers")
    # Feb 2016 game belongs to the 2015 season
    assert b.season == 2015
    assert b.game_date == "2016-02-07"
    assert b.open_ml_home == -250
    assert b.open_ml_away == 200
