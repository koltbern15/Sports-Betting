"""Data & Audit — coverage, cross-source agreement, and data provenance."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import data


def render() -> None:
    st.subheader("Data & Audit")
    s = data.audit_summary()
    c1, c2, c3 = st.columns(3)
    c1.metric("Opening-line rows", f"{s['opening_rows_total']:,}")
    c2.metric("Cross-source agree (spread, ±1pt)", f"{s['overlap_spread_within_1pt']:.0%}")
    c3.metric("Cross-source agree (total, ±1pt)", f"{s['overlap_total_within_1pt']:.0%}")
    st.caption(f"Agreement measured across ~{s['overlap_games']:,} games where both opening-line "
               "sources overlap (2013–2021). Sub-100% is expected — openers vary across "
               "books/timestamps.")

    st.markdown("##### Data sources")
    st.dataframe(pd.DataFrame(s["sources"]), use_container_width=True, hide_index=True)

    st.markdown("##### Opening-line coverage by season")
    cov = data.opening_line_coverage()
    if cov.empty:
        st.info("Coverage data not available — load opening lines first "
                "(`uv run python scripts/load_opening_lines.py`).")
    else:
        pivot = cov.pivot(index="season", columns="source", values="games").fillna(0).astype(int)
        st.dataframe(pivot, use_container_width=True)
    st.caption("Sources cross-validated; closing lines match nflverse ≥96% within ±1pt.")
