# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cian-playwright** — a Python >=3.9 Playwright library for Cian.ru flats, suburban properties, and new construction. The import package is `cian_parser`; authoritative metadata is in `pyproject.toml`.

## Commands

```bash
# Install in development mode
pip install -e ".[dev]"
playwright install chromium

# Run all tests
pytest tests/

# Run only live end-to-end tests (hit real Cian.ru)
pytest -m live
pytest -m live --headed  # Requires a display; useful when Cian rejects headless traffic

# Run slow tests (detail page parsing)
pytest -m slow

# Run a specific test class or test
pytest tests/test_e2e.py::TestFlatSale
pytest tests/test_url_builder.py::test_additional_settings_metro -v

# Run offline tests (some use Chromium with local HTML/intercepted requests)
pytest tests/ -m "not live"
```

## Architecture

### Data Flow

`CianParser` (entry point) → validates inputs → `URLBuilder` constructs search URL → instantiates a `ListParser` with `BrowserManager` → paginate & extract cards → optionally parse detail pages → merge, deduplicate, return `list[dict]`.

### Parser Hierarchy

- `BaseListParser` — shared pagination, retry (3 attempts with 5/10s waits), CAPTCHA partial results, deduplication, and CSV commit ordering.
  - `FlatListParser`, `SuburbanListParser`, and `NewObjectListParser` specialize card extraction and record keys.
- Each property type has a separate detail parser. `page_utils.py` shares guarded navigation, CAPTCHA detection, and cleanup. Newobject collection always includes details; flat/suburban enrichment is optional.

### Key Modules

| Module | Responsibility |
|---|---|
| `parser.py` | Public API: `CianParser` context manager, `list_locations()`, `list_metro_stations()`, `list_districts()` |
| `browser.py` | `BrowserManager` — Playwright lifecycle, owned-context cleanup, stealth, proxy, Russian locale/timezone |
| `url_builder.py` | `URLBuilder` — filter-to-URL translation (rooms, price, floor, metro, district, etc.) |
| `helpers.py` | DOM data extraction functions (price, specs, location, author) |
| `constants.py` | Cities, districts (Moscow/SPb), metro systems, URL templates, deal-type field mappings |
| `page_utils.py` | Detail-page checks, CAPTCHA detection, contact extraction, safe page cleanup |
| `short_rent.py` | Daily rental map cards, asynchronous readiness, button pagination and retry state |
| `csv_saver.py` | Atomic semicolon-delimited UTF-8 CSV export |
| `exceptions.py` | `CaptchaError` (preserves partial results), `LocationNotFoundError`, `BrowserNotInstalledError` |

### Property Types

Three parsing paths in `src/cian_parser/`: `flat/`, `suburban/`, `newobject/` — each with `list_parser.py` and `page_parser.py`.

### Deal Types

`sale`, `rent_long` (4+ weeks), `rent_short` (daily). Each deal type has different output fields defined in `constants.py`.

## Dependencies

- **Runtime:** `playwright>=1.40`, `playwright-stealth>=2.0`
- **Dev:** `pytest`
- **Build:** `setuptools>=77`, `wheel`

## Testing

- `test_e2e.py` — live integration tests against Cian.ru (marked `live`; detail-page tests also marked `slow`)
- `test_e2e_isolated.py` — live tests using separate browser instances; still requires network
- `test_parser_integration.py` — public API integration tests with real Chromium and intercepted HTTP responses
- `test_collection_integrity.py`, `test_extraction.py`, `test_browser.py`, `test_csv_saver.py`, `test_api_contract.py` — regression tests for collection, extraction, cleanup, persistence, and validation
- `test_url_builder.py`, `test_helpers.py`, `test_validators.py`, `test_exceptions.py`, `test_constants.py` — unit tests
- Shared browser fixture in `conftest.py` for module-level reuse; `--headed` affects live tests
- CAPTCHA can interrupt live tests; partial results are preserved via `CaptchaError`

## Key Design Decisions

- **Stealth plugin** is applied to pages; site access can still be denied with HTTP 403
- **Detail page parsing is optional** (`with_extra_data=True` for flats/suburban) — trades speed for completeness
- **CAPTCHA resilience** — `CaptchaError` carries collected data so callers can use partial results
- **Deduplication** by listing ID or full newobject project URL, ignoring tracking parameters
- **Failures are explicit** — exhausted retries and missing page layouts must not return apparently complete data
- **Bounded requests** — use `additional_settings` with `start_page`/`end_page`; newobjects accept only these settings
- **Daily search isolation** — each daily list collection owns a fresh browser context; release it through `BrowserManager.close_page()` to avoid stale search state and context leaks
- **Semicolon CSV delimiter** — standard for European locale spreadsheets
