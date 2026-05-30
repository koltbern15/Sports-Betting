"""Load opening lines from all sources into the opening_lines DB table.

Sources:
  - SBR (SportsbookReviewsOnline): 2007-2021, spread + total, fetched + cached.
  - aussportsbetting: manual-download xlsx, spread + total + ML, ~2006-2025.

Run: uv run python scripts/load_opening_lines.py
Idempotent: safe to re-run (INSERT OR REPLACE).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import connect, init_schema  # noqa: E402
from ingestion.opening_line_aus import load_local  # noqa: E402
from ingestion.opening_line_loader import load_records  # noqa: E402
from ingestion.opening_line_sbr import fetch_season, parse_sbr_html  # noqa: E402

DB_PATH = "data/db/nfl_betting.sqlite"
SBR_SEASONS = list(range(2007, 2022))  # 2007..2021 inclusive (15 seasons)
_FETCH_DELAY = 1.5  # seconds between uncached network fetches


def main() -> int:
    conn = connect(DB_PATH)
    init_schema(conn)  # adds opening_lines if absent; idempotent

    # -----------------------------------------------------------------------
    # SBR: 2007-2021
    # -----------------------------------------------------------------------
    sbr_inserted = 0
    sbr_unmatched = 0
    sbr_skipped_seasons = 0

    for i, season in enumerate(SBR_SEASONS):
        cache_path = Path("data/raw") / f"sbr_{season}.html"
        already_cached = cache_path.exists()

        try:
            html = fetch_season(season)
        except Exception as exc:  # noqa: BLE001
            print(f"  [SBR] WARNING: could not fetch {season}: {exc}")
            sbr_skipped_seasons += 1
            continue

        if not already_cached and i < len(SBR_SEASONS) - 1:
            # Polite delay only after a real network fetch
            time.sleep(_FETCH_DELAY)

        try:
            recs = parse_sbr_html(html, season)
            rep = load_records(conn, recs)
            sbr_inserted += rep.inserted
            sbr_unmatched += rep.unmatched
            print(
                f"  [SBR] {season}: parsed={len(recs)}"
                f"  inserted={rep.inserted}  unmatched={rep.unmatched}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  [SBR] WARNING: could not parse/load {season}: {exc}")
            sbr_skipped_seasons += 1

    # -----------------------------------------------------------------------
    # aussportsbetting
    # -----------------------------------------------------------------------
    aus_inserted = 0
    aus_unmatched = 0

    try:
        print("\n[AUS] Loading aussportsbetting xlsx...")
        aus_recs = load_local()
        print(f"  [AUS] Parsed {len(aus_recs)} records from xlsx")
        aus_rep = load_records(conn, aus_recs)
        aus_inserted = aus_rep.inserted
        aus_unmatched = aus_rep.unmatched
        print(
            f"  [AUS] inserted={aus_rep.inserted}  unmatched={aus_rep.unmatched}"
        )
    except FileNotFoundError as exc:
        print(f"  [AUS] SKIPPED — {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [AUS] ERROR — {exc}")

    conn.close()

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    print("=" * 60)
    print("LOAD SUMMARY")
    print("=" * 60)
    print(
        f"SBR  (2007-2021): inserted={sbr_inserted}  unmatched={sbr_unmatched}"
        + (f"  seasons_skipped={sbr_skipped_seasons}" if sbr_skipped_seasons else "")
    )
    print(
        f"AUS  (~2006-2025): inserted={aus_inserted}  unmatched={aus_unmatched}"
    )
    print(f"TOTAL inserted: {sbr_inserted + aus_inserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
