from engine.leans import spread_lean
from engine.this_week import ThisWeekGame


def _game(*, cons_spread_home=-6.5, cons_total=44.5,
          matchup="Seattle Seahawks at Los Angeles Rams"):
    return ThisWeekGame(
        game_key="k", matchup=matchup, commence_time="2026-09-13T20:25:00Z",
        cons_spread_home=cons_spread_home, cons_total=cons_total,
        best_spread_home=("FanDuel", -6.5, -105), best_spread_away=("DK", 6.5, -108),
        best_total_over=("DK", 44.5, -108), best_total_under=("BetMGM", 44.5, -105),
        best_ml_home=("DK", None, -280), best_ml_away=("DK", None, 230),
        spread_move=0.0, total_move=0.0, spread_ctx=None, total_ctx=None,
    )


def test_spread_home_favorite_lean():
    rates = {"home_fav_3.5_7": {"win_rate": 0.531, "n": 612}}
    ml = spread_lean(_game(cons_spread_home=-6.5), rates)
    assert ml.state == "lean"
    assert "Los Angeles Rams" in ml.side_label and "-6.5" in ml.side_label
    assert "home favorite" in ml.side_label
    assert ml.best_for_lean == ("FanDuel", -6.5, -105)
    assert ml.n == 612


def test_spread_away_lean_when_home_dog_overperforms():
    rates = {"home_dog_3.5_7": {"win_rate": 0.46, "n": 500}}
    ml = spread_lean(_game(cons_spread_home=6.5), rates)
    assert ml.state == "lean"
    assert "Seattle Seahawks" in ml.side_label and "-6.5" in ml.side_label
    assert "away favorite" in ml.side_label
    assert ml.best_for_lean == ("DK", 6.5, -108)


def test_spread_below_breakeven_is_no_lean():
    rates = {"home_fav_3.5_7": {"win_rate": 0.515, "n": 900}}
    ml = spread_lean(_game(cons_spread_home=-6.5), rates)
    assert ml.state == "no_lean"
    assert ml.side_label is None
    assert ml.rate == 0.515


def test_spread_sample_gate():
    g = _game(cons_spread_home=-6.5)
    assert spread_lean(g, {"home_fav_3.5_7": {"win_rate": 0.60, "n": 49}}).state == "no_lean"
    assert spread_lean(g, {"home_fav_3.5_7": {"win_rate": 0.60, "n": 50}}).state == "lean"


def test_spread_pickem_is_no_lean():
    ml = spread_lean(_game(cons_spread_home=0.0), {"pickem": {"win_rate": 0.60, "n": 800}})
    assert ml.state == "no_lean"


def test_spread_no_data_and_no_line():
    assert spread_lean(_game(cons_spread_home=-6.5), {}).state == "no_data"
    assert spread_lean(_game(cons_spread_home=-6.5),
                       {"home_fav_3.5_7": {"win_rate": 0.0, "n": 0}}).state == "no_data"
    no_line = spread_lean(_game(cons_spread_home=None), {"x": {"win_rate": 0.6, "n": 99}})
    assert no_line.state == "no_line"
