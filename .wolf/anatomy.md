# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-05-31T05:06:35.921Z
> Files: 18 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.gitignore` — Git ignore rules (~205 tok)
- `README.md` — Project documentation (~4510 tok)

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

- `charts.py` — Altair chart builders for the dashboard (refined-dark friendly). (~561 tok)
- `data.py` — Cached data-access layer for the dashboard. Thin wrappers over engine functions (~1096 tok)
- `main.py` — NFL Betting Analytics — live This Week odds board (Streamlit entry point). (~610 tok)
- `tab_clv.py` — CLV Explorer — interactive: filter by market + season range, re-bucket live. (~289 tok)
- `tab_data.py` — Data & Audit — coverage, cross-source agreement, and data provenance. (~402 tok)
- `tab_edge.py` — Edge Report — the honest-metrics table (Slice 5): no certified static edge. (~358 tok)
- `tab_finding.py` — The Finding — narrative hero: the CLV signal, with the open-vs-close proof panel. (~600 tok)
- `theme.py` — Refined-dark CSS polish injected into the Streamlit app. (~400 tok)

## data/raw/


## docs/superpowers/plans/

- `2026-05-31-nfl-betting-slice9.md` — NFL Betting Analytics — Slice 9: Historical Showcase Tabs — Implementation Plan (~7415 tok)

## docs/superpowers/specs/

- `2026-05-31-nfl-betting-slice9-design.md` — NFL Betting Analytics — Slice 9: Historical Showcase Tabs (~2223 tok)

## engine/

- `clv.py` — Closing-line value (CLV) engine. (~3072 tok)

## ingestion/

- `live_odds.py` — The Odds API client for live NFL odds. (~2007 tok)

## tests/

- `test_app_data.py` — Tests for app.data — cached data-access loaders (logic tested without Streamlit cache). (~987 tok)
- `test_app_smoke.py` — Smoke test: the Streamlit app boots and renders without error (no live network). (~165 tok)
- `test_clv.py` — Tests for engine.clv — pure CLV math, grading, bucketing. (~2119 tok)
- `test_live_odds.py` — Tests for ingestion.live_odds — parse a saved Odds API payload (no network). (~524 tok)

## tests/fixtures/

