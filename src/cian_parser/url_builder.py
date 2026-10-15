from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from cian_parser.constants import (
    BASE_URL, DEFAULT_POSTFIX_PATH, NEWOBJECT_POSTFIX_PATH, DEFAULT_PATH,
    REGION_PATH, OFFER_TYPE_PATH, RENT_PERIOD_TYPE_PATH, DEAL_TYPE_PATH,
    OBJECT_TYPE_PATH, ROOM_PATH, STUDIO_PATH, IS_ONLY_HOMEOWNER_PATH,
    MIN_BALCONIES_PATH, HAVE_LOGGIA_PATH, MIN_HOUSE_YEAR_PATH, MAX_HOUSE_YEAR_PATH,
    MIN_PRICE_PATH, MAX_PRICE_PATH, MIN_FLOOR_PATH, MAX_FLOOR_PATH,
    MIN_TOTAL_FLOOR_PATH, MAX_TOTAL_FLOOR_PATH, HOUSE_MATERIAL_TYPE_PATH,
    METRO_FOOT_MINUTE_PATH, FLAT_SHARE_PATH, ONLY_FLAT_PATH,
    APARTMENT_PATH, METRO_STATIONS, OBJECT_SUBURBAN_TYPES, OBJECT_TYPES,
    CITIES, DISTRICTS,
    SORT_BY_PRICE_FROM_MIN_TO_MAX_PATH, SORT_BY_PRICE_FROM_MAX_TO_MIN_PATH,
    SORT_BY_TOTAL_METERS_FROM_MAX_TO_MIN_PATH,
    SORT_BY_CREATION_DATA_FROM_NEWER_TO_OLDER_PATH,
    SORT_BY_CREATION_DATA_FROM_OLDER_TO_NEWER_PATH,
    IS_SORT_BY_PRICE_FROM_MIN_TO_MAX_PATH, IS_SORT_BY_PRICE_FROM_MAX_TO_MIN_PATH,
    IS_SORT_BY_TOTAL_METERS_FROM_MAX_TO_MIN_PATH,
    IS_SORT_BY_CREATION_DATA_FROM_NEWER_TO_OLDER_PATH,
    IS_SORT_BY_CREATION_DATA_FROM_OLDER_TO_NEWER_PATH,
)


_NUMERIC_FILTER_PATHS = {
    "min_balconies": MIN_BALCONIES_PATH,
    "min_house_year": MIN_HOUSE_YEAR_PATH,
    "max_house_year": MAX_HOUSE_YEAR_PATH,
    "min_price": MIN_PRICE_PATH,
    "max_price": MAX_PRICE_PATH,
    "min_floor": MIN_FLOOR_PATH,
    "max_floor": MAX_FLOOR_PATH,
    "min_total_floor": MIN_TOTAL_FLOOR_PATH,
    "max_total_floor": MAX_TOTAL_FLOOR_PATH,
    "house_material_type": HOUSE_MATERIAL_TYPE_PATH,
    "metro_foot_minute": METRO_FOOT_MINUTE_PATH,
    "flat_share": FLAT_SHARE_PATH,
}
_SORT_PATHS = {
    IS_SORT_BY_PRICE_FROM_MIN_TO_MAX_PATH: SORT_BY_PRICE_FROM_MIN_TO_MAX_PATH,
    IS_SORT_BY_PRICE_FROM_MAX_TO_MIN_PATH: SORT_BY_PRICE_FROM_MAX_TO_MIN_PATH,
    IS_SORT_BY_TOTAL_METERS_FROM_MAX_TO_MIN_PATH: SORT_BY_TOTAL_METERS_FROM_MAX_TO_MIN_PATH,
    IS_SORT_BY_CREATION_DATA_FROM_NEWER_TO_OLDER_PATH: SORT_BY_CREATION_DATA_FROM_NEWER_TO_OLDER_PATH,
    IS_SORT_BY_CREATION_DATA_FROM_OLDER_TO_NEWER_PATH: SORT_BY_CREATION_DATA_FROM_OLDER_TO_NEWER_PATH,
}


def _encode(value: object) -> str:
    # Braces must be escaped too: the final URL is formatted with a page number.
    return quote(str(value), safe="")


def _validate_settings(settings: dict) -> dict[str, str]:
    if not isinstance(settings, dict):
        raise ValueError("additional_settings must be a dict.")

    for name, default in (("start_page", 1), ("end_page", 100)):
        value = settings.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer.")
    if settings.get("start_page", 1) > settings.get("end_page", 100):
        raise ValueError("start_page must not exceed end_page.")

    numeric: dict[str, Decimal] = {}
    for name in _NUMERIC_FILTER_PATHS:
        if name not in settings:
            continue
        value = settings[name]
        if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
            raise ValueError(f"{name} must be a nonnegative finite number.")
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ValueError(f"{name} must be a nonnegative finite number.") from None
        if not number.is_finite() or number < 0:
            raise ValueError(f"{name} must be a nonnegative finite number.")
        if name not in ("min_price", "max_price") and number != number.to_integral_value():
            raise ValueError(f"{name} must be a whole number.")
        numeric[name] = number
    for suffix in ("price", "floor", "total_floor", "house_year"):
        lower, upper = f"min_{suffix}", f"max_{suffix}"
        if lower in numeric and upper in numeric and numeric[lower] > numeric[upper]:
            raise ValueError(f"{lower} must not exceed {upper}.")

    for name in ("is_by_homeowner", "have_loggia", "only_flat", "only_apartment"):
        if name in settings and (
            not isinstance(settings[name], (bool, int)) or settings[name] not in (0, 1)
        ):
            raise ValueError(f"{name} must be a boolean or 0/1.")

    for name, choices in (("object_type", OBJECT_TYPES), ("sort_by", _SORT_PATHS)):
        if name in settings and (not isinstance(settings[name], str) or settings[name] not in choices):
            raise ValueError(f"Invalid {name}: {settings[name]!r}.")

    # Decimal accepts exponents, underscores and non-ASCII digits. Send the
    # numeric value in plain ASCII so validated inputs are also valid URL values.
    encoded = {}
    for name, number in numeric.items():
        value = format(number, "f") if number else "0"
        encoded[name] = value.rstrip("0").rstrip(".") if "." in value else value
    return encoded


