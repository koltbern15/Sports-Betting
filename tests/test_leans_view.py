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


from streamlit.testing.v1 import AppTest  # noqa: E402


def _smoke_script():
    from app.tab_leans import render
    from engine.this_week import ThisWeekGame

    def g(cons_spread_home=-6.5, cons_total=44.5):
        return ThisWeekGame(
            game_key="k", matchup="Seattle Seahawks at Los Angeles Rams",
            commence_time="2026-09-13T20:25:00Z",
            cons_spread_home=cons_spread_home, cons_total=cons_total,
            best_spread_home=("FanDuel", -6.5, -105), best_spread_away=("DK", 6.5, -108),
            best_total_over=("DK", 44.5, -108), best_total_under=("BetMGM", 44.5, -105),
            best_ml_home=("DK", None, -280), best_ml_away=("DK", None, 230),
            spread_move=0.0, total_move=0.0, spread_ctx=None, total_ctx=None,
        )

    spread_rates = {
        "home_fav_3.5_7": {"win_rate": 0.531, "n": 612},  # lean
        "home_dog_1_3": {"win_rate": 0.50, "n": 600},     # no_lean
    }
    total_rates = {"total_43_45_5": {"win_rate": 0.50, "n": 600}}  # no_lean
    board = [g(-6.5, 44.5), g(2.0, 44.5), g(None, None)]  # lean / no_lean / no_line
    render(board, spread_rates, total_rates)


def test_render_smoke_does_not_crash():
    at = AppTest.from_function(_smoke_script).run()
    assert not at.exception
    assert at.markdown
