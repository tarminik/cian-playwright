# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cian-parser** — a Playwright-based web scraper for Cian.ru real estate listings. Supports flats, suburban properties, and new construction. Published as `cian-parser` on PyPI (v2.0.0). Python >=3.9.

## Commands

```bash
# Install in development mode
pip install -e ".[dev]"
playwright install chromium

# Run all tests
pytest tests/

# Run only live end-to-end tests (hit real Cian.ru)
pytest -m live

# Run slow tests (detail page parsing)
pytest -m slow

# Run a specific test class or test
pytest tests/test_e2e.py::TestFlatSale
pytest tests/test_url_builder.py::test_metro_station -v

# Run unit tests only (no network)
pytest tests/ -m "not live"
```

## Architecture

### Data Flow

`CianParser` (entry point) → validates inputs → `URLBuilder` constructs search URL → instantiates a `ListParser` with `BrowserManager` → paginate & extract cards → optionally parse detail pages → merge, deduplicate, return `list[dict]`.

### Parser Hierarchy

- `BaseListParser` (abstract, in `base_list.py`) — shared pagination, retry (3 attempts, 5/10/15s backoff), CAPTCHA detection, deduplication by URL ID, lazy-load scrolling
  - `FlatListParser` / `SuburbanListParser` — extend base with property-specific card extraction
- `NewObjectListParser` — **independent implementation**, does not inherit from `BaseListParser` (different card structure)
- Each property type has a separate `DetailParser` class for optional detail-page enrichment

### Key Modules

| Module | Responsibility |
|---|---|
| `parser.py` | Public API: `CianParser` context manager, `list_locations()`, `list_metro_stations()`, `list_districts()` |
| `browser.py` | `BrowserManager` — Playwright lifecycle, stealth plugin, proxy, Russian locale/timezone |
| `url_builder.py` | `URLBuilder` — filter-to-URL translation (rooms, price, floor, metro, district, etc.) |
| `helpers.py` | DOM data extraction functions (price, specs, location, author) |
| `constants.py` | Cities (150+), districts (Moscow/SPb), metro stations (6 systems), URL templates, regex patterns, deal-type field mappings |
| `csv_saver.py` | Semicolon-delimited UTF-8 CSV export |
| `exceptions.py` | `CaptchaError` (preserves partial results), `LocationNotFoundError`, `BrowserNotInstalledError` |

### Property Types

Three parsing paths in `src/cian_parser/`: `flat/`, `suburban/`, `newobject/` — each with `list_parser.py` and `page_parser.py`.

### Deal Types

`sale`, `rent_long` (4+ weeks), `rent_short` (daily). Each deal type has different output fields defined in `constants.py`.

## Dependencies

- **Runtime:** `playwright>=1.40`, `playwright-stealth>=2.0`
- **Dev:** `pytest`
- **Build:** `setuptools>=64`, `wheel`

## Testing

- `test_e2e.py` — live integration tests against Cian.ru (marked `live`; detail-page tests also marked `slow`)
- `test_e2e_isolated.py` — integration tests without real network (exception handling, CAPTCHA propagation)
- `test_url_builder.py`, `test_helpers.py`, `test_validators.py`, `test_exceptions.py`, `test_constants.py` — unit tests
- Shared browser fixture in `conftest.py` for test session reuse
- CAPTCHA can interrupt live tests; partial results are preserved via `CaptchaError`

## Key Design Decisions

- **Stealth plugin** to avoid Cian.ru bot detection
- **Detail page parsing is optional** (`additional_data=True`) — trades speed for completeness
- **CAPTCHA resilience** — `CaptchaError` carries collected data so callers can use partial results
- **Deduplication** by listing URL ID across paginated pages
- **Semicolon CSV delimiter** — standard for European locale spreadsheets
