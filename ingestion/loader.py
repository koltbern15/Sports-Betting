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
