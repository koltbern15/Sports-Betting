"""Refined-dark CSS polish injected into the Streamlit app."""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
  .block-container { padding-top: 2rem; max-width: 1100px; }
  .twg-card { background:#1b1e26; border:1px solid #262b36; border-radius:12px;
              padding:16px 18px; margin-bottom:14px; }
  .twg-matchup { font-size:18px; font-weight:700; color:#e8eaf0; }
  .twg-time { font-size:12px; color:#9aa0ad; }
  .twg-best { color:#8aa0ff; font-weight:700; }
  .twg-move-up { color:#2ea043; font-weight:600; }
  .twg-move-down { color:#f85149; font-weight:600; }
  .twg-ctx { font-size:12px; color:#9aa0ad; }
  .twg-banner { background:#1b1e26; border:1px solid #2e3a52; border-radius:10px;
                padding:12px 16px; color:#c9d1e0; font-size:13px; margin-bottom:18px; }
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# Rendered inside a raw-HTML <div>, so use HTML tags (not markdown ** **) for emphasis.
HONESTY_BANNER = (
    "<strong>Context &amp; best prices — not certified picks.</strong> Historical rates are "
    "<em>not</em> a proven edge (the market is efficient — see the CLV finding). The real edge "
    "here is <strong>line shopping</strong>: take the best price. Line movement is descriptive. "
    "Past performance ≠ future results. Gamble responsibly."
)
