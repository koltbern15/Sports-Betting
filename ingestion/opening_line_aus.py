"""Parse the Australia Sports Betting NFL xlsx into OpeningLineRecords.

Opening odds present ~2013+. Odds are decimal (converted to American). Spread
(Home Line Open) already uses our sign convention (negative = home favored).
See docs/superpowers/notes/2026-05-29-opening-line-probe.md for the verified columns.
The xlsx is Cloudflare-gated to bots; it must be downloaded manually to data/raw/aus_nfl.xlsx.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ingestion.opening_line_common import (
    OpeningLineRecord,
    canonical_team,
    decimal_to_american,
    to_iso_date,
)

_SOURCE_URL = "https://www.aussportsbetting.com/historical_data/nfl.xlsx"
_LOCAL_PATH = Path("data/raw/aus_nfl.xlsx")


def _f(v) -> float | None:
    return None if pd.isna(v) else float(v)


def _safe_american(dec: float | None) -> int | None:
    if dec is None:
        return None
    try:
        return decimal_to_american(dec)
    except ValueError:
        return None


def _season_from_date(d) -> int:
    return d.year if d.month >= 8 else d.year - 1


def parse_aus_xlsx(path: str | Path) -> list[OpeningLineRecord]:
    """Parse the aussportsbetting xlsx into OpeningLineRecords (opening lines only).

    Rows with no opening spread/total/ML are skipped. Rows with an unknown team
    name or a bad cell are skipped (not fatal) so one bad row can't sink the load.
    """
    df = pd.read_excel(path)
    records: list[OpeningLineRecord] = []
    for _idx, row in df.iterrows():
        try:
            spread = _f(row["Home Line Open"])
            total = _f(row["Total Score Open"])
            ml_home = _safe_american(_f(row["Home Odds Open"]))
            ml_away = _safe_american(_f(row["Away Odds Open"]))
            if spread is None and total is None and ml_home is None and ml_away is None:
                continue
            d = pd.to_datetime(row["Date"]).to_pydatetime()
            records.append(
                OpeningLineRecord(
                    season=_season_from_date(d),
                    game_date=to_iso_date(d),
                    home_team=canonical_team(str(row["Home Team"])),
                    away_team=canonical_team(str(row["Away Team"])),
                    open_spread_home=spread,
                    open_total=total,
                    open_ml_home=ml_home,
                    open_ml_away=ml_away,
                    source="aus",
                    source_url=_SOURCE_URL,
                )
            )
        except (KeyError, ValueError, TypeError):
            # unknown team / unparseable cell -> skip this row, keep going
            continue
    return records


def load_local() -> list[OpeningLineRecord]:
    """Parse the manually-downloaded xlsx at data/raw/aus_nfl.xlsx."""
    if not _LOCAL_PATH.exists():
        raise FileNotFoundError(
            f"{_LOCAL_PATH} not found. The aussportsbetting xlsx is Cloudflare-gated; "
            "download it manually in a browser from "
            "https://www.aussportsbetting.com/data/historical-nfl-results-and-odds-data/ "
            f"and save it to {_LOCAL_PATH}."
        )
    return parse_aus_xlsx(_LOCAL_PATH)
