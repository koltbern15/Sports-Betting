"""Tests for engine.credible_edges — pure ranker tested with synthetic CSVs."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.credible_edges import CredibleEdge, rank_credible_edges


def _write_ats_csv(path: Path, rows: list[dict]) -> None:
    header = (
        "bucket,n,wins,losses,pushes,win_rate,push_rate,roi_neg110,roi_neg105,"
        "p_value,ci_low,ci_high,insufficient_sample,by_season,profitable_seasons_pct"
    )
    lines = ["# disclaimer", header]
    for r in rows:
        lines.append(
            f"{r['bucket']},{r['n']},{r.get('wins', 50)},{r.get('losses', 40)},0,"
            f"{r.get('wins', 50) / (r.get('wins', 50) + r.get('losses', 40)):.6f},0.000000,"
            f"{r['roi']:.6f},{r['roi']:.6f},"
            f"{r['p']:.6f},{r['ci_low']:.6f},{r['ci_high']:.6f},0,"
            f"2020:0.55;2021:0.50;2022:0.60;2023:0.58,"
            f"{r['prof']:.4f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_totals_csv(path: Path, rows: list[dict]) -> None:
    # Same shape as ATS
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


def test_rank_happy_path(tmp_path):
    ats_path = tmp_path / "ats.csv"
    totals_path = tmp_path / "totals.csv"
    ml_path = tmp_path / "ml.csv"
    _write_ats_csv(
        ats_path,
        [{"bucket": "ats_a", "n": 200, "roi": 0.05,
          "ci_low": 0.01, "ci_high": 0.09, "p": 0.04, "prof": 0.7}],
    )
    _write_totals_csv(
        totals_path,
        [{"bucket": "tot_a", "n": 300, "roi": 0.03,
          "ci_low": 0.005, "ci_high": 0.06, "p": 0.08, "prof": 0.65}],
    )
    _write_ml_csv(
        ml_path,
        [{"bucket": "ml_a", "n": 500, "roi": 0.02,
          "ci_low": 0.015, "ci_high": 0.04, "p": 0.02, "prof": 0.8}],
    )
    edges = rank_credible_edges(ats_path, totals_path, ml_path)
    assert len(edges) == 3
    # Ranked by ci_low desc
    assert edges[0].bucket == "ml_a"   # ci_low 0.015
    assert edges[1].bucket == "ats_a"  # ci_low 0.01
    assert edges[2].bucket == "tot_a"  # ci_low 0.005
    assert all(isinstance(e, CredibleEdge) for e in edges)


def test_rank_rejects_low_n(tmp_path):
    ats = tmp_path / "ats.csv"
    totals = tmp_path / "totals.csv"
    ml = tmp_path / "ml.csv"
    _write_ats_csv(
        ats,
        [{"bucket": "small", "n": 50, "roi": 0.05,
          "ci_low": 0.02, "ci_high": 0.08, "p": 0.03, "prof": 0.7}],
    )
    _write_totals_csv(totals, [])
    _write_ml_csv(ml, [])
    assert rank_credible_edges(ats, totals, ml) == []


def test_rank_rejects_non_positive_ci_low(tmp_path):
    ats = tmp_path / "ats.csv"
    totals = tmp_path / "totals.csv"
    ml = tmp_path / "ml.csv"
    _write_ats_csv(
        ats,
        [{"bucket": "flat", "n": 200, "roi": 0.0,
          "ci_low": -0.01, "ci_high": 0.01, "p": 0.5, "prof": 0.5}],
    )
    _write_totals_csv(totals, [])
    _write_ml_csv(ml, [])
    assert rank_credible_edges(ats, totals, ml) == []


def test_rank_rejects_high_p_value(tmp_path):
    ats = tmp_path / "ats.csv"
    totals = tmp_path / "totals.csv"
    ml = tmp_path / "ml.csv"
    _write_ats_csv(
        ats,
        [{"bucket": "noisy", "n": 200, "roi": 0.05,
          "ci_low": 0.001, "ci_high": 0.10, "p": 0.30, "prof": 0.7}],
    )
    _write_totals_csv(totals, [])
    _write_ml_csv(ml, [])
    assert rank_credible_edges(ats, totals, ml) == []


def test_rank_rejects_low_profitable_seasons(tmp_path):
    ats = tmp_path / "ats.csv"
    totals = tmp_path / "totals.csv"
    ml = tmp_path / "ml.csv"
    _write_ats_csv(
        ats,
        [{"bucket": "spiky", "n": 200, "roi": 0.05,
          "ci_low": 0.02, "ci_high": 0.08, "p": 0.03, "prof": 0.4}],
    )
    _write_totals_csv(totals, [])
    _write_ml_csv(ml, [])
    assert rank_credible_edges(ats, totals, ml) == []


def test_rank_missing_csv_raises(tmp_path):
    ats = tmp_path / "missing_ats.csv"
    totals = tmp_path / "missing_totals.csv"
    ml = tmp_path / "missing_ml.csv"
    with pytest.raises(FileNotFoundError):
        rank_credible_edges(ats, totals, ml)
