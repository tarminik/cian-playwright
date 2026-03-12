from __future__ import annotations

import logging
from typing import Any

from cian_parser.browser import BrowserManager
from cian_parser.constants import CITIES, METRO_STATIONS, DISTRICTS, DEAL_TYPES, OBJECT_SUBURBAN_TYPES
from cian_parser.exceptions import LocationNotFoundError
from cian_parser.flat.list_parser import FlatListParser
from cian_parser.newobject.list_parser import NewObjectListParser
from cian_parser.suburban.list_parser import SuburbanListParser
from cian_parser.url_builder import URLBuilder

logger = logging.getLogger("cian_parser")


def list_locations() -> list[tuple[str, str]]:
    """Return list of available locations as (name, id) tuples."""
    return [(city[0], city[1]) for city in CITIES]


def list_metro_stations() -> dict:
    """Return dict of metro systems with their stations."""
    return METRO_STATIONS


def list_districts(location: str) -> list[tuple[str, str]]:
    """Return list of districts for given location as (name, id) tuples."""
    return DISTRICTS.get(location, [])


class CianParser:
    """Parser for Cian.ru real estate listings using Playwright.

    Args:
        location: City name (e.g. "Москва"). See list_locations() for valid values.
        proxies: Proxy URL string for Playwright browser context, or None.
            If a list is passed, the first element is used (with a warning).
    """

    def __init__(self, location: str, proxies: str | list | None = None):
        location_id = _validate_location(location)

        proxy: str | None = None
        if isinstance(proxies, list):
            logger.warning("List of proxies passed; only the first one will be used (Playwright supports one proxy per context).")
            proxy = proxies[0] if proxies else None
        elif isinstance(proxies, str):
            proxy = proxies

        self._location_name = location
        self._location_id = location_id
        self._browser = BrowserManager(proxy=proxy)

    def get_flats(
        self,
        deal_type: str,
        rooms: int | str | tuple = "all",
        with_saving_csv: bool = False,
        with_extra_data: bool = False,
        additional_settings: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Parse flat listings from Cian.

        Args:
            deal_type: "sale", "rent_long", or "rent_short"
            rooms: Room count filter. Int (1-5), "studio", "all", or tuple of mixed.
            with_saving_csv: Save results to CSV file.
            with_extra_data: Collect additional data from detail pages (slower).
            additional_settings: Dict with filters (min_price, max_price, metro, sort_by, etc.)

        Returns:
            List of dicts with flat data.
        """
        _validate_deal_type(deal_type)
        _validate_rooms(rooms)

        deal, rent_period = _resolve_deal_type(deal_type)

        url_format = _build_url(
            location_id=self._location_id, deal_type=deal,
            accommodation_type="flat", rooms=rooms,
            rent_period_type=rent_period, additional_settings=additional_settings,
        )

        parser = FlatListParser(
            browser=self._browser,
            accommodation_type="flat",
            deal_type=deal,
            rent_period_type=rent_period,
            location_name=self._location_name,
            with_saving_csv=with_saving_csv,
            with_extra_data=with_extra_data,
            additional_settings=additional_settings,
        )

        return parser.run(url_format)

    def get_suburban(
        self,
        suburban_type: str,
        deal_type: str,
        with_saving_csv: bool = False,
        with_extra_data: bool = False,
        additional_settings: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Parse suburban property listings from Cian.

        Args:
            suburban_type: "house", "house-part", "land-plot", or "townhouse"
            deal_type: "sale", "rent_long", or "rent_short"
            with_saving_csv: Save results to CSV file.
            with_extra_data: Collect additional data from detail pages (slower).
            additional_settings: Dict with filters.

        Returns:
            List of dicts with suburban property data.
        """
        _validate_suburban_type(suburban_type)
        _validate_deal_type(deal_type)

        deal, rent_period = _resolve_deal_type(deal_type)

        url_format = _build_url(
            location_id=self._location_id, deal_type=deal,
            accommodation_type="suburban", rent_period_type=rent_period,
            suburban_type=suburban_type, additional_settings=additional_settings,
        )

        parser = SuburbanListParser(
            browser=self._browser,
            accommodation_type="suburban",
            deal_type=deal,
            rent_period_type=rent_period,
            location_name=self._location_name,
            with_saving_csv=with_saving_csv,
            with_extra_data=with_extra_data,
            additional_settings=additional_settings,
            object_type=suburban_type,
        )

        return parser.run(url_format)

    def get_newobjects(self, with_saving_csv: bool = False) -> list[dict[str, Any]]:
        """Parse new construction object listings from Cian.

        Args:
            with_saving_csv: Save results to CSV file.

        Returns:
            List of dicts with new construction data.
        """
        url_format = _build_url(
            location_id=self._location_id, deal_type="sale",
            accommodation_type="newobject",
        )

        parser = NewObjectListParser(
            browser=self._browser,
            location_name=self._location_name,
            with_saving_csv=with_saving_csv,
        )

        return parser.run(url_format)

    def close(self) -> None:
        """Close browser and clean up resources."""
        self._browser.close()

    def __enter__(self) -> "CianParser":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _validate_location(location: str) -> str:
    for city_name, city_id in CITIES:
        if city_name == location:
            return city_id
    raise LocationNotFoundError(
        f'Location "{location}" not found. '
        f'See cian_parser.list_locations() for available locations.'
    )


def _validate_deal_type(deal_type: str) -> None:
    if deal_type not in DEAL_TYPES:
        raise ValueError(
            f'Invalid deal_type="{deal_type}". '
            f'Valid values: "sale", "rent_long", "rent_short".'
        )


def _validate_rooms(rooms: int | str | tuple) -> None:
    if isinstance(rooms, tuple):
        for r in rooms:
            if isinstance(r, int):
                if r < 1 or r > 5:
                    raise ValueError(f'Room count {r} out of range. Valid: 1-5, "studio", "all".')
            elif isinstance(r, str):
                if r != "studio":
                    raise ValueError(f'Invalid room value "{r}". Valid string values: "studio", "all".')
            else:
                raise ValueError(f'Invalid type in rooms tuple: {type(r)}. Expected int or str.')
    elif isinstance(rooms, int):
        if rooms < 1 or rooms > 5:
            raise ValueError(f'Room count {rooms} out of range. Valid: 1-5, "studio", "all".')
    elif isinstance(rooms, str):
        if rooms not in ("studio", "all"):
            raise ValueError(f'Invalid rooms="{rooms}". Valid: 1-5, "studio", "all".')
    else:
        raise ValueError(f'Invalid type for rooms: {type(rooms)}. Expected int, str, or tuple.')


def _validate_suburban_type(suburban_type: str) -> None:
    if suburban_type not in OBJECT_SUBURBAN_TYPES:
        raise ValueError(
            f'Invalid suburban_type="{suburban_type}". '
            f'Valid values: "house", "house-part", "land-plot", "townhouse".'
        )


def _resolve_deal_type(deal_type: str) -> tuple[str, int | None]:
    if deal_type == "rent_long":
        return "rent", 4
    if deal_type == "rent_short":
        return "rent", 2
    return deal_type, None


def _build_url(
    location_id: str,
    deal_type: str,
    accommodation_type: str,
    rooms: int | str | tuple | None = None,
    rent_period_type: int | None = None,
    suburban_type: str | None = None,
    additional_settings: dict[str, Any] | None = None,
) -> str:
    builder = URLBuilder(accommodation_type == "newobject")
    builder.add_location(location_id)
    builder.add_deal_type(deal_type)
    builder.add_accommodation_type(accommodation_type)

    if rooms is not None:
        builder.add_room(rooms)

    if rent_period_type is not None:
        builder.add_rent_period_type(rent_period_type)

    if suburban_type is not None:
        builder.add_object_suburban_type(suburban_type)

    if additional_settings is not None:
        builder.add_additional_settings(additional_settings)

    return builder.get_url()
