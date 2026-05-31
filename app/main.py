"""NFL Betting Analytics — live This Week odds board (Streamlit entry point)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# `streamlit run app/main.py` puts app/ (not the project root) on sys.path, so the
# app/engine/ingestion packages aren't importable without this. (pytest adds the
# root via pythonpath, which is why the smoke test didn't surface it.)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from app import data, tab_clv, tab_data, tab_edge, tab_finding, theme  # noqa: E402
from app.this_week_view import render as render_this_week  # noqa: E402
from engine.db import connect  # noqa: E402
from engine.this_week import build_board  # noqa: E402
from ingestion.live_odds import parse_odds_payload  # noqa: E402
from ingestion.live_odds_store import opener_consensus  # noqa: E402

_DB = "data/db/nfl_betting.sqlite"
_LATEST = Path("data/raw/odds_api_latest.json")


@st.cache_data(show_spinner=False)
def _load_board():
    """Build the board from the latest stored snapshot file (no live call on page load)."""
    if not _LATEST.exists():
        return []
    games = parse_odds_payload(json.loads(_LATEST.read_text(encoding="utf-8")))
    try:
        conn = connect(_DB)
        openers = opener_consensus(conn)
        conn.close()
    except Exception:
        openers = {}
    return build_board(games, openers)


def main() -> None:
    st.set_page_config(page_title="NFL Betting Analytics", page_icon="🏈", layout="wide")
    theme.inject()
    st.title("NFL Betting Analytics")
    lo, hi = data.season_bounds()
    season_range = st.sidebar.slider("Season range (CLV Explorer)", lo, hi, (lo, hi))
    tabs = st.tabs(["This Week", "The Finding", "Edge Report", "CLV Explorer", "Data & Audit"])
    with tabs[0]:
        render_this_week(_load_board())
    with tabs[1]:
        tab_finding.render()
    with tabs[2]:
        tab_edge.render()
    with tabs[3]:
        tab_clv.render(season_range)
    with tabs[4]:
        tab_data.render()


main()
