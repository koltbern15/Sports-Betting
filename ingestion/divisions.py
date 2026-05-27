"""Static NFL division lookup (2002 realignment, valid 2002–present).

Teams are stored by their canonical name. Use ingestion/team_names.py to
normalize a possibly-historical name (e.g. "St. Louis Rams") to its canonical
form ("Los Angeles Rams") before looking up here.
"""

from __future__ import annotations

DIVISIONS: dict[str, tuple[str, str]] = {
    # AFC East
    "Buffalo Bills": ("AFC", "East"),
    "Miami Dolphins": ("AFC", "East"),
    "New England Patriots": ("AFC", "East"),
    "New York Jets": ("AFC", "East"),
    # AFC North
    "Baltimore Ravens": ("AFC", "North"),
    "Cincinnati Bengals": ("AFC", "North"),
    "Cleveland Browns": ("AFC", "North"),
    "Pittsburgh Steelers": ("AFC", "North"),
    # AFC South
    "Houston Texans": ("AFC", "South"),
    "Indianapolis Colts": ("AFC", "South"),
    "Jacksonville Jaguars": ("AFC", "South"),
    "Tennessee Titans": ("AFC", "South"),
    # AFC West
    "Denver Broncos": ("AFC", "West"),
    "Kansas City Chiefs": ("AFC", "West"),
    "Las Vegas Raiders": ("AFC", "West"),
    "Los Angeles Chargers": ("AFC", "West"),
    # NFC East
    "Dallas Cowboys": ("NFC", "East"),
    "New York Giants": ("NFC", "East"),
    "Philadelphia Eagles": ("NFC", "East"),
    "Washington Commanders": ("NFC", "East"),
    # NFC North
    "Chicago Bears": ("NFC", "North"),
    "Detroit Lions": ("NFC", "North"),
    "Green Bay Packers": ("NFC", "North"),
    "Minnesota Vikings": ("NFC", "North"),
    # NFC South
    "Atlanta Falcons": ("NFC", "South"),
    "Carolina Panthers": ("NFC", "South"),
    "New Orleans Saints": ("NFC", "South"),
    "Tampa Bay Buccaneers": ("NFC", "South"),
    # NFC West
    "Arizona Cardinals": ("NFC", "West"),
    "Los Angeles Rams": ("NFC", "West"),
    "San Francisco 49ers": ("NFC", "West"),
    "Seattle Seahawks": ("NFC", "West"),
}


def division_of(team: str) -> tuple[str, str]:
    """Return (conference, division) for a canonical team name."""
    return DIVISIONS[team]


def same_division(team_a: str, team_b: str) -> bool:
    """True if both canonical team names are in the same division."""
    return DIVISIONS[team_a] == DIVISIONS[team_b]
