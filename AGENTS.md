# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.12+ library using a `src/` layout. `src/cian_parser/parser.py` exposes `CianParser`; `browser.py` manages Playwright, `url_builder.py` constructs queries, and `base_list.py` handles shared collection logic. Property-specific list and detail parsers live in `flat/`, `suburban/`, and `newobject/`. Shared extraction, constants, exceptions, and CSV export have separate modules. Tests live in `tests/`, with shared fixtures in `conftest.py`. See `README.md` for usage examples and `pyproject.toml` for dependencies and packaging.

## Build, Test, and Development Commands

Run from the repository root, preferably in a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'       # Editable package and pytest
python -m playwright install chromium # Required browser binary
python -m pytest tests/ -m 'not live'   # Tests without requests to Cian
python -m pytest tests/ -m live        # Real Cian integration tests
python -m pytest tests/test_url_builder.py -v # Focused checks
python -m pip wheel . --no-deps -w dist # Build a wheel
```

`python -m pytest tests/` includes live tests. Use the library through `from cian_parser import CianParser`; prefer its context manager to release browser resources.

## Coding Style & Naming Conventions

Follow existing Python style: four-space indentation, `snake_case` functions and modules, `PascalCase` classes, and `UPPER_SNAKE_CASE` constants. Use type annotations and `from __future__ import annotations` consistently with adjacent modules. Keep public API docstrings concise and target Python 3.12 or newer. No formatter or linter is configured; avoid unrelated formatting changes.

## Testing Guidelines

Use pytest, `test_*.py` files, `test_*` functions, and `Test*` classes. Add focused regression tests for changed behavior; use mocks or local HTML where practical. Select network tests by the `live` marker, not filenames: `test_e2e_isolated.py` also contains live tests. The non-live suite includes a Chromium-backed local HTML test. Mark expensive scenarios `slow`. Live tests require network access and may encounter CAPTCHA; report skips separately from passes. No coverage threshold is configured.

## Commit & Pull Request Guidelines

Follow the history's short imperative subjects, such as `Add support for 6-room apartments`. Keep commits focused. PRs should describe the behavior change, link related issues when applicable, and list validation commands and results, including whether live tests ran. Preserve partial results on CAPTCHA, listing deduplication, and browser cleanup when changing collection behavior. Keep generated CSV/JSON data and proxy credentials out of commits.
