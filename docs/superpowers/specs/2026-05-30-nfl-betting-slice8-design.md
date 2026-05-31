# NFL Betting Analytics — Slice 8: Live "This Week" Odds Board

**Date:** 2026-05-30
**Status:** Approved (brainstorming complete)
**Predecessor:** Slice 7 (`docs/superpowers/specs/2026-05-30-nfl-betting-slice7-design.md`)
**Successor (planned):** Slice 9 — historical showcase tabs (The Finding / Edge Report / CLV Explorer / Data & Audit) plugged into the same app.

---

## Why this slice

The user wants to use the project's data against *current* odds to bet smarter. The honest version of that — given everything Slices 4–7 proved — is **not** a winner-predictor (static historical buckets aren't a certified edge; CLV isn't knowable until the close). It is:

1. **Line shopping** — show the best available price per side across sportsbooks. This is a *real, legitimate edge*: when you do bet, take the best number on the board.
2. **Live line movement** — opening (our first weekly snapshot) → current, grounded in the Slice 7 finding that the close is sharper than the open.
3. **Historical context** — the historical rate of the bucket each current line falls into, explicitly labeled *not a certified edge*.

This slice is **live-first** per the user's pivot: the "This Week" board is the deliverable; the historical showcase tabs are deferred to Slice 9 (they plug into the same Streamlit app).

## Goal

Pull current NFL odds for upcoming games from The Odds API, store weekly snapshots, and present each game in a refined-dark Streamlit "This Week" board: best price per side (line shopping), line movement since our first snapshot, and historical bucket context — honestly framed as context + best price, not certified picks.

## Markets

Spread, total, and moneyline for upcoming NFL games.

## Out of scope (deferred)

- The historical showcase tabs (Slice 9): The Finding, Edge Report, CLV Explorer, Data & Audit.
- Any "best bet"/+EV ranking that implies a predictive edge (forbidden by our own findings — see Honesty rails).
- Paid Odds API historical tier / retroactive openers (free tier captures openers going forward only).
- Hosting/deployment (local `streamlit run`); auth; bet tracking/bankroll.
- ML-CLV historical analysis (separate future slice).

---

## Secret handling (API key)

The Odds API key is read from the **`ODDS_API_KEY` environment variable** — never committed, never in source, never in the transcript. Mechanism:

- Code resolves the key via `os.getenv("ODDS_API_KEY")`. If absent, also load a gitignored project-root `.env` (tiny stdlib parser: `KEY=value` lines) so the user can persist it locally without exporting each shell.
- A committed **`.env.example`** documents the variable (no real value).
- `.gitignore` gains `.env` and `.streamlit/secrets.toml`.
- If the key is missing at runtime, the CLI and the app show a clear "set ODDS_API_KEY (see .env.example)" message — they do not crash or log the key.

---

## Architecture

**Additive.** Reuses the existing engine/ingestion where it helps (team-name normalization, the historical bucket helpers). New live-odds path + a new `app/` Streamlit package.

### Components

