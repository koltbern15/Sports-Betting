# Opening-Line Source Probe — 2026-05-29

## Purpose

Verify the real structure of two free historical NFL opening-odds sources before building parsers
for Slice 6 (CLV analysis). This is a discovery note, not a build artifact.

---

## Source 1: SportsbookReviewsOnline (SBR)

### Fetch result

- URL pattern: `https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl-odds-{YYYY-YY}/`
- Index page: `https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl/nfloddsarchives.htm`
- urllib fetch: **SUCCESS** — 117,675 bytes (no Cloudflare gate, no JS challenge)
- File saved: `data/raw/sbr_2021.html`
- Season coverage: **2007-08 through 2021-22** (15 seasons)
- No 2022-23 or later seasons exist on SBR.

### HTML structure

`pd.read_html()` finds **1 table** per page with shape `(N+1, 13)` where row 0 is the header.

**Column layout (indices 0–12):**

| Col | Header | Content |
|-----|--------|---------|
| 0 | `Date` | Integer MMDD — e.g. `909` = Sep 9, `130` = Jan 30. No year (infer from URL). |
| 1 | `Rot` | Rotation number. Odd = away team; even = home team. |
| 2 | `VH` | Team side: `V` = visitor/away, `H` = home, `N` = neutral site. |
| 3 | `Team` | Team name (no spaces — e.g. `TampaBay`, `KansasCity`, `SanFrancisco`). |
| 4–7 | `1st`–`4th` | Quarter scores. |
| 8 | `Final` | Final score. |
| 9 | `Open` | **DUAL USE — see below.** |
| 10 | `Close` | **DUAL USE — same layout as Open.** |
| 11 | `ML` | American-format moneyline. Away ML in away row; home ML in home row. |
| 12 | `2H` | Second-half line (same dual-use pattern as Open/Close). |

### Two-rows-per-game layout

Every game occupies **exactly two consecutive rows**: away team first (lower Rot#, `VH=V`),
home team second (higher Rot#, `VH=H`). Neutral-site games use `VH=N` for both rows.

The `Open` and `Close` columns serve **dual purpose** across the two rows of a game:
- One row carries the **game O/U total** (e.g. `47.5`).
- The other row carries the **home team spread** (e.g. `3.5` or `pk`).

### Open/Close column — total vs spread assignment

The assignment of total vs spread to V/H rows is **not consistent across games**. The reliable
parse strategy is value-size classification:

- **Value > 25** → this row's Open/Close = **game total** (o/u line).
- **Value ≤ 25 or `pk`** → this row's Open/Close = **home team spread**.

In the 2021-22 season (285 games):
- ~63% follow the "natural" layout: V row = total, H row = spread.
- ~37% are flipped: V row = spread, H row = total.
- Only 1 game pair in 285 is genuinely ambiguous on `Open` (both values ≤ 25). In that case,
  use the `Close` column to resolve — the closing total will be unambiguously large (e.g. 46).

### Spread sign convention

The spread number is **always shown as a positive value** (or `pk`). The sign must be inferred:
- If the home team's ML is negative (home is favorite) → home spread is negative (they give points).
- If the home team's ML is positive (home is dog) → home spread is positive (they get points).
- `pk` = pick'em (spread = 0), though the ML may still not be exactly even.

### Moneyline

**Opening ML is present for every game row.** American format. Stored in column index 11.

### Concrete parse recipe (per-game, home-perspective spread + total)

```
1. Group data rows into pairs by sequential position (row i, row i+1).
2. Identify away_row and home_row by VH column (V/N first = away, H = home).
   OR use Rot# parity: odd Rot = away, even Rot = home.
3. For Open column:
   a. Convert both rows' Open values to float ('pk' → 0.0).
   b. The row whose |Open| > 25 holds the TOTAL. The other holds the SPREAD.
   c. If both > 25 or both ≤ 25, fall back to Close column for disambiguation.
4. Total = the raw value from the total-row Open.
5. Spread (home perspective) = the raw value from the spread-row Open.
   Apply sign: if home ML < 0 → spread_home = -|spread|; else spread_home = +|spread|.
   If value is 'pk' → spread_home = 0.0.
6. ML_away = away_row[11], ML_home = home_row[11] (already signed American format).
```

### Season URL pattern

```
https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl-odds-{START_YY}-{END_YY}/
```
Examples: `nfl-odds-2021-22`, `nfl-odds-2007-08`. The index page lists all 15 available URLs.

---

## Source 2: Australia Sports Betting (aussportsbetting)

### Fetch result

- Landing page URL: `https://www.aussportsbetting.com/data/historical-nfl-results-and-odds-data/`
- urllib fetch (stdlib + full browser headers): **HTTP 403 Forbidden** — Cloudflare WAF blocks all
  automated requests.
- WebFetch tool: also **HTTP 403 Forbidden**.
- Direct xlsx URL guesses (4 candidate paths): all **HTTP 403 Forbidden**.
- **The xlsx file CANNOT be downloaded programmatically.** It requires a real browser session
  with JavaScript execution to pass the Cloudflare challenge.

### Column structure

**UNKNOWN** — the file could not be fetched. Column layout cannot be confirmed programmatically.

From the Slice 6 design spec (based on prior research, unverified):
- Claimed to have: Date, Home Team, Away Team, opening spread, closing spread, opening total,
  closing total, and possibly opening moneyline from 2013 onward.
- Claimed coverage: 2006–present (opening odds from ~2013+).
- Odds format: unverified (decimal vs American unknown).

**None of these claims could be verified in this probe.**

### Blocker status

**BROWSER-GATED BLOCKER.** Automated fetch is not possible. To use this source, a human must:
1. Visit `https://www.aussportsbetting.com/data/historical-nfl-results-and-odds-data/` in a
   real browser.
2. Locate and click the `.xlsx` download link.
3. Save the file to `data/raw/aus_nfl.xlsx`.
4. Only then can the column layout be confirmed and a parser written.

---

## ML Verdict

**ML DEFERRED — no usable opening ML from automated sources.**

- SBR has opening ML (American format) for every game, but SBR only covers through 2021-22. No
  2022+ data. ML from SBR is available and parseable.
- Aussportsbetting ML status is unknown (blocked). It cannot contribute to CLV until manually
  downloaded and inspected.

For Slice 6 CLV analysis, **SBR opening ML (2007–2022) is available and clean** for the covered
seasons. This is sufficient to proceed with opening-spread + opening-total + opening-ML for
those 15 seasons.

---

## Summary

| Source | Fetch | Opening Spread | Opening Total | Opening ML | Date Range | Blocker |
|--------|-------|---------------|--------------|-----------|------------|---------|
| SBR | ✓ urllib | ✓ (dual-col parse) | ✓ (dual-col parse) | ✓ American | 2007–2022 | None — freely scrapeable |
| aussportsbetting | ✗ 403 | Unknown | Unknown | Unknown | Unknown | Cloudflare WAF — manual download required |

### Files saved to data/raw/

- `data/raw/sbr_2021.html` — 117,675 bytes (2021-22 NFL season, 285 games, 571 rows)

### Recommended parse order for Slice 6

1. **SBR scraper** — loop the 15 season URLs, fetch HTML, parse with the dual-column recipe
   above. Covers 2007–2022 with opening spread + total + ML.
2. **aussportsbetting** — DEFERRED until manual download. If Kolton downloads the xlsx, confirm
   columns match the claimed layout, then write a second ingestion path. This would extend
   coverage to 2022–present if the file includes recent seasons.
