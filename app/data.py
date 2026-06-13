"""Cached data-access layer for the dashboard. Thin wrappers over engine functions
+ produced CSVs. Loaders use st.cache_data (which exposes .__wrapped__ for tests).
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from engine.clv import CLV_BUCKET_ORDER, aggregate_clv, build_bets_from_db
from engine.db import connect

_DB = "data/db/nfl_betting.sqlite"
_EDGE_CSV = Path("data/processed/edge_report.csv")


def _open_db() -> sqlite3.Connection:
    return connect(_DB)


@st.cache_data(show_spinner=False)
def load_edge_report() -> pd.DataFrame:
    """The honest edge report (Slice 5). Empty DataFrame if not generated yet."""
    if not _EDGE_CSV.exists():
        return pd.DataFrame()
    with _EDGE_CSV.open(encoding="utf-8") as f:
        rows = [ln for ln in f if not ln.lstrip().startswith("#")]
    return pd.DataFrame(list(csv.DictReader(rows)))


@st.cache_data(show_spinner=False)
def clv_ladder(
    *, market: str, season_range: tuple[int, int], grade_at: str = "open"
) -> pd.DataFrame:
    """Per-CLV-bucket rows for one market, filtered to a season range. Empty if no data."""
    try:
        conn = _open_db()
    except Exception:
        return pd.DataFrame()
    bets = build_bets_from_db(conn, grade_at=grade_at)
    lo, hi = season_range
    bets = [b for b in bets if lo <= b["season"] <= hi]
    rows = [r for r in aggregate_clv(bets) if r.market == market]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "clv_bucket": r.clv_bucket, "n": r.n, "mean_clv": r.mean_clv,
        "win_rate": r.win_rate, "roi": r.roi, "p_value": r.p_value,
        "mde80": r.mde80, "ci_low": r.ci_low, "ci_high": r.ci_high,
        "low_n": r.insufficient_sample,
    } for r in rows])
    df["_order"] = df["clv_bucket"].map(CLV_BUCKET_ORDER.index)
    return df.sort_values("_order").drop(columns="_order").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def opening_line_coverage() -> pd.DataFrame:
    """Opening-line rows per source per season. Empty if DB/table absent."""
    try:
        conn = _open_db()
        return pd.read_sql_query(
            "SELECT ol.source, g.season, COUNT(*) AS games"
            " FROM opening_lines ol JOIN games g ON g.game_id = ol.game_id"
            " GROUP BY ol.source, g.season ORDER BY g.season, ol.source",
            conn,
        )
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def clv_result_correlation(
    *, market: str, season_range: tuple[int, int]
) -> tuple[float, float, int]:
    """Live point-biserial correlation between per-bet CLV and the win/loss outcome.

    Drops pushes, maps win->1 / loss->0, and runs scipy.stats.pearsonr over the
    opener-graded reference bets for `market` in the season range. Returns
    (r, p_value, n_decided). Returns (nan, nan, 0) when data is absent or n < 3.
    This replaces a previously hardcoded stat card so the figure tracks the data.
    """
    try:
        conn = _open_db()
    except Exception:
        return float("nan"), float("nan"), 0
    bets = build_bets_from_db(conn, grade_at="open")
    lo, hi = season_range
    pairs = [
        (b["clv"], 1.0 if b["result"] == "win" else 0.0)
        for b in bets
        if b["market"] == market
        and lo <= b["season"] <= hi
        and b["result"] in ("win", "loss")
    ]
    if len(pairs) < 3:
        return float("nan"), float("nan"), len(pairs)
    clvs = [c for c, _ in pairs]
    outcomes = [o for _, o in pairs]
    # Degenerate guard: pearsonr needs variance on both axes.
    if len(set(clvs)) < 2 or len(set(outcomes)) < 2:
        return float("nan"), float("nan"), len(pairs)
    from scipy.stats import pearsonr

    r, p = pearsonr(clvs, outcomes)
    return float(r), float(p), len(pairs)


def season_bounds() -> tuple[int, int]:
    """Min/max season available, for the slider. Falls back to 2007-2024."""
    try:
        conn = _open_db()
        df = pd.read_sql_query("SELECT MIN(season) lo, MAX(season) hi FROM games", conn)
        return int(df["lo"].iloc[0]), int(df["hi"].iloc[0])
    except Exception:
        return 2007, 2024


def audit_summary() -> dict:
    """Static data-quality facts.

    Source of truth: docs/superpowers/notes/2026-05-29-opening-line-audit.md
    """
    return {
        "opening_rows_total": 8620,
        "overlap_games": 2183,
        "overlap_spread_within_1pt": 0.75,
        "overlap_total_within_1pt": 0.82,
        "sources": [
            {
                "name": "Kaggle (spreadspoke)",
                "provides": "closing spread + total",
                "window": "2004-2024",
            },
            {
                "name": "nflverse (nfl_data_py)",
                "provides": "real closing moneyline",
                "window": "2020-2024",
            },
            {
                "name": "SportsbookReviewsOnline",
                "provides": "opening spread + total",
                "window": "2007-2021",
            },
            {
                "name": "Australia Sports Betting",
                "provides": "opening spread/total/ML",
                "window": "2006-2024",
            },
        ],
    }
