"""Altair chart builders for the dashboard (refined-dark friendly)."""

from __future__ import annotations

import altair as alt
import pandas as pd

from engine.clv import CLV_BUCKET_ORDER
from engine.stats_utils import BREAKEVEN_AT_NEG_110

_ACCENT = "#6c8cff"


def clv_ladder_chart(df: pd.DataFrame) -> alt.Chart:
    """Win rate by CLV bucket as a line+points, with a breakeven reference line.

    A line (not bars) so the y-axis can zoom to the data without the truncated-
    baseline distortion bars would imply — the monotonic climb (and, in the proof
    panel, 'rising vs flat') reads honestly against the breakeven line.
    """
    line = (
        alt.Chart(df)
        .mark_line(color=_ACCENT, point=alt.OverlayMarkDef(color=_ACCENT, size=90))
        .encode(
            x=alt.X("clv_bucket:N", sort=CLV_BUCKET_ORDER,
                    title="CLV bucket (← against · toward →)"),
            y=alt.Y("win_rate:Q", title="win rate", scale=alt.Scale(zero=False)),
            tooltip=["clv_bucket", "win_rate", "mean_clv"],
        )
    )
    rule = (
        alt.Chart(pd.DataFrame({"y": [BREAKEVEN_AT_NEG_110]}))
        .mark_rule(color="#9aa0ad", strokeDash=[4, 4])
        .encode(y="y:Q")
    )
    return (line + rule).properties(height=260)


def ci_errorbar_chart(df: pd.DataFrame) -> alt.Chart:
    """Point ROI per bucket with 95% CI error bars and a breakeven (0) line."""
    base = alt.Chart(df)
    points = base.mark_point(color=_ACCENT, filled=True, size=70).encode(
        x=alt.X("bucket:N", title="bucket"),
        y=alt.Y("point_roi:Q", title="point ROI"),
        tooltip=["bucket", "point_roi", "ci_low", "ci_high"],
    )
    bars = base.mark_rule(color=_ACCENT).encode(x="bucket:N", y="ci_low:Q", y2="ci_high:Q")
    zero = (
        alt.Chart(pd.DataFrame({"y": [0.0]}))
        .mark_rule(color="#9aa0ad", strokeDash=[4, 4])
        .encode(y="y:Q")
    )
    return (bars + points + zero).properties(height=300)
