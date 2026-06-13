"""Tests for ingestion.opening_line_aus — parse the xlsx fixture."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ingestion import opening_line_aus
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


def test_bad_row_is_skipped_not_fatal(monkeypatch):
    """One corrupt row (garbage team -> KeyError) is dropped; good rows survive.

    Exercises the `except (KeyError, ValueError, TypeError): continue` path
    (opening_line_aus.py:74), which the clean xlsx fixture never hits. We feed
    parse_aus_xlsx an in-memory DataFrame via the same pd.read_excel entry point
    rather than regenerating the binary fixture.
    """
    df = pd.DataFrame(
        [
            {
                "Date": "2015-09-13",
                "Home Team": "Dallas Cowboys",
                "Away Team": "New York Giants",
                "Home Line Open": -3.5,
                "Total Score Open": 47.5,
                "Home Odds Open": 1.50,
                "Away Odds Open": 2.60,
            },
            {
                # garbage home team -> canonical_team raises KeyError -> row skipped
                "Date": "2015-09-20",
                "Home Team": "Springfield Isotopes",
                "Away Team": "New York Giants",
                "Home Line Open": -1.5,
                "Total Score Open": 44.0,
                "Home Odds Open": 1.80,
                "Away Odds Open": 2.10,
            },
            {
                "Date": "2015-09-27",
                "Home Team": "Carolina Panthers",
                "Away Team": "New Orleans Saints",
                "Home Line Open": -6.0,
                "Total Score Open": 48.0,
                "Home Odds Open": 1.40,
                "Away Odds Open": 3.00,
            },
        ]
    )
    monkeypatch.setattr(opening_line_aus.pd, "read_excel", lambda _path: df)

    recs = parse_aus_xlsx("ignored.xlsx")

    # The bad middle row is silently dropped; the two good rows survive (no raise).
    assert len(recs) == 2
    homes = {r.home_team for r in recs}
    assert homes == {"Dallas Cowboys", "Carolina Panthers"}


def test_bad_cell_is_skipped_not_fatal(monkeypatch):
    """A non-numeric odds cell (TypeError on float()) drops only that row."""
    df = pd.DataFrame(
        [
            {
                "Date": "2015-09-13",
                "Home Team": "Dallas Cowboys",
                "Away Team": "New York Giants",
                "Home Line Open": -3.5,
                "Total Score Open": 47.5,
                "Home Odds Open": 1.50,
                "Away Odds Open": 2.60,
            },
            {
                # non-numeric spread -> float() raises -> row skipped
                "Date": "2015-09-20",
                "Home Team": "Carolina Panthers",
                "Away Team": "New Orleans Saints",
                "Home Line Open": "garbage",
                "Total Score Open": 44.0,
                "Home Odds Open": 1.80,
                "Away Odds Open": 2.10,
            },
        ]
    )
    monkeypatch.setattr(opening_line_aus.pd, "read_excel", lambda _path: df)

    recs = parse_aus_xlsx("ignored.xlsx")

    assert len(recs) == 1
    assert recs[0].home_team == "Dallas Cowboys"
