"""CLV Explorer — interactive: filter by market + season range, re-bucket live."""

from __future__ import annotations

import streamlit as st

from app import charts, data


def render(season_range) -> None:
    st.subheader("CLV Explorer")
    st.write("Slice the closing-line-value signal yourself. Win rate should rise with CLV; "
             "the positive-CLV tails are statistically marginal — the **monotonic shape** is "
             "the evidence, not any single bucket.")
    market = st.radio("Market", ["spread", "total"], horizontal=True, key="clv_market")
    df = data.clv_ladder(market=market, season_range=season_range, grade_at="open")
    if df.empty:
        st.info(f"No {market} CLV data for seasons {season_range[0]}–{season_range[1]}.")
        return
    st.altair_chart(charts.clv_ladder_chart(df), use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Signal test, not a tradeable strategy — CLV is unknowable until the close.")