class URLBuilder:
    def __init__(self, is_newobject: bool):
        self._location_id: str | None = None
        self._suburban_type: str | None = None
        self.url = BASE_URL
        if is_newobject:
            self.url += NEWOBJECT_POSTFIX_PATH
        else:
            self.url += DEFAULT_POSTFIX_PATH
        self.url += DEFAULT_PATH

    def get_url(self) -> str:
        return self.url

    def add_accommodation_type(self, accommodation_type: str) -> None:
        self.url += OFFER_TYPE_PATH.format(_encode(accommodation_type))

    def add_deal_type(self, deal_type: str) -> None:
        self.url += DEAL_TYPE_PATH.format(_encode(deal_type))

    def add_location(self, location_id: str) -> None:
        self._location_id = str(location_id)
        self.url += REGION_PATH.format(_encode(location_id))

    def add_room(self, rooms: int | str | tuple) -> None:
        rooms_path = ""
        if isinstance(rooms, tuple):
            for count_of_room in rooms:
                if isinstance(count_of_room, int):
                    if 0 < count_of_room < 7:
                        rooms_path += ROOM_PATH.format(count_of_room)
                elif isinstance(count_of_room, str):
                    if count_of_room == "studio":
                        rooms_path += STUDIO_PATH
        elif isinstance(rooms, int):
            if 0 < rooms < 7:
                rooms_path += ROOM_PATH.format(rooms)
        elif isinstance(rooms, str):
            if rooms == "studio":
                rooms_path += STUDIO_PATH
            elif rooms == "all":
                rooms_path = ""

        self.url += rooms_path

    def add_rent_period_type(self, rent_period_type: int) -> None:
        self.url += RENT_PERIOD_TYPE_PATH.format(_encode(rent_period_type))

    def add_object_suburban_type(self, object_type: str) -> None:
        self.url += OBJECT_TYPE_PATH.format(OBJECT_SUBURBAN_TYPES[object_type])
        self._suburban_type = object_type

    def add_additional_settings(self, additional_settings: dict) -> None:
        numeric_values = _validate_settings(additional_settings)
        district_ids = self._district_ids(additional_settings)
        metro_ids = self._metro_ids(additional_settings)

        if "object_type" in additional_settings:
            if self._suburban_type is not None:
                raise ValueError("object_type is a flat filter and cannot override suburban_type.")
            self.url += OBJECT_TYPE_PATH.format(OBJECT_TYPES[additional_settings["object_type"]])

        if additional_settings.get("is_by_homeowner"):
            self.url += IS_ONLY_HOMEOWNER_PATH
        if additional_settings.get("have_loggia"):
            self.url += HAVE_LOGGIA_PATH

        for name, path in _NUMERIC_FILTER_PATHS.items():
            if name in numeric_values:
                self.url += path.format(_encode(numeric_values[name]))
        for i, metro_id in enumerate(metro_ids):
            self.url += f"&metro%5B{i}%5D={_encode(metro_id)}"
        for i, did in enumerate(district_ids):
            self.url += f"&district%5B{i}%5D={_encode(did)}"

        if additional_settings.get("only_flat"):
            self.url += ONLY_FLAT_PATH.format(1)

        if additional_settings.get("only_apartment"):
            self.url += APARTMENT_PATH.format(1)

        if "sort_by" in additional_settings:
            self.url += _SORT_PATHS[additional_settings["sort_by"]]

    def _district_ids(self, settings: dict) -> list[str]:
        result = []
        if "district" in settings:
            names = settings["district"]
            names = [names] if isinstance(names, str) else names
            if not isinstance(names, (list, tuple)) or not names or not all(isinstance(name, str) for name in names):
                raise ValueError("district must be a name or a nonempty list/tuple of names.")
            city = next((name for name, city_id in CITIES if city_id == self._location_id), None)
            groups = DISTRICTS.values() if self._location_id is None else [DISTRICTS.get(city, [])]
            districts = {name: district_id for group in groups for name, district_id in group}
            for name in names:
                if name not in districts:
                    raise ValueError(f"Unknown district {name!r} for the selected location.")
                result.append(districts[name])

        if "district_id" in settings:
            ids = settings["district_id"]
            ids = ids if isinstance(ids, (list, tuple)) else [ids]
            if not ids:
                raise ValueError("district_id must not be empty.")
            for district_id in ids:
                if isinstance(district_id, bool) or not isinstance(district_id, (int, str)):
                    raise ValueError("district_id must contain positive integer IDs.")
                value = str(district_id)
                if not value.isascii() or not value.isdigit() or int(value) < 1:
                    raise ValueError("district_id must contain positive integer IDs.")
                result.append(value)
        return list(dict.fromkeys(result))

    @staticmethod
    def _metro_ids(settings: dict) -> list[str]:
        if "metro" not in settings and "metro_station" not in settings:
            return []
        metro = settings.get("metro")
        station = settings.get("metro_station")
        if not isinstance(metro, str) or metro not in METRO_STATIONS:
            raise ValueError("metro must name an available metro system when filtering by station.")
        ids = [metro_id for name, metro_id in METRO_STATIONS[metro] if name == station]
        if not ids:
            raise ValueError(f"Unknown metro_station {station!r} in {metro!r}.")
        return list(dict.fromkeys(ids))
