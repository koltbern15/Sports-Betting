"""Opening-line data quality audit.

Reads opening_lines + betting_lines + games from the SQLite DB and produces:
  - stdout: coverage table, overlap agreement rates, movement stats, ML status
  - docs/superpowers/notes/2026-05-29-opening-line-audit.md: full markdown report

Run: uv run python scripts/cross_check_openers.py
(DB must be populated; run after Task 8 ingestion is complete.)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import connect, fetch_df  # noqa: E402
from engine.opener_audit import agreement_rate, movement_stats, outliers  # noqa: E402
from ingestion.opening_line_loader import canonical_opener_source  # noqa: E402

DB_PATH = "data/db/nfl_betting.sqlite"
OUT_MD = Path("docs/superpowers/notes/2026-05-29-opening-line-audit.md")
OVERLAP_SEASONS = list(range(2013, 2022))  # 2013–2021 both sbr + aus present


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _section_coverage(conn) -> str:
    """Per-source, per-season row counts joined to games."""
    df = fetch_df(
        conn,
        "SELECT ol.source, g.season, COUNT(*) AS rows"
        " FROM opening_lines ol"
        " JOIN games g ON g.game_id = ol.game_id"
        " GROUP BY ol.source, g.season"
        " ORDER BY ol.source, g.season",
    )
    if df.empty:
        return "## Coverage\n\n_No data._\n"
    lines = ["## Coverage", "", df.to_string(index=False), ""]
    return "\n".join(lines)


def _section_overlap_agreement(conn) -> str:
    """Agreement rates for sbr vs aus on spread and total in 2013-2021."""
    seasons_ph = ",".join("?" * len(OVERLAP_SEASONS))
    sql = (
        f"SELECT g.game_id, g.season, g.home_team, g.away_team,"
        f"  sbr.open_spread_home AS sbr_spread, aus.open_spread_home AS aus_spread,"
        f"  sbr.open_total      AS sbr_total,  aus.open_total       AS aus_total"
        f" FROM games g"
        f" JOIN opening_lines sbr ON sbr.game_id = g.game_id AND sbr.source = 'sbr'"
        f" JOIN opening_lines aus ON aus.game_id = g.game_id AND aus.source = 'aus'"
        f" WHERE g.season IN ({seasons_ph})"
    )
    df = fetch_df(conn, sql, params=OVERLAP_SEASONS)

    if df.empty:
        return "## Overlap Agreement (2013–2021)\n\n_No overlap data._\n"

    sbr_spread = df["sbr_spread"].tolist()
    aus_spread = df["aus_spread"].tolist()
    sbr_total = df["sbr_total"].tolist()
    aus_total = df["aus_total"].tolist()

    sp_05 = agreement_rate(sbr_spread, aus_spread, tol=0.5)
    sp_10 = agreement_rate(sbr_spread, aus_spread, tol=1.0)
    to_05 = agreement_rate(sbr_total, aus_total, tol=0.5)
    to_10 = agreement_rate(sbr_total, aus_total, tol=1.0)

    lines = [
        "## Overlap Agreement (2013–2021)",
        "",
        f"Games with both sbr + aus rows: {len(df)}",
        "",
        "| Market  | tol=0.5 | tol=1.0 |",
        "| ------- | ------- | ------- |",
        f"| Spread  | {sp_05:.4f}  | {sp_10:.4f}  |",
        f"| Total   | {to_05:.4f}  | {to_10:.4f}  |",
        "",
    ]

    # Worst 10 spread disagreements
    df_sp = df.dropna(subset=["sbr_spread", "aus_spread"]).copy()
    if not df_sp.empty:
        df_sp["spread_diff"] = (df_sp["sbr_spread"] - df_sp["aus_spread"]).abs()
        worst_sp = df_sp.nlargest(10, "spread_diff")[
            ["season", "home_team", "away_team", "sbr_spread", "aus_spread", "spread_diff"]
        ]
        lines += ["### Worst 10 spread disagreements", "", worst_sp.to_string(index=False), ""]

    # Worst 10 total disagreements
    df_to = df.dropna(subset=["sbr_total", "aus_total"]).copy()
    if not df_to.empty:
        df_to["total_diff"] = (df_to["sbr_total"] - df_to["aus_total"]).abs()
        worst_to = df_to.nlargest(10, "total_diff")[
            ["season", "home_team", "away_team", "sbr_total", "aus_total", "total_diff"]
        ]
        lines += ["### Worst 10 total disagreements", "", worst_to.to_string(index=False), ""]

    return "\n".join(lines)


def _section_closer_sanity(conn) -> str:
    """Movement stats: canonical open vs closing line."""
    # Pull all opening_lines rows and pick the canonical source per game's season.
    sql = (
        "SELECT g.game_id, g.season, g.home_team, g.away_team,"
        "  ol.source, ol.open_spread_home, ol.open_total,"
        "  bl.spread_home_close, bl.total_close"
        " FROM games g"
        " JOIN opening_lines ol ON ol.game_id = g.game_id"
        " JOIN betting_lines  bl ON bl.game_id = g.game_id"
    )
    df = fetch_df(conn, sql)

    if df.empty:
        return "## Closer Sanity\n\n_No data._\n"

    # Keep only canonical source per (game_id, season)
    df["canonical_src"] = df["season"].apply(canonical_opener_source)
    df = df[df["source"] == df["canonical_src"]].copy()

    opens_spread = df["open_spread_home"].tolist()
    closes_spread = df["spread_home_close"].tolist()
    opens_total = df["open_total"].tolist()
    closes_total = df["total_close"].tolist()

    sp_stats = movement_stats(opens_spread, closes_spread)
    to_stats = movement_stats(opens_total, closes_total)

    sp_outlier_idx = outliers(opens_spread, closes_spread, threshold=7.0)
    flagged = df.iloc[sp_outlier_idx][
        ["season", "home_team", "away_team", "open_spread_home", "spread_home_close"]
    ]

    lines = [
        "## Closer Sanity",
        "",
        "### Movement stats (close − open)",
        "",
        "| Market | n   | mean  | stdev |",
        "| ------ | --- | ----- | ----- |",
        f"| Spread | {sp_stats['n']} | {sp_stats['mean']:.3f} | {sp_stats['stdev']:.3f} |",
        f"| Total  | {to_stats['n']} | {to_stats['mean']:.3f} | {to_stats['stdev']:.3f} |",
        "",
        f"### Spread outliers (|close − open| > 7.0): {len(sp_outlier_idx)} games",
        "",
    ]
    if not flagged.empty:
        lines += [flagged.to_string(index=False), ""]

    return "\n".join(lines)


def _section_ml_status(conn) -> str:
    """Count rows with non-null open_ml_home."""
    df = fetch_df(
        conn,
        "SELECT source, COUNT(*) AS total_rows,"
        "  SUM(CASE WHEN open_ml_home IS NOT NULL THEN 1 ELSE 0 END) AS ml_rows"
        " FROM opening_lines"
        " GROUP BY source",
    )
    if df.empty:
        return "## ML Status\n\n_No data._\n"
    lines = ["## ML Status", "", df.to_string(index=False), ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    conn = connect(DB_PATH)

    cov = _section_coverage(conn)
    overlap = _section_overlap_agreement(conn)
    closer = _section_closer_sanity(conn)
    ml_status = _section_ml_status(conn)

    conn.close()

    md = "\n".join([
        "# Opening-Line Audit — 2026-05-29",
        "",
        cov,
        overlap,
        closer,
        ml_status,
    ])

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")

    print(cov)
    print(overlap)
    print(closer)
    print(ml_status)
    print(f"Report written to {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
