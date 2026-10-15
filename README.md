# cian-playwright

Playwright-based parser for [Cian.ru](https://cian.ru) real estate listings.

## Installation

Requires Python 3.12 or newer.

```bash
pip install cian-playwright
playwright install chromium
```

Install the full Chromium browser; `playwright install chromium --only-shell`
is insufficient. On Linux servers, use `playwright install --with-deps chromium`
to install the browser and its system dependencies.

## Quick start

```python
from cian_parser import CianParser

with CianParser("Москва") as parser:
    bounds = {"start_page": 1, "end_page": 1}
    # Sale
    flats = parser.get_flats(deal_type="sale", rooms=(1, 2), additional_settings=bounds)

    # Long-term rent
    rent = parser.get_flats(deal_type="rent_long", rooms="all", additional_settings=bounds)

    # Short-term rent
    daily = parser.get_flats(deal_type="rent_short", additional_settings=bounds)

    # Suburban
    houses = parser.get_suburban("house", deal_type="sale", additional_settings=bounds)

    # New construction
    newbuilds = parser.get_newobjects(additional_settings=bounds)
```

## API

### `CianParser(location, proxies=None, *, headless=True)`

- **location** — city name (e.g. `"Москва"`). See `cian_parser.list_locations()` for all options.
- **proxies** — optional proxy URL string for Playwright.
- **headless** — defaults to `True`: full Chromium runs in its unified headless
  mode, without a window, desktop, or Xvfb. Use `False` to show Chromium
  (requires a desktop/display). The library does not switch modes automatically.

### `get_flats(deal_type, rooms="all", with_saving_csv=False, with_extra_data=False, additional_settings=None)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `deal_type` | `str` | `"sale"`, `"rent_long"`, or `"rent_short"` |
| `rooms` | `int \| str \| tuple` | `1`–`6` (`6` selects six or more rooms), `"studio"`, `"all"`, or a nonempty tuple like `(1, 2, "studio")` |
| `with_saving_csv` | `bool` | Save results to CSV |
| `with_extra_data` | `bool` | Parse detail pages for extra fields (slower) |
| `additional_settings` | `dict` | Filters: `min_price`, `max_price`, `metro`, `district`, `sort_by`, etc. |

### `get_suburban(suburban_type, deal_type, with_saving_csv=False, with_extra_data=False, additional_settings=None)`

Uses the same CSV, enrichment, and filter settings as `get_flats`, without a
`rooms` argument. Select the property type with:

| Parameter | Type | Description |
|-----------|------|-------------|
| `suburban_type` | `str` | `"house"`, `"house-part"`, `"land-plot"`, or `"townhouse"` |

### `get_newobjects(with_saving_csv=False, *, additional_settings=None)`

Parse new construction listings, including their detail pages. `additional_settings`
accepts only `start_page` and `end_page`; defaults are 1 and 50.

### Filters and pagination

Flat/suburban pagination defaults to pages 1–100 and stops earlier when no next
page exists. Bounds are inclusive positive integers. Use a small `end_page` for
initial checks; detail enrichment visits each listing and takes longer.
For daily rentals, the library follows the map interface's Next button; page
bounds still apply even though the address bar does not change between pages.

```python
settings = {
    "start_page": 1, "end_page": 2,
    "min_price": 10_000_000, "max_price": 20_000_000,
    "district": "Арбат",  # Resolved within the selected city
    "metro": "Московский", "metro_station": "Арбатская",
}
```

Named districts are available for Moscow and Saint Petersburg. `district_id`
accepts an ID or a list of IDs. Other filters include `min_floor`, `max_floor`,
`min_total_floor`, `max_total_floor`, `min_house_year`, `max_house_year`,
`is_by_homeowner`, `only_flat`, `only_apartment`, and flat `object_type`
(`"secondary"` or `"new"`). Invalid known filters, room counts, bounds, and proxy
types raise `ValueError` before browsing. Unknown flat/suburban settings are
ignored for compatibility; use supported names.

### Results and failures

Methods return `list[dict]`. Flat/suburban sale records have `price`; long/short rentals have
`price_per_month`/`price_per_day`. Prices are rubles; long-rental `commissions`
is a percentage. Missing fields retain their established `-1`/empty-string
defaults; an empty phone means no complete public phone link was available.
Daily `price_per_day` can be the advertised starting rate ("от"); it is not a
quote for specific booking dates.
Studio `rooms_count` is `1` for compatibility. Detail area values retain the
site's text and units. Recommendations outside the requested search are excluded.

Collection retries failed pages up to three attempts, waiting 5 and 10 seconds.
Persistent navigation, HTTP, or parsing failures raise an exception instead of
returning an apparently complete collection. CAPTCHA raises `CaptchaError`:

```python
from cian_parser import CaptchaError

try:
    with CianParser("Москва") as parser:
        records = parser.get_flats("sale", additional_settings={"end_page": 1})
except CaptchaError as exc:
    records = exc.partial_results  # Incomplete: collected before the challenge
```

Site access can be blocked independently of parser correctness (for example,
HTTP 403). Such failures are not successful empty results. CSV exports use
UTF-8 and `;`, are written in the current directory, and are replaced atomically
after each collected record; a failed write leaves the previous export intact.

### Helpers

```python
from cian_parser import list_locations, list_metro_stations, list_districts

list_locations()              # [("Москва", "1"), ("Санкт-Петербург", "2"), ...]
list_metro_stations()         # Metro systems, e.g. "Московский", and station IDs
list_districts("Москва")      # [("Арбат", "13"), ...]
```

## Development

```bash
python3.12 -m venv .venv # Or a newer supported Python
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m pytest tests/ -m 'not live'
python -m pytest tests/ -m live
python -m pytest tests/ -m live --headed # Visible browser, when a display is available
python -m pip wheel . --no-deps -w dist
```

The non-live suite includes Chromium tests against local HTML and intercepted
requests. Live tests contact Cian and may skip on CAPTCHA; skips do not prove
successful collection. CI runs offline tests and wheel checks on Python
3.12–3.15. `pytest tests/` includes both suites.

## License

[MIT](LICENSE)
