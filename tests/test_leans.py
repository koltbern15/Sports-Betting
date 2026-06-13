from engine.leans import game_leans, spread_lean, total_lean
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


def test_spread_home_dog_lean():
    # Home team is the underdog (+6.5) but covers historically at a high rate.
    rates = {"home_dog_3.5_7": {"win_rate": 0.56, "n": 200}}
    ml = spread_lean(_game(cons_spread_home=6.5), rates)
    assert ml.state == "lean"
    assert "Los Angeles Rams" in ml.side_label and "+6.5" in ml.side_label
    assert "home dog" in ml.side_label
    assert ml.best_for_lean == ("FanDuel", -6.5, -105)


def test_total_over_lean():
    ml = total_lean(_game(cons_total=47.5), {"total_46_48_5": {"win_rate": 0.55, "n": 300}})
    assert ml.state == "lean"
    assert ml.side_label == "OVER 47.5"
    assert ml.best_for_lean == ("DK", 44.5, -108)


def test_total_under_lean():
    ml = total_lean(_game(cons_total=47.5), {"total_46_48_5": {"win_rate": 0.44, "n": 300}})
    assert ml.state == "lean"
    assert ml.side_label == "UNDER 47.5"
    assert ml.best_for_lean == ("BetMGM", 44.5, -105)


def test_total_below_breakeven_is_no_lean():
    ml = total_lean(_game(cons_total=47.5), {"total_46_48_5": {"win_rate": 0.515, "n": 600}})
    assert ml.state == "no_lean"
    assert ml.rate == 0.515


def test_total_no_data_and_no_line():
    assert total_lean(_game(cons_total=47.5), {}).state == "no_data"
    assert total_lean(_game(cons_total=None), {"x": {"win_rate": 0.6, "n": 99}}).state == "no_line"


def test_game_leans_returns_spread_then_total():
    sp_rates = {"home_fav_3.5_7": {"win_rate": 0.531, "n": 612}}
    tot_rates = {"total_43_45_5": {"win_rate": 0.55, "n": 300}}
    sp, tot = game_leans(_game(), sp_rates, tot_rates)
    assert sp.market == "spread" and tot.market == "total"
    assert sp.state == "lean" and tot.state == "lean"
