"""Build the 'This Week' board from current GameOdds + stored opener consensus.

Per upcoming game: current consensus + best price per side (from live GameOdds),
line movement vs our earliest snapshot, and historical bucket context (spread/total
only — ML buckets are derived/biased, so no historical 'rate' is shown for ML).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from engine.ats import bucket_spread
from engine.totals import bucket_total
from ingestion.live_odds import BestLine, GameOdds

_ATS_CSV = Path("data/processed/ats_by_bucket.csv")
_TOT_CSV = Path("data/processed/totals_by_bucket.csv")


@dataclass(frozen=True)
class ThisWeekGame:
    game_key: str
    matchup: str  # "Away at Home"
    commence_time: str
    cons_spread_home: float | None
    cons_total: float | None
    best_spread_home: BestLine | None
    best_spread_away: BestLine | None
    best_total_over: BestLine | None
    best_total_under: BestLine | None
    best_ml_home: BestLine | None
    best_ml_away: BestLine | None
    spread_move: float | None
    total_move: float | None
    spread_ctx: dict | None
    total_ctx: dict | None


def _lookup(csv_path: Path, bucket: str | None) -> dict | None:
    if bucket is None or not csv_path.exists():
        return None
    with csv_path.open(encoding="utf-8") as f:
        rows = [ln for ln in f if not ln.lstrip().startswith("#")]
    for row in csv.DictReader(rows):
        if row.get("bucket") == bucket:
            return {"bucket": bucket, "win_rate": float(row["win_rate"]), "n": int(row["n"])}
    return None


def historical_spread_context(spread_home: float | None) -> dict | None:
    """Historical ATS rate for the bucket a current home spread falls into (uncertified)."""
    if spread_home is None:
        return None
    return _lookup(_ATS_CSV, bucket_spread(spread_home))


def historical_total_context(total: float | None) -> dict | None:
    if total is None:
        return None
    return _lookup(_TOT_CSV, bucket_total(total))


def _move(current: float | None, opener: float | None) -> float | None:
    if current is None or opener is None:
        return None
    return round(current - opener, 2)


def build_board(games: list[GameOdds], openers: dict[str, dict]) -> list[ThisWeekGame]:
    """Assemble the board. `openers` maps game_key -> earliest consensus dict.

    Sorted by absolute spread movement desc (biggest movers first) — descriptive,
    not an edge ranking.
    """
    board: list[ThisWeekGame] = []
    for g in games:
        op = openers.get(g.game_key, {})
        board.append(ThisWeekGame(
            game_key=g.game_key,
            matchup=f"{g.away_team} at {g.home_team}",
            commence_time=g.commence_time,
            cons_spread_home=g.cons_spread_home,
            cons_total=g.cons_total,
            best_spread_home=g.best_spread_home,
            best_spread_away=g.best_spread_away,
            best_total_over=g.best_total_over,
            best_total_under=g.best_total_under,
            best_ml_home=g.best_ml_home,
            best_ml_away=g.best_ml_away,
            spread_move=_move(g.cons_spread_home, op.get("cons_spread_home")),
            total_move=_move(g.cons_total, op.get("cons_total")),
            spread_ctx=historical_spread_context(g.cons_spread_home),
            total_ctx=historical_total_context(g.cons_total),
        ))
    board.sort(
        key=lambda t: abs(t.spread_move) if t.spread_move is not None else -1.0,
        reverse=True,
    )
    return board
