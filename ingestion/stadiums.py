"""Stadium dome-flag lookup.

Includes every NFL stadium used in the 2004–2024 window. Conservative default
for unknown stadiums is False (outdoor) — we'd rather mis-classify a rare
neutral-site dome as outdoor than the reverse.
"""

from __future__ import annotations

_DOME_STADIUMS: set[str] = {
    # Fixed-roof domes
    "Mercedes-Benz Superdome",
    "Caesars Superdome",
    "Ford Field",
    "Hubert H. Humphrey Metrodome",
    "U.S. Bank Stadium",
    "Edward Jones Dome",
    "RCA Dome",
    "Lucas Oil Stadium",
    "Alamodome",
    "Carrier Dome",
    "Allegiant Stadium",
    "SoFi Stadium",
    "Mercedes-Benz Stadium",
    # Retractable-roof domes (counted as domes since the league decides whether
    # to play with the roof open or closed, and for Slice 1 we only need the
    # gross indoor/outdoor distinction)
    "AT&T Stadium",
    "NRG Stadium",
    "Reliant Stadium",
    "State Farm Stadium",
    "University of Phoenix Stadium",
    "Cardinals Stadium",
    "Tottenham Hotspur Stadium",
}


def is_dome(stadium: str | None) -> bool:
    """True if the stadium has a roof. Unknown / missing → False."""
    if stadium is None:
        return False
    return stadium in _DOME_STADIUMS
