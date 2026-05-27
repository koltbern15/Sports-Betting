"""CSV → SQLite loader for NFL betting data.

Pure derivation helpers are exported individually for unit testing.
The end-to-end orchestrator is ``load_csv_to_db``.
"""

from __future__ import annotations

import math


def derive_spread_home_close(
    spread_favorite: float | None,
    favorite_is_home: bool,
) -> float | None:
    """Convert (magnitude, favorite-is-home) to a home-perspective signed spread.

    Output convention:
      - negative = home favored
      - positive = home underdog
      - 0        = pick'em
      - None     = data missing
    """
    is_nan = isinstance(spread_favorite, float) and math.isnan(spread_favorite)
    if spread_favorite is None or is_nan:
        return None
    magnitude = abs(spread_favorite)
    return -magnitude if favorite_is_home else magnitude


def derive_ats_result(
    home_score: int | None,
    away_score: int | None,
    spread_home_close: float | None,
) -> str | None:
    """Compute home-side ATS result.

    Adjusts the home margin by the spread (negative = home favored).
    Returns 'cover' if adjusted > 0, 'loss' if < 0, 'push' if == 0.
    Returns None if any input is missing.
    """
    if home_score is None or away_score is None or spread_home_close is None:
        return None
    home_margin = home_score - away_score
    adjusted = home_margin + spread_home_close
    if adjusted > 0:
        return "cover"
    if adjusted < 0:
        return "loss"
    return "push"


def derive_total_result(
    home_score: int | None,
    away_score: int | None,
    total_close: float | None,
) -> str | None:
    """Compute over/under/push for the combined score vs the total line."""
    if home_score is None or away_score is None or total_close is None:
        return None
    combined = home_score + away_score
    if combined > total_close:
        return "over"
    if combined < total_close:
        return "under"
    return "push"


_PLAYOFF_WEEK_MAP: dict[str, int] = {
    "Wildcard": 100,
    "Division": 101,
    "Conference": 102,
    "Superbowl": 103,
}


def parse_week(raw: str | int) -> int:
    """Map Kaggle's schedule_week values to integer weeks.

    Regular season "1"–"18" → integer; playoff strings → 100–103.
    """
    if isinstance(raw, int):
        return raw
    if raw in _PLAYOFF_WEEK_MAP:
        return _PLAYOFF_WEEK_MAP[raw]
    try:
        return int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Unknown schedule_week value: {raw!r}") from e
