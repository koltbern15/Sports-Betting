from app.tab_leans import _lean_headline, _market_row
from engine.leans import MarketLean


def _ml(state, *, side_label=None, rate=None, n=None, market="spread"):
    return MarketLean(market, state, side_label, rate, n, None, None, None)


def test_headline_lean_mentions_side_and_breakeven():
    h = _lean_headline(_ml("lean", side_label="Rams -6.5 · home favorite", rate=0.531, n=612))
    assert "LEAN" in h and "Rams -6.5 · home favorite" in h
    assert "breakeven" in h and "53.1%" in h
    assert "612" in h


def test_headline_no_lean_is_coin_flip_with_rate():
    h = _lean_headline(_ml("no_lean", rate=0.498, n=540, market="total"))
    assert "No lean" in h and "49.8%" in h and "540" in h


def test_headline_no_data_and_no_line():
    assert "no historical data" in _lean_headline(_ml("no_data")).lower()
    nl = _lean_headline(_ml("no_line")).lower()
    assert "no" in nl and "line" in nl


def test_market_row_no_line_omits_price():
    ml = MarketLean("spread", "no_line", None, None, None, None, None, None)
    assert "best" not in _market_row("Spread", ml).lower()


def test_market_row_no_data_still_shows_best_prices():
    ml = MarketLean("spread", "no_data", None, None, None, None,
                    ("FanDuel", -6.5, -105), ("DK", 6.5, -108))
    row = _market_row("Spread", ml)
    assert "FanDuel" in row and "DK" in row  # shopping value shown even with no history
