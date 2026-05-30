"""Tests for ingestion.opening_line_sbr — parse the SBR HTML fixture (offline)."""

from __future__ import annotations

from pathlib import Path

from ingestion.opening_line_sbr import parse_sbr_html

_FIX = Path(__file__).parent / "fixtures" / "sbr_sample.html"


def _load() -> str:
    return _FIX.read_text(encoding="utf-8")


def test_parses_all_four_games():
    recs = parse_sbr_html(_load(), season=2021)
    assert len(recs) == 4


def test_no_opening_ml_emitted():
    recs = parse_sbr_html(_load(), season=2021)
    assert all(r.open_ml_home is None and r.open_ml_away is None for r in recs)
    assert all(r.source == "sbr" for r in recs)
    assert all(r.season == 2021 for r in recs)


def test_normal_layout_home_favorite():
    # Dallas @ TampaBay: V row holds total (52.5), H row holds spread (7).
    # TampaBay ML -450 -> home favorite -> spread negative.
    recs = parse_sbr_html(_load(), season=2021)
    g = next(r for r in recs if r.home_team == "Tampa Bay Buccaneers")
    assert g.away_team == "Dallas Cowboys"
    assert g.game_date == "2021-09-09"
    assert g.open_spread_home == -7.0
    assert g.open_total == 52.5
    assert g.open_ml_home is None
    assert g.open_ml_away is None


def test_flipped_pickem_home_dog():
    # Jacksonville @ Houston: FLIPPED — V row = 'pk' spread, H row = total (46).
    # Houston ML +150 -> home NOT favorite -> pickem spread = +0.0.
    recs = parse_sbr_html(_load(), season=2021)
    g = next(r for r in recs if r.home_team == "Houston Texans")
    assert g.away_team == "Jacksonville Jaguars"
    assert g.game_date == "2021-09-12"
    assert g.open_spread_home == 0.0
    assert g.open_total == 46.0


def test_flipped_home_dog_spread():
    # Minnesota @ Cincinnati: FLIPPED — V row = spread (3), H row = total (48.5).
    # Cincinnati ML +135 -> home NOT favorite -> spread = +3.0.
    recs = parse_sbr_html(_load(), season=2021)
    g = next(r for r in recs if r.home_team == "Cincinnati Bengals")
    assert g.away_team == "Minnesota Vikings"
    assert g.open_spread_home == 3.0
    assert g.open_total == 48.5


def test_flipped_san_francisco_detroit():
    # SanFrancisco @ Detroit: FLIPPED — V row = spread (9), H row = total (46).
    # Detroit ML +360 -> home NOT favorite -> spread = +9.0.
    recs = parse_sbr_html(_load(), season=2021)
    g = next(r for r in recs if r.home_team == "Detroit Lions")
    assert g.away_team == "San Francisco 49ers"
    assert g.open_spread_home == 9.0
    assert g.open_total == 46.0
