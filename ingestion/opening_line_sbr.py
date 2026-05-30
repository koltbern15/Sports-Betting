"""Parse SportsbookReviewsOnline (SBR) NFL season odds pages into records.

SBR publishes one HTML table per season. Quirks handled here:
- No string headers: pandas yields integer column labels; row 0 is the header.
- Two rows per game: away (VH='V') then home (VH='H'); 'N' for neutral site.
- Open column is dual-use per pair: one row holds the game TOTAL (>25), the
  other holds the home-side SPREAD magnitude (<=25, or 'pk' = pickem = 0). The
  V/H assignment is NOT consistent across games, so classify by magnitude.
- Spread sign: home is favorite iff the home row's ML (moneyline) is negative.
- Team names are concatenated short forms ('TampaBay', 'GreenBay') — mapped to
  canonical full names via _SBR_TEAM_ALIAS below.
- ML here is treated as closing/uncertain: opening ML is NOT emitted.
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import pandas as pd

from ingestion.opening_line_common import (
    OpeningLineRecord,
    canonical_team,
    normalize_spread_sign,
    to_iso_date_mmdd,
)

# Column positions in the SBR table (integer-labeled; header is data row 0).
_COL_DATE = 0
_COL_VH = 2
_COL_TEAM = 3
_COL_OPEN = 9
_COL_ML = 11

# Values <= this magnitude are spreads; values above are game totals.
_SPREAD_MAX = 25.0

# SBR concatenated team string -> canonical full name. canonical_team is still
# applied after the lookup so already-canonical names pass through unchanged.
_SBR_TEAM_ALIAS: dict[str, str] = {
    "Arizona": "Arizona Cardinals",
    "Atlanta": "Atlanta Falcons",
    "Baltimore": "Baltimore Ravens",
    "Buffalo": "Buffalo Bills",
    "Carolina": "Carolina Panthers",
    "Chicago": "Chicago Bears",
    "Cincinnati": "Cincinnati Bengals",
    "Cleveland": "Cleveland Browns",
    "Dallas": "Dallas Cowboys",
    "Denver": "Denver Broncos",
    "Detroit": "Detroit Lions",
    "GreenBay": "Green Bay Packers",
    "Houston": "Houston Texans",
    "Indianapolis": "Indianapolis Colts",
    "Jacksonville": "Jacksonville Jaguars",
    "KansasCity": "Kansas City Chiefs",
    "LAChargers": "Los Angeles Chargers",
    "LARams": "Los Angeles Rams",
    "LasVegas": "Las Vegas Raiders",
    "Miami": "Miami Dolphins",
    "Minnesota": "Minnesota Vikings",
    "NYGiants": "New York Giants",
    "NYJets": "New York Jets",
    "NewEngland": "New England Patriots",
    "NewOrleans": "New Orleans Saints",
    "Philadelphia": "Philadelphia Eagles",
    "Pittsburgh": "Pittsburgh Steelers",
    "SanFrancisco": "San Francisco 49ers",
    "Seattle": "Seattle Seahawks",
    "TampaBay": "Tampa Bay Buccaneers",
    "Tennessee": "Tennessee Titans",
    "Washington": "Washington Commanders",
}

_BASE_URL = "https://www.sportsbookreviewsonline.com/scoresoddsarchives"


def _resolve_team(raw: str) -> str:
    """Map an SBR team string to its canonical full name."""
    raw = str(raw).strip()
    return canonical_team(_SBR_TEAM_ALIAS.get(raw, raw))


def _parse_open_value(raw: object) -> float:
    """Parse one Open cell into a numeric magnitude. 'pk' -> 0.0."""
    s = str(raw).strip().lower()
    if s in ("pk", "pick", "p"):
        return 0.0
    return float(s)


def _classify_pair(v_open: float, h_open: float) -> tuple[float, float]:
    """Split the two Open values of a game-pair into (spread_magnitude, total).

    The value above _SPREAD_MAX is the game total; the other is the home-side
    spread magnitude. 'pk' (0.0) is always the spread.
    """
    if v_open > _SPREAD_MAX and h_open <= _SPREAD_MAX:
        return h_open, v_open
    if h_open > _SPREAD_MAX and v_open <= _SPREAD_MAX:
        return v_open, h_open
    # Both look like spreads (e.g. a pickem game with a small total is
    # impossible in the NFL) or both look like totals — pick the larger as the
    # total and the smaller as the spread.
    if v_open >= h_open:
        return h_open, v_open
    return v_open, h_open


def _select_games_table(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Pick the odds table: the one whose header row contains 'Open' and 'VH'."""
    for df in tables:
        header = [str(x).strip() for x in df.iloc[0].tolist()]
        if "Open" in header and "VH" in header and "Team" in header:
            return df
    # Fall back to the widest table.
    return max(tables, key=lambda d: d.shape[1])


