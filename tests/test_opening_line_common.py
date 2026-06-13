"""Tests for ingestion.opening_line_common — pure record + normalization helpers."""

from __future__ import annotations

import pytest

from ingestion.opening_line_common import (
    OpeningLineRecord,
    canonical_team,
    decimal_to_american,
    normalize_spread_sign,
    to_iso_date,
    to_iso_date_mmdd,
)


def test_canonical_team_passthrough_known():
    assert canonical_team("Dallas Cowboys") == "Dallas Cowboys"


def test_canonical_team_normalizes_relocation():
    assert canonical_team("Oakland Raiders") == "Las Vegas Raiders"


def test_canonical_team_unknown_raises():
    with pytest.raises(KeyError):
        canonical_team("Springfield Isotopes")


def test_to_iso_date_from_mmdd_fall_game():
    assert to_iso_date_mmdd(913, 2015) == "2015-09-13"


def test_to_iso_date_from_mmdd_january_rolls_year():
    assert to_iso_date_mmdd(103, 2015) == "2016-01-03"


def test_to_iso_date_passthrough_date():
    import datetime
    assert to_iso_date(datetime.date(2015, 9, 13)) == "2015-09-13"


def test_to_iso_date_passthrough_datetime():
    import datetime
    assert to_iso_date(datetime.datetime(2015, 9, 13, 0, 0)) == "2015-09-13"


def test_normalize_spread_sign_home_favored_negative():
    assert normalize_spread_sign(3.0, home_is_favorite=True) == -3.0
    assert normalize_spread_sign(3.0, home_is_favorite=False) == 3.0


def test_decimal_to_american_favorite():
    assert decimal_to_american(1.50) == -200


def test_decimal_to_american_underdog():
    assert decimal_to_american(2.50) == 150


def test_decimal_to_american_none_passthrough():
    assert decimal_to_american(None) is None


def test_decimal_to_american_at_boundary_raises():
    # decimal odds of exactly 1.0 mean no payout -> invalid (opening_line_common.py:63-64)
    with pytest.raises(ValueError):
        decimal_to_american(1.0)


def test_decimal_to_american_below_boundary_raises():
    with pytest.raises(ValueError):
        decimal_to_american(0.5)


def test_record_is_frozen():
    import dataclasses

    r = OpeningLineRecord(
        season=2015, game_date="2015-09-13", home_team="Dallas Cowboys",
        away_team="New York Giants", open_spread_home=-3.0, open_total=47.0,
        open_ml_home=None, open_ml_away=None, source="sbr",
        source_url="http://example",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.season = 2016  # frozen
