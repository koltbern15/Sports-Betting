"""Tests for app.data — cached data-access loaders (logic tested without Streamlit cache)."""

from __future__ import annotations

from app import data as appdata
from engine.db import connect, init_schema


def _seed_clv(conn):
    # g1: home wins 24-20 (+4). open=-3 (covers: 4>3), close=-7 (loses: 4<7).
    #     CLV_spread = open - close = -3 - (-7) = +4 -> clv_gt_2 bucket.
    #     grade_at=open -> WIN; grade_at=close -> LOSS. Win rates WILL differ.
    # g2: home wins 30-20 (+10). open=-3 (covers), close=-6 (covers).
    #     CLV_spread = -3 - (-6) = +3 -> clv_gt_2 bucket.
    #     grade_at=open -> WIN; grade_at=close -> WIN.
    # Season split: g1=2015, g2=2020 so season_range filter test works.
    conn.executescript(
        "INSERT INTO games"
        " (game_id,season,week,game_date,home_team,away_team,home_score,away_score)"
        " VALUES ('g1',2015,1,'2015-09-13','Dallas Cowboys','New York Giants',24,20),"
        "        ('g2',2020,1,'2020-09-13','Green Bay Packers','Chicago Bears',30,20);"
        "INSERT INTO betting_lines (game_id,spread_home_close,total_close)"
        " VALUES ('g1',-7.0,45.0),('g2',-6.0,44.0);"
        "INSERT INTO opening_lines (game_id,source,open_spread_home,open_total)"
        " VALUES ('g1','aus',-3.0,45.0),('g2','aus',-3.0,44.0);"
    )
    conn.commit()


def _call(fn, **kw):
    """Call a possibly-cache-wrapped loader, bypassing the cache if present."""
    return getattr(fn, "__wrapped__", fn)(**kw)


def test_clv_ladder_filters_by_market_and_season(monkeypatch):
    conn = connect(":memory:")
    init_schema(conn)
    _seed_clv(conn)
    monkeypatch.setattr(appdata, "_open_db", lambda: conn)
    df_all = _call(appdata.clv_ladder, market="spread", season_range=(2000, 2030))
    df_2020 = _call(appdata.clv_ladder, market="spread", season_range=(2019, 2021))
    assert not df_all.empty
    assert df_2020["n"].sum() < df_all["n"].sum()
    assert set(df_all["clv_bucket"]).issubset({
        "clv_le_neg2", "clv_neg2_neg05", "clv_pm05", "clv_05_2", "clv_gt_2",
    })


def test_clv_ladder_open_vs_close_differ(monkeypatch):
    conn = connect(":memory:")
    init_schema(conn)
    _seed_clv(conn)
    monkeypatch.setattr(appdata, "_open_db", lambda: conn)
    op = _call(appdata.clv_ladder, market="spread", season_range=(2000, 2030), grade_at="open")
    cl = _call(appdata.clv_ladder, market="spread", season_range=(2000, 2030), grade_at="close")
    win_rates_differ = list(op["win_rate"]) != list(cl["win_rate"])
    buckets_differ = list(op["clv_bucket"]) != list(cl["clv_bucket"])
    assert win_rates_differ or buckets_differ


def test_load_edge_report_missing_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(appdata, "_EDGE_CSV", tmp_path / "nope.csv")
    assert _call(appdata.load_edge_report).empty


def test_audit_summary_has_sources():
    s = appdata.audit_summary()
    assert "sources" in s and len(s["sources"]) == 4
    assert "overlap_spread_within_1pt" in s


def test_charts_build_without_error():
    import pandas as pd

    from app import charts  # noqa: E402
    ladder = pd.DataFrame({"clv_bucket": ["clv_pm05", "clv_gt_2"], "win_rate": [0.5, 0.57],
                           "mean_clv": [0.1, 3.0]})
    edge = pd.DataFrame({
        "bucket": ["b1"], "point_roi": [0.01], "ci_low": [-0.05], "ci_high": [0.07],
    })
    assert charts.clv_ladder_chart(ladder) is not None
    assert charts.ci_errorbar_chart(edge) is not None
