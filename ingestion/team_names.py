"""Historical NFL team name normalization (covers 2004–2024 window).

Source CSVs (e.g. Kaggle spreadspoke_scores) record the name in use at game time.
This module maps any historical variant to the franchise's canonical 2024 name.
"""

from __future__ import annotations

# Canonical name = the team's 2024-season name. Mapping covers every variant
# seen in the 2004–2024 window plus a few obvious aliases (e.g. "LA Rams").
_NAME_MAP: dict[str, str] = {
    # AFC East
    "Buffalo Bills": "Buffalo Bills",
    "Miami Dolphins": "Miami Dolphins",
    "New England Patriots": "New England Patriots",
    "New York Jets": "New York Jets",
    # AFC North
    "Baltimore Ravens": "Baltimore Ravens",
    "Cincinnati Bengals": "Cincinnati Bengals",
    "Cleveland Browns": "Cleveland Browns",
    "Pittsburgh Steelers": "Pittsburgh Steelers",
    # AFC South
    "Houston Texans": "Houston Texans",
    "Indianapolis Colts": "Indianapolis Colts",
    "Jacksonville Jaguars": "Jacksonville Jaguars",
    "Tennessee Titans": "Tennessee Titans",
    # AFC West — Raiders moved Oakland → Las Vegas (2020); Chargers SD → LA (2017)
    "Denver Broncos": "Denver Broncos",
    "Kansas City Chiefs": "Kansas City Chiefs",
    "Las Vegas Raiders": "Las Vegas Raiders",
    "Oakland Raiders": "Las Vegas Raiders",
    "Los Angeles Chargers": "Los Angeles Chargers",
    "San Diego Chargers": "Los Angeles Chargers",
    # NFC East — Washington renamed twice (2020 → Football Team, 2022 → Commanders)
    "Dallas Cowboys": "Dallas Cowboys",
    "New York Giants": "New York Giants",
    "Philadelphia Eagles": "Philadelphia Eagles",
    "Washington Commanders": "Washington Commanders",
    "Washington Football Team": "Washington Commanders",
    "Washington Redskins": "Washington Commanders",
    # NFC North
    "Chicago Bears": "Chicago Bears",
    "Detroit Lions": "Detroit Lions",
    "Green Bay Packers": "Green Bay Packers",
    "Minnesota Vikings": "Minnesota Vikings",
    # NFC South
    "Atlanta Falcons": "Atlanta Falcons",
    "Carolina Panthers": "Carolina Panthers",
    "New Orleans Saints": "New Orleans Saints",
    "Tampa Bay Buccaneers": "Tampa Bay Buccaneers",
    # NFC West — Rams moved STL → LA (2016)
    "Arizona Cardinals": "Arizona Cardinals",
    "Los Angeles Rams": "Los Angeles Rams",
    "St. Louis Rams": "Los Angeles Rams",
    "San Francisco 49ers": "San Francisco 49ers",
    "Seattle Seahawks": "Seattle Seahawks",
}

CANONICAL_TEAMS: set[str] = set(_NAME_MAP.values())


def canonicalize_team_name(name: str) -> str:
    """Map any historical NFL team name to its canonical 2024 name.

    Raises KeyError on unknown names (callers should not silently accept
    typos or non-NFL teams).
    """
    return _NAME_MAP[name]
