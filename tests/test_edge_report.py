"""Tests for engine.edge_report — pure measure-and-annotate report, synthetic CSVs."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from engine.edge_report import EdgeRow, build_edge_report, write_edge_report_csv


def _write_ats_csv(path: Path, rows: list[dict]) -> None:
    header = (
        "bucket,n,wins,losses,pushes,win_rate,push_rate,roi_neg110,roi_neg105,"
        "p_value,ci_low,ci_high,insufficient_sample,by_season,profitable_seasons_pct"
    )
    lines = ["# disclaimer", header]
    for r in rows:
        wins = r.get("wins", 50)
        losses = r.get("losses", 40)
        win_rate = wins / (wins + losses)
        lines.append(
            f"{r['bucket']},{r['n']},{wins},{losses},0,"
            f"{win_rate:.6f},0.000000,"
            f"{r['roi']:.6f},{r['roi']:.6f},"
            f"{r['p']:.6f},{r['ci_low']:.6f},{r['ci_high']:.6f},0,"
            f"2020:0.55;2021:0.50;2022:0.60;2023:0.58,"
            f"{r['prof']:.4f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_totals_csv(path: Path, rows: list[dict]) -> None:
    _write_ats_csv(path, rows)


def _write_ml_csv(path: Path, rows: list[dict]) -> None:
    header = (
        "bucket,n,derived_roi,real_roi,delta_roi,wins,losses,"
        "ci_low,ci_high,p_value,profitable_seasons_pct,by_season"
    )
    lines = ["# Real-line sample: source=fixture, n_games=100", "# disclaimer", header]
    for r in rows:
        lines.append(
            f"{r['bucket']},{r['n']},0.0,{r['roi']:.6f},0.0,"
            f"{r.get('wins', 50)},{r.get('losses', 40)},"
            f"{r['ci_low']:.6f},{r['ci_high']:.6f},{r['p']:.6f},"
            f"{r['prof']:.4f},2020:0.05;2021:0.01;2022:0.08"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _three_csvs(tmp_path):
    ats, totals, ml = tmp_path / "ats.csv", tmp_path / "totals.csv", tmp_path / "ml.csv"
    _write_ats_csv(ats, [
        {"bucket": "ats_lo", "n": 200, "roi": -0.02,
         "ci_low": 0.48, "ci_high": 0.56, "p": 0.40, "prof": 0.4},
        {"bucket": "ats_hi", "n": 300, "roi": 0.06,
         "ci_low": 0.53, "ci_high": 0.61, "p": 0.03, "prof": 0.7},
    ])
    _write_totals_csv(totals, [
        {"bucket": "tot_a", "n": 250, "roi": 0.01,
         "ci_low": 0.50, "ci_high": 0.57, "p": 0.20, "prof": 0.6},
    ])
    _write_ml_csv(ml, [
        {"bucket": "ml_a", "n": 500, "roi": 0.03,
         "ci_low": -0.01, "ci_high": 0.07, "p": 0.10, "prof": 0.6},
    ])
    return ats, totals, ml


def test_no_rows_dropped(tmp_path):
    """Every input bucket appears in the report — nothing is filtered out."""
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    buckets = {r.bucket for r in report}
    assert buckets == {"ats_lo", "ats_hi", "tot_a", "ml_a"}
    assert len(report) == 4


def test_ranked_by_point_roi_desc(tmp_path):
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    rois = [r.point_roi for r in report]
    assert rois == sorted(rois, reverse=True)
    assert report[0].bucket == "ats_hi"   # +0.06, highest
    assert report[-1].bucket == "ats_lo"  # -0.02, lowest


def test_power_columns_populated_and_finite(tmp_path):
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    for r in report:
        assert math.isfinite(r.mde80_roi), f"{r.bucket} mde80_roi not finite"
        assert math.isfinite(r.breakeven_needed_roi), f"{r.bucket} breakeven not finite"
        assert r.mde80_roi > 0
        assert r.breakeven_needed_roi > 0


def test_ml_winrate_blank_ats_populated(tmp_path):
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    by_bucket = {r.bucket: r for r in report}
    assert math.isnan(by_bucket["ml_a"].win_rate)
    assert not math.isnan(by_bucket["ats_hi"].win_rate)


def test_ats_ci_expressed_in_roi(tmp_path):
    """ATS ci_low/ci_high are win-rate Wilson bounds in the source CSV; the report
    must convert them to ROI. ci_low win-rate 0.53 -> roi_from_win_prob(0.53)."""
    from engine.stats_utils import roi_from_win_prob
    ats, totals, ml = _three_csvs(tmp_path)
    report = build_edge_report(ats, totals, ml)
    hi = next(r for r in report if r.bucket == "ats_hi")
    assert hi.ci_low == pytest.approx(roi_from_win_prob(0.53), abs=1e-6)
    assert hi.ci_high == pytest.approx(roi_from_win_prob(0.61), abs=1e-6)


def test_missing_csv_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_edge_report(tmp_path / "no_ats.csv", tmp_path / "no_t.csv", tmp_path / "no_ml.csv")


def test_write_edge_report_csv_has_new_schema(tmp_path):
    rows = [
        EdgeRow(
            market="ats", bucket="ats_hi", n=300, win_rate=0.56, point_roi=0.06,
            ci_low=0.011, ci_high=0.165, p_value=0.03, profitable_seasons_pct=0.7,
            mde80_roi=0.12, breakeven_needed_roi=0.08,
        ),
        EdgeRow(
            market="ml", bucket="ml_a", n=500, win_rate=math.nan, point_roi=0.03,
            ci_low=-0.01, ci_high=0.07, p_value=0.10, profitable_seasons_pct=0.6,
            mde80_roi=0.09, breakeven_needed_roi=0.07,
        ),
    ]
    out = tmp_path / "edge_report.csv"
    write_edge_report_csv(rows, out)
    text = out.read_text(encoding="utf-8")
    assert "# Edge report:" in text
    assert "mde80_roi" in text
    assert "# Past performance" in text
    assert (
        "market,bucket,n,win_rate,point_roi,ci_low,ci_high,"
        "p_value,profitable_seasons_pct,mde80_roi,breakeven_needed_roi" in text
    )
    assert "ats,ats_hi,300" in text
    # ML row has a blank win_rate cell (two consecutive commas after n)
    assert "ml,ml_a,500,," in text
