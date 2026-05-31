"""Edge Report — the honest-metrics table (Slice 5): no certified static edge."""

from __future__ import annotations

import streamlit as st

from app import charts, data


def render() -> None:
    st.subheader("Edge report — every bucket, with its uncertainty")
    st.write(
        "No static bucket shows a **certified** edge. That's a statement about statistical "
        "power, not proof the market is perfectly efficient — a real +2% ROI edge would be "
        "invisible at these sample sizes. `mde80_roi` = smallest edge detectable at this n."
    )
    df = data.load_edge_report()
    if df.empty:
        st.info("Edge report not available — generate it with the engine reports then "
                "`uv run python -m engine.edge_report`.")
        return
    markets = sorted(df["market"].unique())
    pick = st.selectbox("Market", markets, key="edge_market")
    sub = df[df["market"] == pick].copy()
    for col in ("point_roi", "ci_low", "ci_high"):
        sub[col] = sub[col].astype(float)
    st.altair_chart(charts.ci_errorbar_chart(sub), use_container_width=True)
    st.dataframe(sub, use_container_width=True, hide_index=True)
    st.caption("Past performance ≠ future results. Informational only; gamble responsibly.")
