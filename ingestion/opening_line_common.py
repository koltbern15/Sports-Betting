"""Shared types + pure normalization helpers for opening-line ingestion.

Both source parsers (SBR, aussportsbetting) emit OpeningLineRecord and reuse
these helpers so the loader is source-agnostic.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from ingestion.team_names import canonicalize_team_name


@dataclass(frozen=True)
class OpeningLineRecord:
    season: int
    game_date: str  # ISO yyyy-mm-dd, matches games.game_date
    home_team: str  # canonical full name
    away_team: str
    open_spread_home: float | None  # home-perspective, negative = home favored
    open_total: float | None
    open_ml_home: int | None  # American odds; None if source lacks ML
    open_ml_away: int | None
    source: str  # 'sbr' | 'aus'
    source_url: str


def canonical_team(name: str) -> str:
    """Normalize a team name to canonical full form. Raises KeyError if unknown."""
    return canonicalize_team_name(name.strip())


def to_iso_date(d: datetime.date | datetime.datetime) -> str:
    """Format a date/datetime as ISO yyyy-mm-dd."""
    if isinstance(d, datetime.datetime):
        d = d.date()
    return d.isoformat()


def to_iso_date_mmdd(mmdd: int, season: int) -> str:
    """Convert an SBR-style MMDD integer within an NFL season to ISO yyyy-mm-dd.

    NFL seasons span Sep-Feb. Months >= 8 belong to the season's calendar year;
    months <= 7 (Jan/Feb playoffs) belong to season + 1.
    """
    month = mmdd // 100
    day = mmdd % 100
    year = season if month >= 8 else season + 1
    return datetime.date(year, month, day).isoformat()


def normalize_spread_sign(magnitude: float, *, home_is_favorite: bool) -> float:
    """Return the home-perspective spread: negative when the home team is favored."""
    m = abs(magnitude)
    return -m if home_is_favorite else m


def decimal_to_american(decimal_odds: float | None) -> int | None:
    """Convert decimal odds to American odds (int), or None if input is None."""
    if decimal_odds is None:
        return None
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal odds must be > 1.0, got {decimal_odds}")
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1.0) * 100)
    return -round(100.0 / (decimal_odds - 1.0))
