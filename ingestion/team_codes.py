"""nflverse team abbreviation → canonical full-name mapping.

nflverse uses stable 2-3-letter codes (KC, LV, LAC, WAS). This module maps
each to the canonical name used in our DB (matches `ingestion/team_names.py`
output). Update the probe doc's "Team abbreviation codes seen" if any code
is missing here.
"""

from __future__ import annotations

NFLVERSE_TEAM_CODES: dict[str, str] = {
    # AFC East
    "BUF": "Buffalo Bills",
    "MIA": "Miami Dolphins",
    "NE": "New England Patriots",
    "NYJ": "New York Jets",
    # AFC North
    "BAL": "Baltimore Ravens",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "PIT": "Pittsburgh Steelers",
    # AFC South
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "TEN": "Tennessee Titans",
    # AFC West
    "DEN": "Denver Broncos",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    # NFC East
    "DAL": "Dallas Cowboys",
    "NYG": "New York Giants",
    "PHI": "Philadelphia Eagles",
    "WAS": "Washington Commanders",
    # NFC North
    "CHI": "Chicago Bears",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "MIN": "Minnesota Vikings",
    # NFC South
    "ATL": "Atlanta Falcons",
    "CAR": "Carolina Panthers",
    "NO": "New Orleans Saints",
    "TB": "Tampa Bay Buccaneers",
    # NFC West
    "ARI": "Arizona Cardinals",
    "LA": "Los Angeles Rams",
    "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
}


def code_to_canonical(code: str) -> str:
    """Look up the canonical full name for an nflverse team code."""
    try:
        return NFLVERSE_TEAM_CODES[code]
    except KeyError as e:
        raise KeyError(f"unknown nflverse team code: {code!r}") from e
