from __future__ import annotations

from cian_parser.constants import (
    BASE_URL, DEFAULT_POSTFIX_PATH, NEWOBJECT_POSTFIX_PATH, DEFAULT_PATH,
    REGION_PATH, OFFER_TYPE_PATH, RENT_PERIOD_TYPE_PATH, DEAL_TYPE_PATH,
    OBJECT_TYPE_PATH, ROOM_PATH, STUDIO_PATH, IS_ONLY_HOMEOWNER_PATH,
    MIN_BALCONIES_PATH, HAVE_LOGGIA_PATH, MIN_HOUSE_YEAR_PATH, MAX_HOUSE_YEAR_PATH,
    MIN_PRICE_PATH, MAX_PRICE_PATH, MIN_FLOOR_PATH, MAX_FLOOR_PATH,
    MIN_TOTAL_FLOOR_PATH, MAX_TOTAL_FLOOR_PATH, HOUSE_MATERIAL_TYPE_PATH,
    METRO_FOOT_MINUTE_PATH, METRO_ID_PATH, FLAT_SHARE_PATH, ONLY_FLAT_PATH,
    APARTMENT_PATH, METRO_STATIONS, OBJECT_SUBURBAN_TYPES, OBJECT_TYPES,
    DISTRICTS,
    SORT_BY_PRICE_FROM_MIN_TO_MAX_PATH, SORT_BY_PRICE_FROM_MAX_TO_MIN_PATH,
    SORT_BY_TOTAL_METERS_FROM_MAX_TO_MIN_PATH,
    SORT_BY_CREATION_DATA_FROM_NEWER_TO_OLDER_PATH,
    SORT_BY_CREATION_DATA_FROM_OLDER_TO_NEWER_PATH,
    IS_SORT_BY_PRICE_FROM_MIN_TO_MAX_PATH, IS_SORT_BY_PRICE_FROM_MAX_TO_MIN_PATH,
    IS_SORT_BY_TOTAL_METERS_FROM_MAX_TO_MIN_PATH,
    IS_SORT_BY_CREATION_DATA_FROM_NEWER_TO_OLDER_PATH,
    IS_SORT_BY_CREATION_DATA_FROM_OLDER_TO_NEWER_PATH,
)


class URLBuilder:
    def __init__(self, is_newobject: bool):
        self.url = BASE_URL
        if is_newobject:
            self.url += NEWOBJECT_POSTFIX_PATH
        else:
            self.url += DEFAULT_POSTFIX_PATH
        self.url += DEFAULT_PATH

    def get_url(self) -> str:
        return self.url

    def add_accommodation_type(self, accommodation_type: str) -> None:
        self.url += OFFER_TYPE_PATH.format(accommodation_type)

    def add_deal_type(self, deal_type: str) -> None:
        self.url += DEAL_TYPE_PATH.format(deal_type)

    def add_location(self, location_id: str) -> None:
        self.url += REGION_PATH.format(location_id)

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
        self.url += RENT_PERIOD_TYPE_PATH.format(rent_period_type)

    def add_object_suburban_type(self, object_type: str) -> None:
        self.url += OBJECT_TYPE_PATH.format(OBJECT_SUBURBAN_TYPES[object_type])

    def add_additional_settings(self, additional_settings: dict) -> None:
        if "object_type" in additional_settings:
            self.url += OBJECT_TYPE_PATH.format(OBJECT_TYPES[additional_settings["object_type"]])

        if additional_settings.get("is_by_homeowner"):
            self.url += IS_ONLY_HOMEOWNER_PATH
        if "min_balconies" in additional_settings:
            self.url += MIN_BALCONIES_PATH.format(additional_settings["min_balconies"])
        if additional_settings.get("have_loggia"):
            self.url += HAVE_LOGGIA_PATH

        if "min_house_year" in additional_settings:
            self.url += MIN_HOUSE_YEAR_PATH.format(additional_settings["min_house_year"])
        if "max_house_year" in additional_settings:
            self.url += MAX_HOUSE_YEAR_PATH.format(additional_settings["max_house_year"])

        if "min_price" in additional_settings:
            self.url += MIN_PRICE_PATH.format(additional_settings["min_price"])
        if "max_price" in additional_settings:
            self.url += MAX_PRICE_PATH.format(additional_settings["max_price"])

        if "min_floor" in additional_settings:
            self.url += MIN_FLOOR_PATH.format(additional_settings["min_floor"])
        if "max_floor" in additional_settings:
            self.url += MAX_FLOOR_PATH.format(additional_settings["max_floor"])

        if "min_total_floor" in additional_settings:
            self.url += MIN_TOTAL_FLOOR_PATH.format(additional_settings["min_total_floor"])
        if "max_total_floor" in additional_settings:
            self.url += MAX_TOTAL_FLOOR_PATH.format(additional_settings["max_total_floor"])

        if "house_material_type" in additional_settings:
            self.url += HOUSE_MATERIAL_TYPE_PATH.format(additional_settings["house_material_type"])

        if "metro" in additional_settings and "metro_station" in additional_settings:
            metro_system = additional_settings["metro"]
            if metro_system in METRO_STATIONS:
                for metro_station, metro_id in METRO_STATIONS[metro_system]:
                    if additional_settings["metro_station"] == metro_station:
                        self.url += METRO_ID_PATH.format(metro_id)

        # District filter — by name (lookup) or by numeric ID
        district_ids = []
        if "district" in additional_settings:
            district_val = additional_settings["district"]
            names = [district_val] if isinstance(district_val, str) else district_val
            for city_districts in DISTRICTS.values():
                for dname, did in city_districts:
                    if dname in names:
                        district_ids.append(did)

        if "district_id" in additional_settings:
            did_val = additional_settings["district_id"]
            if isinstance(did_val, (list, tuple)):
                district_ids.extend(str(d) for d in did_val)
            else:
                district_ids.append(str(did_val))

        for i, did in enumerate(district_ids):
            self.url += f"&district%5B{i}%5D={did}"

        if "metro_foot_minute" in additional_settings:
            self.url += METRO_FOOT_MINUTE_PATH.format(additional_settings["metro_foot_minute"])

        if "flat_share" in additional_settings:
            self.url += FLAT_SHARE_PATH.format(additional_settings["flat_share"])

        if additional_settings.get("only_flat"):
            self.url += ONLY_FLAT_PATH.format(1)

        if additional_settings.get("only_apartment"):
            self.url += APARTMENT_PATH.format(1)

        if "sort_by" in additional_settings:
            sort_map = {
                IS_SORT_BY_PRICE_FROM_MIN_TO_MAX_PATH: SORT_BY_PRICE_FROM_MIN_TO_MAX_PATH,
                IS_SORT_BY_PRICE_FROM_MAX_TO_MIN_PATH: SORT_BY_PRICE_FROM_MAX_TO_MIN_PATH,
                IS_SORT_BY_TOTAL_METERS_FROM_MAX_TO_MIN_PATH: SORT_BY_TOTAL_METERS_FROM_MAX_TO_MIN_PATH,
                IS_SORT_BY_CREATION_DATA_FROM_NEWER_TO_OLDER_PATH: SORT_BY_CREATION_DATA_FROM_NEWER_TO_OLDER_PATH,
                IS_SORT_BY_CREATION_DATA_FROM_OLDER_TO_NEWER_PATH: SORT_BY_CREATION_DATA_FROM_OLDER_TO_NEWER_PATH,
            }
            sort_path = sort_map.get(additional_settings["sort_by"])
            if sort_path:
                self.url += sort_path
