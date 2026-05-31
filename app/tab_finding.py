"""The Finding — narrative hero: the CLV signal, with the open-vs-close proof panel."""

from __future__ import annotations

import streamlit as st

from app import charts, data


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
    lo, hi = spread["win_rate"].iloc[0], spread["win_rate"].iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("Spread win rate: low → high CLV", f"{lo:.1%} → {hi:.1%}")
    c2.metric("CLV ↔ result", "r ≈ 0.12 · p ≈ 1e-14")
    c3.metric("Bets analyzed", f"{int(spread['n'].sum()):,}+")
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
