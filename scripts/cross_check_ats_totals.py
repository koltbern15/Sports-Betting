"""One-time Kaggle-vs-nflverse cross-check for closing spread + total lines.

Compares Kaggle's `betting_lines.spread_home_close` and `total_close` to
nflverse's `spread_line` and `total_line` on the 2020-2024 overlap.

Outputs:
  - stdout: agreement %, sample sizes, top 10 worst disagreements per market
  - data/processed/kaggle_vs_nflverse_lines.csv: full per-game comparison

Decision rule for downstream (engine.credible_edges):
  - If spread agreement >= 95% AND total agreement >= 95% -> keep Kaggle 2004-2024
  - Else -> narrow to 2020-2024 nflverse-confirmed

Run: uv run python scripts/cross_check_ats_totals.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nfl_data_py as nfl  # noqa: E402

from engine.db import connect, fetch_df  # noqa: E402
from ingestion.team_codes import code_to_canonical  # noqa: E402

AGREEMENT_TOLERANCE = 0.5  # half-point — anything within this counts as a match
SEASONS = [2020, 2021, 2022, 2023, 2024]
KAGGLE_DB = "data/db/nfl_betting.sqlite"
OUT_CSV = Path("data/processed/kaggle_vs_nflverse_lines.csv")


def main() -> int:
    conn = connect(KAGGLE_DB)
    kaggle = fetch_df(
        conn,
        "SELECT g.season, g.week, g.home_team, g.away_team, "
        "       bl.spread_home_close, bl.total_close "
        "FROM games g JOIN betting_lines bl ON bl.game_id = g.game_id "
        "WHERE g.season BETWEEN 2020 AND 2024",
    )
    conn.close()

    raw = nfl.import_schedules(SEASONS)
    nflv = raw[
        ["season", "week", "home_team", "away_team", "spread_line", "total_line"]
    ].copy()
    nflv["home_team"] = nflv["home_team"].map(code_to_canonical)
    nflv["away_team"] = nflv["away_team"].map(code_to_canonical)
    # nflverse spread_line: POSITIVE = home favored (per nflverse docs).
    # Kaggle spread_home_close: NEGATIVE = home favored (home-perspective signed).
    # Flip nflverse to match Kaggle's home-perspective convention.
    nflv["spread_line"] = -nflv["spread_line"]

    merged = kaggle.merge(
        nflv,
        on=["season", "week", "home_team", "away_team"],
        how="inner",
        suffixes=("_kag", "_nfl"),
    )

    n = len(merged)
    if n == 0:
        print("ERROR: zero rows joined — check team-name canonicalization.")
        return 1

    spread_match = (
        (merged["spread_home_close"] - merged["spread_line"]).abs() <= AGREEMENT_TOLERANCE
    )
    total_match = (
        (merged["total_close"] - merged["total_line"]).abs() <= AGREEMENT_TOLERANCE
    )

    spread_pct = spread_match.sum() / n
    total_pct = total_match.sum() / n

    print(f"Matched games: {n}")
    print(f"Spread agreement (+/-{AGREEMENT_TOLERANCE}): {spread_pct:.4f}")
    print(f"Total  agreement (+/-{AGREEMENT_TOLERANCE}): {total_pct:.4f}")
    print()

    print("Top 10 worst spread disagreements:")
    spread_cols = [
        "season", "week", "home_team", "away_team",
        "spread_home_close", "spread_line", "spread_diff",
    ]
    worst_spread = (
        merged.assign(spread_diff=lambda d: (d.spread_home_close - d.spread_line).abs())
        .nlargest(10, "spread_diff")[spread_cols]
    )
    print(worst_spread.to_string(index=False))
    print()

    print("Top 10 worst total disagreements:")
    total_cols = [
        "season", "week", "home_team", "away_team",
        "total_close", "total_line", "total_diff",
    ]
    worst_total = (
        merged.assign(total_diff=lambda d: (d.total_close - d.total_line).abs())
        .nlargest(10, "total_diff")[total_cols]
    )
    print(worst_total.to_string(index=False))
    print()

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT_CSV, index=False)
    print(f"Full per-game comparison written to {OUT_CSV}")

    # Report agreement at multiple tolerances. Bucket boundaries in
    # engine/ats.py and engine/totals.py are 3+ points wide, so the
    # ±1.0 row is the meaningful test, not ±0.5.
    print("\nAgreement by tolerance:")
    for tol in (0.5, 1.0, 1.5):
        sp_t = ((merged["spread_home_close"] - merged["spread_line"]).abs() <= tol).mean()
        to_t = ((merged["total_close"] - merged["total_line"]).abs() <= tol).mean()
        print(f"  +/-{tol}: spread {sp_t:.4f}, total {to_t:.4f}")

    suggestion = (
        "KEEP Kaggle 2004-2024 (>=95% agreement at +/-0.5)"
        if spread_pct >= 0.95 and total_pct >= 0.95
        else "REVIEW manually — check ±1.0 row above; see docs/superpowers/notes/"
        "2026-05-28-kaggle-nflverse-crosscheck.md for the project's standing decision"
    )
    print(f"\nSuggestion: {suggestion}")
    print("(Project decision is canonical in the notes doc, not this script's output.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
