"""NFL Betting Analytics — live This Week odds board (Streamlit entry point)."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app import theme
from app.this_week_view import render as render_this_week
from engine.db import connect
from engine.this_week import build_board
from ingestion.live_odds import parse_odds_payload
from ingestion.live_odds_store import opener_consensus

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
    st.set_page_config(page_title="NFL Odds — This Week", page_icon="🏈", layout="wide")
    theme.inject()
    st.title("This Week — live NFL odds")
    (tab_week,) = st.tabs(["This Week"])
    with tab_week:
        render_this_week(_load_board())


main()
