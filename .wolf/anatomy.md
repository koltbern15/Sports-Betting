# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-06-13T22:03:19.370Z
> Files: 23 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.gitignore` — Git ignore rules (~322 tok)
- `pyproject.toml` — NFL historical betting analytics engine (Slice 1: ingestion + ATS) (~262 tok)
- `README.md` — Project documentation (~4581 tok)

## .claude/


## .claude/rules/


## .pytest_cache/


## .pytest_cache/v/cache/


## .ruff_cache/


## .ruff_cache/0.15.14/


## .streamlit/


## .superpowers/brainstorm/965-1780189118/content/


## .venv/


## .venv/Lib/site-packages/


## .venv/Lib/site-packages/_pytest/


## .venv/Lib/site-packages/_pytest/_code/


## .venv/Lib/site-packages/_pytest/_io/


## .venv/Lib/site-packages/_pytest/_py/


## .venv/Lib/site-packages/_pytest/assertion/


## .venv/Lib/site-packages/_pytest/config/


## .venv/Lib/site-packages/_pytest/mark/


## .venv/Lib/site-packages/appdirs-1.4.4.dist-info/


## .venv/Lib/site-packages/colorama-0.4.6.dist-info/


## .venv/Lib/site-packages/colorama-0.4.6.dist-info/licenses/


## .venv/Lib/site-packages/colorama/


## .venv/Lib/site-packages/colorama/tests/


## .venv/Lib/site-packages/cramjam-2.11.0.dist-info/


## .venv/Lib/site-packages/cramjam-2.11.0.dist-info/licenses/


## .venv/Lib/site-packages/cramjam/


## .venv/Lib/site-packages/dateutil/


## .venv/Lib/site-packages/dateutil/parser/


## .venv/Lib/site-packages/dateutil/tz/


## .venv/Lib/site-packages/dateutil/zoneinfo/


## .venv/Lib/site-packages/et_xmlfile-2.0.0.dist-info/


## .venv/Lib/site-packages/et_xmlfile/


## .venv/Lib/site-packages/fastparquet-2026.5.0.dist-info/


## .venv/Lib/site-packages/fastparquet-2026.5.0.dist-info/licenses/


## .venv/Lib/site-packages/fastparquet/


## .venv/Lib/site-packages/fastparquet/parquet_thrift/


## .venv/Lib/site-packages/fastparquet/parquet_thrift/parquet/


## .venv/Lib/site-packages/fsspec-2026.4.0.dist-info/


## .venv/Lib/site-packages/fsspec-2026.4.0.dist-info/licenses/


## .venv/Lib/site-packages/fsspec/


## .venv/Lib/site-packages/fsspec/implementations/


## .venv/Lib/site-packages/fsspec/tests/abstract/


## .venv/Lib/site-packages/iniconfig-2.3.0.dist-info/


## .venv/Lib/site-packages/iniconfig-2.3.0.dist-info/licenses/


## .venv/Lib/site-packages/iniconfig/


## .venv/Lib/site-packages/lxml-6.1.1.dist-info/


## .venv/Lib/site-packages/lxml-6.1.1.dist-info/licenses/


## .venv/Lib/site-packages/lxml/


## .venv/Lib/site-packages/lxml/html/


## .venv/Lib/site-packages/lxml/includes/


## .venv/Lib/site-packages/lxml/includes/extlibs/


## .venv/Lib/site-packages/lxml/includes/libexslt/


## .venv/Lib/site-packages/lxml/includes/libxml/


## .venv/Lib/site-packages/lxml/includes/libxslt/


## .venv/Lib/site-packages/lxml/isoschematron/


## .venv/Lib/site-packages/lxml/isoschematron/resources/rng/


## .venv/Lib/site-packages/lxml/isoschematron/resources/xsl/


## .venv/Lib/site-packages/lxml/isoschematron/resources/xsl/iso-schematron-xslt1/


## .venv/Lib/site-packages/nfl_data_py-0.3.2.dist-info/


## .venv/Lib/site-packages/nfl_data_py/


## .venv/Lib/site-packages/numpy/


## .venv/Lib/site-packages/numpy/_core/


## app/

- `charts.py` — Altair chart builders for the dashboard (refined-dark friendly). (~755 tok)
- `data.py` — Cached data-access layer for the dashboard. Thin wrappers over engine functions (~1546 tok)
- `tab_clv.py` — CLV Explorer — interactive: filter by market + season range, re-bucket live. (~434 tok)
- `tab_finding.py` — The Finding — narrative hero: the CLV signal, with the open-vs-close proof panel. (~919 tok)
- `this_week_view.py` — Render the This Week board (thin view over engine.this_week.build_board). (~968 tok)

## data/raw/


## docs/superpowers/plans/


## docs/superpowers/specs/


## engine/

- `clv.py` — Closing-line value (CLV) engine. (~3322 tok)

## ingestion/

- `live_odds.py` — The Odds API client for live NFL odds. (~2153 tok)
- `loader.py` — CSV → SQLite loader for NFL betting data. (~3304 tok)
- `opening_line_sbr.py` — Parse SportsbookReviewsOnline (SBR) NFL season odds pages into records. (~3390 tok)

## scripts/

- `build_board_artifact.py` — Build the self-contained 'This Week' odds-board HTML from the latest odds snapshot. (~3346 tok)

## tests/

- `test_ats.py` — test_bucket_spread_known_values, test_bucket_spread_none_returns_none, test_metrics_basic_case, test (~1995 tok)
- `test_live_odds.py` — Tests for ingestion.live_odds — parse a saved Odds API payload (no network). (~1892 tok)
- `test_loader.py` — Columns the loader reads, in the same order as the real Kaggle CSV. (~1950 tok)
- `test_moneyline.py` — Tests for engine.moneyline. (~2758 tok)
- `test_opening_line_aus.py` — Tests for ingestion.opening_line_aus — parse the xlsx fixture. (~1228 tok)
- `test_opening_line_common.py` — Tests for ingestion.opening_line_common — pure record + normalization helpers. (~707 tok)
- `test_opening_line_sbr.py` — Tests for ingestion.opening_line_sbr — parse the SBR HTML fixture (offline). (~1711 tok)
- `test_this_week_view.py` — Tests for app.this_week_view team-filter helpers (pure, no Streamlit). (~805 tok)
- `test_validation.py` — Tests for engine.validation — pure helpers. (~2016 tok)

## tests/fixtures/

- `moneyline_tie.csv` (~152 tok)
