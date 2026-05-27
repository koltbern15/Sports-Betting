"""ATS-by-spread-bucket analysis.

Buckets the home-perspective signed spread into the 11 categories defined in
the Slice 1 spec, then aggregates wins / losses / pushes / metrics per bucket.
"""

from __future__ import annotations

# Bucket order is the order they will appear in the final report (favorites → dogs).
BUCKET_ORDER: list[str] = [
    "home_fav_14.5+",
    "home_fav_10.5_14",
    "home_fav_7.5_10",
    "home_fav_3.5_7",
    "home_fav_1_3",
    "pickem",
    "home_dog_1_3",
    "home_dog_3.5_7",
    "home_dog_7.5_10",
    "home_dog_10.5_14",
    "home_dog_14.5+",
]


def bucket_spread(spread_home_close: float | None) -> str | None:
    """Bucket the home-perspective spread.

    Pick'em covers (-0.5, 0, 0.5). Favorites and underdogs partition the rest.
    """
    if spread_home_close is None:
        return None
    s = spread_home_close
    if -0.5 <= s <= 0.5:
        return "pickem"
    if s < 0:
        m = -s  # magnitude when home is favored
        if m >= 14.5:
            return "home_fav_14.5+"
        if m >= 10.5:
            return "home_fav_10.5_14"
        if m >= 7.5:
            return "home_fav_7.5_10"
        if m >= 3.5:
            return "home_fav_3.5_7"
        return "home_fav_1_3"
    # s > 0.5 → home is the dog
    if s >= 14.5:
        return "home_dog_14.5+"
    if s >= 10.5:
        return "home_dog_10.5_14"
    if s >= 7.5:
        return "home_dog_7.5_10"
    if s >= 3.5:
        return "home_dog_3.5_7"
    return "home_dog_1_3"
