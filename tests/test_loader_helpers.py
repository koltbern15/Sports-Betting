import math

import pytest

from ingestion.loader import (
    derive_ats_result,
    derive_division_game_flag,
    derive_spread_home_close,
    derive_total_result,
    parse_week,
)


def test_home_favored():
    # Kaggle stores spread_favorite as a magnitude with a separate favorite-team id.
    # If team_favorite_id resolves to home, spread_home_close = -|spread|.
    assert derive_spread_home_close(spread_favorite=-7.0, favorite_is_home=True) == -7.0


def test_away_favored():
    # If team_favorite_id resolves to away, spread_home_close = +|spread|.
    assert derive_spread_home_close(spread_favorite=-3.5, favorite_is_home=False) == 3.5


def test_pickem_returns_zero():
    assert derive_spread_home_close(spread_favorite=0.0, favorite_is_home=True) == 0.0
    assert derive_spread_home_close(spread_favorite=0.0, favorite_is_home=False) == 0.0


def test_missing_spread_returns_none():
    assert derive_spread_home_close(spread_favorite=None, favorite_is_home=True) is None


def test_positive_input_normalized():
    # Defensive: if a row has positive spread_favorite for some reason,
    # treat its magnitude as the spread.
    assert derive_spread_home_close(spread_favorite=7.0, favorite_is_home=True) == -7.0
    assert derive_spread_home_close(spread_favorite=7.0, favorite_is_home=False) == 7.0


def test_nan_treated_as_missing():
    assert derive_spread_home_close(spread_favorite=math.nan, favorite_is_home=True) is None


def test_ats_home_favored_and_covers():
    # Home -7, final 28-17 → margin +11, beats the spread → cover for home side
    assert derive_ats_result(home_score=28, away_score=17, spread_home_close=-7.0) == "cover"


def test_ats_home_favored_and_loses():
    # Home -7, final 21-20 → margin +1, fails to cover → loss
    assert derive_ats_result(home_score=21, away_score=20, spread_home_close=-7.0) == "loss"


def test_ats_home_favored_push():
    # Home -7, final 24-17 → margin +7 exactly → push
    assert derive_ats_result(home_score=24, away_score=17, spread_home_close=-7.0) == "push"


def test_ats_home_underdog_covers():
    # Home +3, final 17-20 → margin -3 ; with +3 buffer → 0 exactly → push
    assert derive_ats_result(home_score=17, away_score=20, spread_home_close=3.0) == "push"
    # Home +3, final 20-21 → margin -1 + 3 = +2 → cover
    assert derive_ats_result(home_score=20, away_score=21, spread_home_close=3.0) == "cover"


def test_ats_pickem_outright_winner():
    # Pickem (0), home wins → home covers
    assert derive_ats_result(home_score=27, away_score=20, spread_home_close=0.0) == "cover"
    # Pickem (0), home loses → loss
    assert derive_ats_result(home_score=20, away_score=27, spread_home_close=0.0) == "loss"
    # Pickem (0), tie → push
    assert derive_ats_result(home_score=20, away_score=20, spread_home_close=0.0) == "push"


def test_ats_missing_inputs_returns_none():
    assert derive_ats_result(home_score=None, away_score=20, spread_home_close=-3.0) is None
    assert derive_ats_result(home_score=20, away_score=None, spread_home_close=-3.0) is None
    assert derive_ats_result(home_score=20, away_score=20, spread_home_close=None) is None


def test_total_over():
    assert derive_total_result(home_score=28, away_score=24, total_close=45.5) == "over"


def test_total_under():
    assert derive_total_result(home_score=10, away_score=7, total_close=45.5) == "under"


def test_total_push():
    assert derive_total_result(home_score=24, away_score=21, total_close=45.0) == "push"


def test_total_missing_returns_none():
    assert derive_total_result(home_score=None, away_score=21, total_close=45.0) is None
    assert derive_total_result(home_score=21, away_score=None, total_close=45.0) is None
    assert derive_total_result(home_score=21, away_score=21, total_close=None) is None


def test_parse_regular_season_week():
    assert parse_week("1") == 1
    assert parse_week("18") == 18


def test_parse_playoff_strings():
    assert parse_week("Wildcard") == 100
    assert parse_week("Division") == 101
    assert parse_week("Conference") == 102
    assert parse_week("Superbowl") == 103


def test_parse_week_integer_input():
    assert parse_week(5) == 5


def test_parse_unknown_raises():
    with pytest.raises(ValueError):
        parse_week("Preseason")


def test_same_division_returns_one():
    assert derive_division_game_flag("Kansas City Chiefs", "Denver Broncos") == 1


def test_same_conference_different_division_returns_zero():
    assert derive_division_game_flag("Kansas City Chiefs", "Buffalo Bills") == 0


def test_different_conference_returns_zero():
    assert derive_division_game_flag("Kansas City Chiefs", "Dallas Cowboys") == 0


def test_historical_name_inputs_handled():
    # Caller is expected to canonicalize names BEFORE this helper.
    # We document that requirement by asserting that an unknown (historical) name raises.
    with pytest.raises(KeyError):
        derive_division_game_flag("Oakland Raiders", "Kansas City Chiefs")
