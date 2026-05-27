"""Real-line moneyline validation — comparator + reporting.

Compares derived ML prices (from `engine.moneyline.derive_ml_from_spread`)
to real historical ML prices stored in `real_ml_lines`. Outputs per-side
implied-probability errors plus per-bucket ROI under both price sets.
"""

from __future__ import annotations

from statistics import mean, median


def american_to_implied_prob(ml: int) -> float:
    """Convert integer American odds to raw implied probability (vig included)."""
    if ml < 0:
        return (-ml) / ((-ml) + 100)
    return 100 / (ml + 100)


def side_error(real_ml: int, derived_ml: int) -> dict:
    """Per-side comparison: error in implied-probability points and raw American delta.

    Returns {"error_prob": float, "error_ml": int}
      error_prob = real_implied_p - derived_implied_p
        (positive => real market priced this side as more likely than derived)
      error_ml   = real_ml - derived_ml (raw American-odds delta, for readability)
    """
    return {
        "error_prob": american_to_implied_prob(real_ml) - american_to_implied_prob(derived_ml),
        "error_ml": real_ml - derived_ml,
    }


def compute_price_stats(sides: list[dict]) -> dict:
    """Aggregate per-side comparisons into summary stats.

    Each side dict must contain: real_ml, derived_ml, is_favorite (bool).
    """
    if not sides:
        raise ValueError("compute_price_stats called with empty sides list")

    errors = [side_error(s["real_ml"], s["derived_ml"]) for s in sides]
    errs_prob = [e["error_prob"] for e in errors]
    errs_ml = [e["error_ml"] for e in errors]

    n_sides = len(sides)
    n_within = sum(1 for e in errs_prob if abs(e) <= 0.02)

    sign_flips = 0
    for side, _err in zip(sides, errs_prob, strict=True):
        real_p = american_to_implied_prob(side["real_ml"])
        derived_p = american_to_implied_prob(side["derived_ml"])
        if (real_p > 0.5) != (derived_p > 0.5):
            sign_flips += 1

    fav_errors = [
        e["error_prob"] for e, s in zip(errors, sides, strict=True) if s["is_favorite"]
    ]
    if fav_errors:
        mean_fav_err = mean(fav_errors)
        pct_share_sign = sum(1 for e in fav_errors if e < 0) / len(fav_errors)
        overshades = mean_fav_err < 0 and pct_share_sign > 0.6
    else:
        overshades = False

    return {
        "n_sides": n_sides,
        "mean_error_prob": mean(errs_prob),
        "median_abs_error_prob": median(abs(e) for e in errs_prob),
        "pct_within_2_pct_points": n_within / n_sides,
        "pct_sign_flip": sign_flips / n_sides,
        "derived_overshades_favorites": overshades,
        "mean_error_ml": mean(errs_ml),
    }
