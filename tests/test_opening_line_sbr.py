"""Tests for ingestion.opening_line_sbr — parse the SBR HTML fixture (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.opening_line_sbr import _classify_pair, parse_sbr_html

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


# --- _classify_pair direct unit tests (ambiguity resolution via Close) -------


def test_classify_unambiguous_v_total():
    # Away Open is the total (>25), home Open is the spread.
    assert _classify_pair(52.5, 7.0) == pytest.approx((7.0, 52.5))


def test_classify_unambiguous_h_total():
    # Home Open is the total (>25), away Open is the spread.
    assert _classify_pair(3.0, 48.5) == pytest.approx((3.0, 48.5))


def test_classify_unambiguous_ignores_close():
    # When Open is already unambiguous, Close is not consulted.
    assert _classify_pair(46.0, 9.0, v_close=9.0, h_close=46.0) == pytest.approx(
        (9.0, 46.0)
    )


def test_classify_both_low_garbage_open_total_skips():
    # Both Opens <= 25 (ambiguous): a real pickem (0.0) paired with a freak low
    # value (3.0). Close picks the home row as the total (46.0), but that row's
    # OPEN total slot is 3.0 (<= 25) -> the opening total was never recorded
    # (garbage) -> unrecoverable -> None (skip rather than fabricate total=3.0).
    # This mirrors all 4 real ambiguous game-pairs in the 2007-2021 archive.
    assert _classify_pair(0.0, 3.0, v_close=2.5, h_close=46.0) is None


def test_classify_both_low_garbage_open_total_away_skips():
    # Same shape, away row is the total per Close (46.0) but away Open (3.0) is
    # not a plausible total -> skip.
    assert _classify_pair(3.0, 1.0, v_close=46.0, h_close=2.5) is None


def test_classify_real_2017_ind_buf_skips():
    # 2017 IND@BUF, Dec 10 (verbatim from data/raw/sbr_2017.html):
    #   V IND  Open='pk'(0.0)  Close=36.5     H BUF  Open=13.5  Close=3.5
    # Close says away is the total, but away Open is 0.0 (the opening total was
    # never recorded) -> unrecoverable -> skip, not a fabricated total.
    assert _classify_pair(0.0, 13.5, v_close=36.5, h_close=3.5) is None


def test_classify_both_high_resolved_by_close():
    # Both Opens > 25 (ambiguous, e.g. a freak high spread cell). A valid Close
    # disambiguates: home Close is the total (47.0 > 25), away Close is the
    # spread magnitude (10.0 <= 25), AND the home Open (47.0) is itself a
    # plausible total -> resolved: home Open is the total, away Open the spread.
    result = _classify_pair(40.0, 47.0, v_close=10.0, h_close=47.0)
    # Close: home is total, home Open plausible -> (v_open spread, h_open total).
    assert result == pytest.approx((40.0, 47.0))


def test_classify_ambiguous_no_close_skips():
    # Both Opens <= 25 and no Close supplied -> cannot resolve -> None (skip).
    assert _classify_pair(0.0, 3.0) is None


def test_classify_ambiguous_close_also_ambiguous_skips():
    # Both Opens <= 25 and Close is ALSO ambiguous (both close values <= 25)
    # -> cannot resolve -> None (skip rather than fabricate).
    assert _classify_pair(0.0, 3.0, v_close=3.0, h_close=2.5) is None


def test_classify_ambiguous_close_both_high_skips():
    # Both Opens > 25 and both Close values > 25 -> Close cannot disambiguate
    # (neither row stays a spread) -> None (skip rather than fabricate).
    assert _classify_pair(40.0, 47.0, v_close=40.0, h_close=47.0) is None


def test_classify_ambiguous_missing_one_close_skips():
    # Only one Close value present -> cannot resolve -> None (skip).
    assert _classify_pair(0.0, 3.0, v_close=46.0, h_close=None) is None
