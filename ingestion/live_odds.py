"""The Odds API client for live NFL odds.

Pure parse (parse_odds_payload) tested against a fixture; thin network boundary
(fetch_odds). Computes consensus (median across books, home-perspective) and the
best available price per side (line shopping). Key from ODDS_API_KEY env var.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from ingestion.team_names import canonicalize_team_name

_API = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
_ENV_FILE = Path(".env")

# best-line = (book_title, point_or_None, price)
BestLine = tuple[str, float | None, int]


@dataclass(frozen=True)
class GameOdds:
    game_key: str
    commence_time: str
    home_team: str
    away_team: str
    cons_spread_home: float | None
    cons_total: float | None
    cons_ml_home: int | None
    cons_ml_away: int | None
    best_spread_home: BestLine | None
    best_spread_away: BestLine | None
    best_total_over: BestLine | None
    best_total_under: BestLine | None
    best_ml_home: BestLine | None
    best_ml_away: BestLine | None
    n_books: int


def get_api_key() -> str | None:
    """Resolve ODDS_API_KEY from the environment, falling back to a gitignored .env."""
    key = os.getenv("ODDS_API_KEY")
    if key:
        return key.strip()
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ODDS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _game_key(commence_time: str, away: str, home: str) -> str:
    date = commence_time[:10]
    return f"{date}_{away.replace(' ', '_')}_at_{home.replace(' ', '_')}"


def _collect(bookmakers: list[dict], market_key: str, outcome_name: str) -> list[BestLine]:
    """Return (book_title, point, price) tuples for a market+outcome across books."""
    out: list[BestLine] = []
    for bk in bookmakers:
        for m in bk.get("markets", []):
            if m.get("key") != market_key:
                continue
            for o in m.get("outcomes", []):
                if o.get("name") == outcome_name:
                    price = o.get("price")
                    if price is None:
                        continue  # skip outcomes with missing/None price
                    title = bk.get("title", bk.get("key", "?"))
                    out.append((title, o.get("point"), int(price)))
    return out


def _median_or_none(vals: list[float]) -> float | None:
    return median(vals) if vals else None


def _best(lines: list[BestLine], *, by_point: str | None) -> BestLine | None:
    """Pick the most favorable line.

    by_point=None  -> moneyline: best = highest price.
    by_point='max' -> bettor wants the highest point (spread home/away backer; under).
    by_point='min' -> bettor wants the lowest point  (over backer).
    Tie-break on price (higher better).
    """
    if not lines:
        return None
    if by_point is None:
        return max(lines, key=lambda t: t[2])
    sign = 1 if by_point == "max" else -1
    return max(lines, key=lambda t: (sign * (t[1] if t[1] is not None else 0.0), t[2]))


def parse_odds_payload(payload: list[dict]) -> list[GameOdds]:
    """Parse The Odds API JSON into GameOdds. Unknown teams skip the game."""
    games: list[GameOdds] = []
    for evt in payload:
        # Skip-and-continue: one malformed event must not sink the whole snapshot.
        # Covers unknown teams (canonicalize KeyError) plus missing/None
        # commence_time and any bad outcome that slips past _collect.
        try:
            home = canonicalize_team_name(evt["home_team"])
            away = canonicalize_team_name(evt["away_team"])
            bks = evt.get("bookmakers", [])
            raw_home, raw_away = evt["home_team"], evt["away_team"]

            sp_home = _collect(bks, "spreads", raw_home)
            sp_away = _collect(bks, "spreads", raw_away)
            tot_over = _collect(bks, "totals", "Over")
            tot_under = _collect(bks, "totals", "Under")
            ml_home = _collect(bks, "h2h", raw_home)
            ml_away = _collect(bks, "h2h", raw_away)

            games.append(GameOdds(
                game_key=_game_key(evt["commence_time"], away, home),
                commence_time=evt["commence_time"],
                home_team=home,
                away_team=away,
                cons_spread_home=_median_or_none([p for _b, p, _pr in sp_home if p is not None]),
                cons_total=_median_or_none([p for _b, p, _pr in tot_over if p is not None]),
                cons_ml_home=round(median([pr for _b, _p, pr in ml_home])) if ml_home else None,
                cons_ml_away=round(median([pr for _b, _p, pr in ml_away])) if ml_away else None,
                best_spread_home=_best(sp_home, by_point="max"),
                best_spread_away=_best(sp_away, by_point="max"),
                best_total_over=_best(tot_over, by_point="min"),
                best_total_under=_best(tot_under, by_point="max"),
                best_ml_home=_best(ml_home, by_point=None),
                best_ml_away=_best(ml_away, by_point=None),
                n_books=len(bks),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return games


def fetch_odds(api_key: str | None = None) -> list[GameOdds]:
    """Fetch + parse current NFL odds. Raises RuntimeError with guidance if no key."""
    key = api_key or get_api_key()
    if not key:
        raise RuntimeError("ODDS_API_KEY not set — see .env.example. Never commit the key.")
    qs = urllib.parse.urlencode({
        "apiKey": key, "regions": "us", "markets": "spreads,totals,h2h", "oddsFormat": "american",
    })
    req = urllib.request.Request(f"{_API}?{qs}", headers={"User-Agent": "nfl-betting/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # `from None` drops the chained HTTPError, whose .url carries the key.
        hint = " — check that ODDS_API_KEY is valid and active" if e.code in (401, 403) else ""
        raise RuntimeError(f"The Odds API returned HTTP {e.code}{hint}.") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach The Odds API: {e.reason}") from None
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/raw/odds_api_latest.json").write_text(json.dumps(payload), encoding="utf-8")
    return parse_odds_payload(payload)


def _main() -> int:
    from datetime import UTC, datetime

    from engine.db import connect, init_schema
    from ingestion.live_odds_store import store_snapshot

    try:
        games = fetch_odds()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 1
    conn = connect("data/db/nfl_betting.sqlite")
    init_schema(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    n = store_snapshot(conn, games, captured_at=now)
    conn.close()
    print(f"Fetched {len(games)} games; stored {n} consensus snapshots at {now}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