def parse_sbr_html(html: str | bytes, season: int) -> list[OpeningLineRecord]:
    """Parse an SBR season odds page into OpeningLineRecords. Pure, no network.

    Iterates rows in away/home pairs. Each game-pair that fails to parse (bad
    cell, unknown team, malformed pair) is skipped, never aborting the whole
    parse. Opening ML is not emitted (open_ml_home/away = None).
    """
    buf: io.StringIO | io.BytesIO
    if isinstance(html, bytes):
        buf = io.BytesIO(html)
    else:
        buf = io.StringIO(html)
    tables = pd.read_html(buf)
    df = _select_games_table(tables)

    # Drop the header row (row 0); keep data rows in order.
    rows = df.iloc[1:].reset_index(drop=True)
    source_url = (
        f"{_BASE_URL}/nfl-odds-{season}-{(season + 1) % 100:02d}/"
    )

    records: list[OpeningLineRecord] = []
    n = len(rows)
    for i in range(0, n - 1, 2):
        away = rows.iloc[i]
        home = rows.iloc[i + 1]
        try:
            # Sanity-check pairing via the VH column when present.
            away_vh = str(away.iloc[_COL_VH]).strip().upper()
            home_vh = str(home.iloc[_COL_VH]).strip().upper()
            if away_vh not in ("V", "N") or home_vh not in ("H", "N"):
                continue

            away_team = _resolve_team(away.iloc[_COL_TEAM])
            home_team = _resolve_team(home.iloc[_COL_TEAM])

            v_open = _parse_open_value(away.iloc[_COL_OPEN])
            h_open = _parse_open_value(home.iloc[_COL_OPEN])
            spread_mag, total = _classify_pair(v_open, h_open)

            home_ml = float(str(home.iloc[_COL_ML]).strip())
            home_is_favorite = home_ml < 0
            open_spread_home = normalize_spread_sign(
                spread_mag, home_is_favorite=home_is_favorite
            )

            mmdd = int(float(str(away.iloc[_COL_DATE]).strip()))
            game_date = to_iso_date_mmdd(mmdd, season)

            records.append(
                OpeningLineRecord(
                    season=season,
                    game_date=game_date,
                    home_team=home_team,
                    away_team=away_team,
                    open_spread_home=open_spread_home,
                    open_total=total,
                    open_ml_home=None,
                    open_ml_away=None,
                    source="sbr",
                    source_url=source_url,
                )
            )
        except (KeyError, ValueError, TypeError, IndexError):
            # Skip-and-count: a malformed pair must not abort the whole parse.
            continue

    return records


def fetch_season(season: int) -> str:
    """Fetch (and cache) the SBR season odds page. I/O boundary; not for tests.

    Reads data/raw/sbr_{season}.html if present; otherwise GETs the page with a
    browser User-Agent, writes the cache, and returns the text.
    """
    cache = Path("data/raw") / f"sbr_{season}.html"
    if cache.exists():
        return cache.read_text(encoding="utf-8", errors="replace")

    url = f"{_BASE_URL}/nfl-odds-{season}-{(season + 1) % 100:02d}/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:  # noqa: S310 (trusted host)
        text = resp.read().decode("utf-8", errors="replace")

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text
