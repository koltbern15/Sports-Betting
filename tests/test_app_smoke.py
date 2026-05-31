"""Smoke test: the Streamlit app boots and renders without error (no live network)."""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402


def test_app_boots_without_error():
    at = AppTest.from_file("../app/main.py", default_timeout=30).run()
    assert not at.exception
