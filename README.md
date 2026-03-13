# cian-parser

Playwright-based parser for [Cian.ru](https://cian.ru) real estate listings.

## Installation

```bash
pip install cian-parser
playwright install chromium
```

## Quick start

```python
from cian_parser import CianParser

with CianParser("Москва") as parser:
    # Sale
    flats = parser.get_flats(deal_type="sale", rooms=(1, 2))

    # Long-term rent
    rent = parser.get_flats(deal_type="rent_long", rooms="all")

    # Short-term rent
    daily = parser.get_flats(deal_type="rent_short")

    # Suburban
    houses = parser.get_suburban("house", deal_type="sale")

    # New construction
    newbuilds = parser.get_newobjects()
```

## API

### `CianParser(location, proxies=None)`

- **location** — city name (e.g. `"Москва"`). See `cian_parser.list_locations()` for all options.
- **proxies** — optional proxy URL string for Playwright.

### `get_flats(deal_type, rooms="all", with_saving_csv=False, with_extra_data=False, additional_settings=None)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `deal_type` | `str` | `"sale"`, `"rent_long"`, or `"rent_short"` |
| `rooms` | `int \| str \| tuple` | `1`–`5`, `"studio"`, `"all"`, or tuple like `(1, 2, "studio")` |
| `with_saving_csv` | `bool` | Save results to CSV |
| `with_extra_data` | `bool` | Parse detail pages for extra fields (slower) |
| `additional_settings` | `dict` | Filters: `min_price`, `max_price`, `metro`, `district`, `sort_by`, etc. |

### `get_suburban(suburban_type, deal_type, ...)`

Same parameters as `get_flats`, plus:

| Parameter | Type | Description |
|-----------|------|-------------|
| `suburban_type` | `str` | `"house"`, `"house-part"`, `"land-plot"`, or `"townhouse"` |

### `get_newobjects(with_saving_csv=False)`

Parse new construction listings.

### Helpers

```python
from cian_parser import list_locations, list_metro_stations, list_districts

list_locations()              # [("Москва", "1"), ("Санкт-Петербург", "2"), ...]
list_metro_stations()         # {"Москва": [("Арбатская", "1"), ...], ...}
list_districts("Москва")      # [("Арбат", "13"), ...]
```

## License

[MIT](LICENSE)
