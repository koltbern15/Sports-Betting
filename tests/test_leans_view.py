from app.tab_leans import _lean_headline
from engine.leans import MarketLean


def _ml(state, *, side_label=None, rate=None, n=None, market="spread"):
    return MarketLean(market, state, side_label, rate, n, None, None, None)


def test_headline_lean_mentions_side_and_breakeven():
    h = _lean_headline(_ml("lean", side_label="Rams -6.5 · home favorite", rate=0.531, n=612))
    assert "LEAN" in h and "Rams -6.5 · home favorite" in h
    assert "breakeven" in h and "53.1%" in h


def test_headline_no_lean_is_coin_flip_with_rate():
    h = _lean_headline(_ml("no_lean", rate=0.498, n=540, market="total"))
    assert "No lean" in h and "49.8%" in h and "540" in h


def test_headline_no_data_and_no_line():
    assert "no historical data" in _lean_headline(_ml("no_data")).lower()
    nl = _lean_headline(_ml("no_line")).lower()
    assert "no" in nl and "line" in nl
