import math

from ingestion.loader import derive_spread_home_close


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
