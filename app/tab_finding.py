"""The Finding — narrative hero: the CLV signal, with the open-vs-close proof panel."""

from __future__ import annotations

import math

import streamlit as st

from app import charts, data
from engine.clv import CLV_BUCKET_ORDER


def render() -> None:
    st.subheader("The close is sharper than the open")
    st.write(
        "After we showed static bucket strategies are noise, this is the project's one real "
        "signal: when the line moves toward your side after you bet, you were more likely right — "
        "because the closing line is a better estimate than the opener."
    )
    bounds = data.season_bounds()
    spread = data.clv_ladder(market="spread", season_range=bounds, grade_at="open")
    if spread.empty:
        st.info("CLV data not available — generate it with `uv run python -m engine.clv`.")
        return
    # Win-rate swing across the CLV extremes, selected by bucket LABEL (not row
    # position) so it always compares the most-negative vs most-positive CLV bucket.
    lo_row = spread.loc[spread["clv_bucket"] == CLV_BUCKET_ORDER[0], "win_rate"]
    hi_row = spread.loc[spread["clv_bucket"] == CLV_BUCKET_ORDER[-1], "win_rate"]
    swing = (
        f"{lo_row.iloc[0]:.1%} → {hi_row.iloc[0]:.1%}"
        if not lo_row.empty and not hi_row.empty
        else "—"
    )

    # Live CLV<->result correlation (replaces a former hardcoded "r ≈ 0.12 · p ≈ 1e-14"
    # literal so the figure tracks the actual data window).
    r, p, _n = data.clv_result_correlation(market="spread", season_range=bounds)
    if not math.isnan(r):
        p_str = "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
        corr = f"r ≈ {r:.2f} · {p_str}"
    else:
        corr = "—"

    # Bets analyzed across BOTH markets (spread + total), matching the design intent.
    total = data.clv_ladder(market="total", season_range=bounds, grade_at="open")
    n_bets = int(spread["n"].sum()) + (int(total["n"].sum()) if not total.empty else 0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Spread win rate: low → high CLV", swing)
    c2.metric("CLV ↔ result", corr)
    c3.metric("Bets analyzed", f"{n_bets:,}")
    st.altair_chart(charts.clv_ladder_chart(spread), use_container_width=True)

    st.markdown("##### Why it's real, not an artifact")
    st.caption("Grade the same bets at the OPENING number → win rate rises with CLV. "
               "Grade them at the CLOSING number → the trend flattens. The close has absorbed "
               "the information — proof the signal is genuine.")
    p1, p2 = st.columns(2)
    with p1:
        st.caption("graded @ opener (rises ↗)")
        st.altair_chart(charts.clv_ladder_chart(spread), use_container_width=True)
    with p2:
        st.caption("graded @ close (flat — signal gone)")
        close = data.clv_ladder(market="spread", season_range=bounds, grade_at="close")
        if close.empty:
            st.caption("—")
        else:
            st.altair_chart(charts.clv_ladder_chart(close), use_container_width=True)
    st.caption("⚠ Signal test, not a tradeable strategy — CLV is unknowable until the line "
               "closes. Past performance ≠ future results.")