| File | Responsibility | Lifecycle |
|---|---|---|
| `ingestion/live_odds.py` | The Odds API client: fetch upcoming NFL odds (spreads/totals/h2h) across books; normalize teams; compute consensus + best price per side; key via env. Pure parse fn + thin fetch boundary. | NEW |
| `tests/test_live_odds.py` | Parser/consensus/best-price tests against a saved sample JSON payload (no network). | NEW |
| `engine/db.py` | Add `live_odds_snapshots` table. | MODIFY |
| `tests/test_db.py` | Test the new table. | MODIFY |
| `ingestion/live_odds_store.py` | Persist a fetched snapshot into `live_odds_snapshots`; read opener (earliest) + current (latest) per game. | NEW |
| `tests/test_live_odds_store.py` | Store/read tests vs in-memory DB. | NEW |
| `engine/this_week.py` | Board builder: per upcoming game assemble current consensus, best price + book, movement vs first snapshot, historical-bucket context. Returns `ThisWeekGame` records. Pure over inputs → testable. | NEW |
| `tests/test_this_week.py` | Board-builder tests on synthetic snapshots + historical context. | NEW |
| `app/this_week_view.py` | Streamlit refined-dark render of the board (per-game cards, movement, context, honesty banner). | NEW |
| `app/theme.py` | Refined-dark CSS/theme helpers. | NEW |
| `app/main.py` | Streamlit entry: page config + theme + the This Week board (tab scaffold ready for Slice 9 tabs). | NEW |
| `.streamlit/config.toml` | Refined-dark theme (bg #14161c, primary #6c8cff, etc.). | NEW |
| `.env.example` | Documents `ODDS_API_KEY`. | NEW |
| `.gitignore` | Add `.env`, `.streamlit/secrets.toml`. | MODIFY |
| `pyproject.toml` | Add `streamlit`, `altair`. | MODIFY |
| `README.md` | Slice 8 section + run instructions. | MODIFY |

The odds fetch uses stdlib `urllib` (no `requests` dep), consistent with `ingestion/opening_line_sbr.py`.

---

## Data flow

```
(weekly) ODDS_API_KEY + The Odds API  ──ingestion.live_odds.fetch──►  raw JSON (cached to data/raw/)
                                       ──parse/normalize──►  list[GameOdds] (consensus + best-price-per-side per book)
ingestion.live_odds_store.store(conn, games)  ──►  live_odds_snapshots  (one timestamped row set per run)

engine.this_week.build_board(conn, historical_ctx)
   reads snapshots: opener = earliest per game, current = latest
   ──►  list[ThisWeekGame] {matchup, commence_time, current lines, best price+book per side,
                            movement(open→now) per market, historical bucket context, biggest-mover flag}

app/main.py (streamlit) ──► renders the board (refined-dark)
```

- **Opener capture:** the earliest snapshot we hold for a game is treated as its "open." On the free tier this means live movement is meaningful only from the first weekly run forward — documented in the UI ("movement since first captured").
- **Best price:** per side, the most favorable American odds across the returned books, with the book name.
- **Consensus:** median line across books (home-perspective spread; total; ML).
- **Historical context:** map each current line to its historical bucket (reuse the existing bucket logic — `engine.ats`/`totals` bucketers and the historical per-bucket rates) and show that bucket's historical win rate, **labeled uncertified** with its caveat.

---

## The board UI (refined-dark)

A single "This Week" view (Slice 9 adds sibling tabs). For each upcoming game, a card:
- Matchup + kickoff time.
- **Best price** per side (spread/total/ML) with the offering book highlighted — the headline, actionable, honest value.
- **Consensus** line for reference.
- **Movement** arrow: opener → current per market (e.g. "home −3 → −4.5, moved 1.5 toward home"). Labeled "since first captured."
- **Historical context** line: "home favorites in this range historically covered X% (n=…, not a certified edge)."
- Persistent **honesty banner** at the top of the board.
- A "biggest moves this week" strip (sorted by absolute movement — descriptive, not an edge claim).

If there are no upcoming games (offseason) or no snapshots yet, the board shows a friendly empty state explaining how to pull odds.

---

## Honesty rails (non-negotiable)

Given Slices 4–7, the board must not imply a predictive edge:
- Top banner: *"Context and best prices — not certified picks. Historical rates are not a proven edge (the market is efficient — see the CLV finding). The real edge here is line shopping: take the best price. Past performance ≠ future results. Gamble responsibly."*
- Historical context always carries its sample size + "not certified."
- Games are ranked/sorted by **line movement magnitude** (descriptive), never by a fabricated "edge" or "value" score.
- No language that frames a game as a recommended bet.

---

## Error handling

- Missing `ODDS_API_KEY` → CLI/app print a clear "set ODDS_API_KEY (see .env.example)" message; exit cleanly; never echo the key.
- The Odds API error / rate limit / network failure → caught, surfaced as a friendly message; last stored snapshot still renders.
- Offseason / no upcoming games → empty-state message, not an error.
- Unknown team name from the API → normalized via `team_names`; an unmapped name is skipped-and-counted (logged), not fatal.
- All file I/O `pathlib` + utf-8; raw API responses cached under `data/raw/` (gitignored).

---

## Testing

- **`tests/test_live_odds.py`** — parse a saved sample The Odds API JSON payload (committed small fixture): correct team normalization, home-perspective spread sign, consensus = median, best-price-per-side selects the most favorable book. No live network in tests.
- **`tests/test_live_odds_store.py`** — store a snapshot to an in-memory DB; opener=earliest, current=latest per game; idempotency of a re-store within a run.
- **`tests/test_this_week.py`** — board builder on synthetic snapshots: movement computed correctly per market, historical context joined, biggest-mover flag, empty-state.
- **`tests/test_db.py`** — `live_odds_snapshots` table created/idempotent.
- **Streamlit `AppTest` smoke test** — the app boots and the board renders without error using a seeded DB (no live calls).
- After it runs end-to-end with a real key + a real pull, **`openwolf designqc`** screenshots the board to iterate on polish (the "make it great" bar).
- Full suite stays green; ruff clean. Target ~312 baseline + new tests.

---

## Definition of Done

- [ ] `ingestion/live_odds.py` fetches + normalizes upcoming NFL odds; key via `ODDS_API_KEY`; consensus + best-price-per-side; fixture-tested
- [ ] `live_odds_snapshots` table + store/read (`ingestion/live_odds_store.py`); opener=earliest, current=latest
- [ ] `engine/this_week.py` builds `ThisWeekGame` records (current, best price, movement, historical context, biggest movers)
- [ ] Refined-dark Streamlit board (`app/`) renders the This Week view with the honesty banner; `streamlit run app/main.py` works
- [ ] Secret handling: env var + `.env` (gitignored) + `.env.example`; missing-key message; key never committed/logged
- [ ] `streamlit` + `altair` added; `urllib`-based fetch (no `requests`)
- [ ] Tests: live_odds parse (fixture), store, this_week builder, db table, AppTest smoke — all green; ruff clean
- [ ] End-to-end pull with a real key produces a live board; `openwolf designqc` pass for polish
- [ ] README Slice 8 section (setup: get key, set env, pull, run); Scope bullet
- [ ] `.wolf/memory.md` + `.wolf/cerebrum.md` entries

---

## Decisions log (this slice)

- **Live-first pivot:** the live This Week board is the priority deliverable; historical showcase tabs deferred to Slice 9 (same app).
- **"Best odds" = line shopping:** the one honest, real edge — best available price per side across books. Directly serves the user's "find the best odds" goal without implying a winner-predictor.
- **Honesty rails are mandatory:** no predictive-edge framing; historical context labeled uncertified; sort by line movement, not by a fake edge score. Consistent with Slices 4–7.
- **Opener via our own weekly snapshot:** free-tier-compatible; live movement is meaningful from first capture forward (documented in UI).
- **Secret hygiene:** `ODDS_API_KEY` env var + gitignored `.env`; never in source/transcript/repo.
- **Refined-dark + Streamlit + Altair + urllib fetch:** matches the approved look; minimal new deps.
- **Vertical slice (ingestion → store → builder → UI):** delivers a usable tool now; data layers are pure/testable, UI is thin.
