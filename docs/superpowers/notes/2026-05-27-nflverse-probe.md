# nflverse import_schedules probe — 2026-05-27

**Source:** `nfl_data_py.import_schedules([2020,2021,2022,2023,2024])`

**nfl-data-py version:** 0.3.2

**Total rows:** 1408

**ML columns found:** `home_moneyline`, `away_moneyline` (exact names — no variants needed)

## Coverage by season

| season | rows | home_ml_non_null | away_ml_non_null | home_ml % | away_ml % |
|--------|------|-----------------|-----------------|-----------|-----------|
| 2020   | 269  | 269             | 269             | 100%      | 100%      |
| 2021   | 285  | 285             | 285             | 100%      | 100%      |
| 2022   | 284  | 284             | 284             | 100%      | 100%      |
| 2023   | 285  | 285             | 285             | 100%      | 100%      |
| 2024   | 285  | 285             | 285             | 100%      | 100%      |

**Verdict: 100% ML coverage across all 5 seasons (1408/1408 rows non-null for both sides).**

## Team abbreviation codes seen (2024 season, 32 teams)

```
['ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN',
 'DET', 'GB',  'HOU', 'IND', 'JAX', 'KC',  'LA',  'LAC', 'LV',  'MIA',
 'MIN', 'NE',  'NO',  'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF',  'TB',
 'TEN', 'WAS']
```

Notes for T3 (team_codes.py):
- Rams = `LA` (not `LAR`)
- Raiders = `LV` (moved from OAK in 2020; historical seasons pre-2020 would show `OAK`)
- Chargers = `LAC`
- Washington = `WAS` (not `WSH` or `WFT`)
- Jaguars = `JAX` (not `JAC`)

## Full column list (46 total)

```
game_id, season, game_type, week, gameday, weekday, gametime,
away_team, away_score, home_team, home_score, location, result, total, overtime,
old_game_id, gsis, nfl_detail_id, pfr, pff, espn, ftn,
away_rest, home_rest,
away_moneyline, home_moneyline,
spread_line, away_spread_odds, home_spread_odds,
total_line, under_odds, over_odds,
div_game, roof, surface, temp, wind,
away_qb_id, home_qb_id, away_qb_name, home_qb_name,
away_coach, home_coach, referee, stadium_id, stadium
```

## Betting-relevant columns (useful for later tasks)

| column            | description                                          | sample values        |
|-------------------|------------------------------------------------------|----------------------|
| `home_moneyline`  | Closing ML price for home team (American odds)       | -423.0, -112.0       |
| `away_moneyline`  | Closing ML price for away team (American odds)       | 349.0, 102.0         |
| `spread_line`     | Closing spread from home team perspective (negative = home fav) | 9.5, 1.0, -7.0 |
| `away_spread_odds`| Juice on the away spread (usually -105 to -115)      | -105.0               |
| `home_spread_odds`| Juice on the home spread                             | -105.0               |
| `total_line`      | Closing over/under total                             | 53.5, 49.5, 47.0     |
| `over_odds`       | Juice on the over                                    | -102.0, -112.0       |
| `under_odds`      | Juice on the under                                   | -109.0, 100.0        |
| `result`          | Final margin (home_score - away_score)               | 14.0, -13.0, 32.0    |
| `total`           | Actual combined score                                | 54.0, 63.0, 44.0     |
| `overtime`        | 1 if OT, 0 otherwise                                | 0.0, 1.0             |
| `div_game`        | 1 if divisional matchup                             | 0, 1                 |
| `roof`            | dome / outdoors / retractable                       | "dome", "outdoors"   |
| `surface`         | grass / fieldturf / etc.                            | "grass", "fieldturf" |
| `temp`            | Game-time temperature (F)                           | 72.0, NaN (dome)     |
| `wind`            | Wind speed (mph)                                    | 8.0, NaN (dome)      |
| `away_rest`       | Days rest for away team                             | 7, 14                |
| `home_rest`       | Days rest for home team                             | 7, 14                |

## Key notes for downstream tasks

- **T4 column constants:** use `home_moneyline` and `away_moneyline` exactly.
- **T3 team codes:** the 32 codes above are the canonical nflverse abbreviations. Note `LA` for Rams, `LV` for Raiders (post-2020 move), `JAX` not `JAC`, `WAS` not `WSH`.
- **spread_line sign convention:** positive = home is underdog, negative = home is favorite (opposite of some other sources). E.g., `spread_line = 9.5` means home team is a 9.5-point dog.
- `result = home_score - away_score` (so positive = home win margin).
- `game_type` distinguishes REG / WC / DIV / CON / SB — filter to `REG` for regular-season-only analysis.

## Decision

**Tier 1 viable.** nfl_data_py v0.3.2 returns 100% ML coverage for 2020–2024 (1408 games, 0 nulls). Both `home_moneyline` and `away_moneyline` columns present with closing American-odds integer-like float values. Install is clean on Windows (no pyarrow dependency — uses fastparquet instead). Proceed with T2–T12.
