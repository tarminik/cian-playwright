from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

from cian_parser.parser import _build_url
from cian_parser.url_builder import URLBuilder


def test_basic_flat_sale_url():
    builder = URLBuilder(is_newobject=False)
    builder.add_location("1")
    builder.add_deal_type("sale")
    builder.add_accommodation_type("flat")
    url = builder.get_url()

    assert "cian.ru/cat.php?" in url
    assert "region=1" in url
    assert "deal_type=sale" in url
    assert "offer_type=flat" in url
    assert "p={}" in url


def test_newobject_url():
    builder = URLBuilder(is_newobject=True)
    builder.add_location("1")
    builder.add_deal_type("sale")
    builder.add_accommodation_type("newobject")
    url = builder.get_url()

    assert "/newobjects/list/?" in url


def test_rooms_single():
    builder = URLBuilder(is_newobject=False)
    builder.add_room(2)
    assert "&room2=1" in builder.get_url()


def test_rooms_studio():
    builder = URLBuilder(is_newobject=False)
    builder.add_room("studio")
    assert "&room9=1" in builder.get_url()


def test_rooms_all():
    builder = URLBuilder(is_newobject=False)
    url_before = builder.get_url()
    builder.add_room("all")
    assert builder.get_url() == url_before


def test_rooms_tuple():
    builder = URLBuilder(is_newobject=False)
    builder.add_room((1, 3, "studio"))
    url = builder.get_url()
    assert "&room1=1" in url
    assert "&room3=1" in url
    assert "&room9=1" in url


def test_additional_settings_price():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({"min_price": 1000000, "max_price": 5000000})
    url = builder.get_url()
    assert "&minprice=1000000" in url
    assert "&maxprice=5000000" in url


def test_additional_settings_metro():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({
        "metro": "Московский",
        "metro_station": "Маяковская",
        "metro_foot_minute": 10,
    })
    url = builder.get_url()
    assert "&metro%5B0%5D=68" in url
    assert "&only_foot=2&foot_min=10" in url


def test_additional_settings_sort():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({"sort_by": "price_from_min_to_max"})
    url = builder.get_url()
    assert "&sort=price_object_order" in url


def test_additional_settings_homeowner():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({"is_by_homeowner": True})
    assert "&is_by_homeowner=1" in builder.get_url()


def test_additional_settings_floor():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({"min_floor": 2, "max_floor": 10, "min_total_floor": 5, "max_total_floor": 25})
    url = builder.get_url()
    assert "&minfloor=2" in url
    assert "&maxfloor=10" in url
    assert "&minfloorn=5" in url
    assert "&maxfloorn=25" in url


def test_suburban_type():
    builder = URLBuilder(is_newobject=False)
    builder.add_object_suburban_type("house")
    assert "&object_type%5B0%5D=1" in builder.get_url()


def test_rent_period_type():
    builder = URLBuilder(is_newobject=False)
    builder.add_rent_period_type(4)
    assert "&type=4" in builder.get_url()


def test_additional_settings_district():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({"district": "Арбат"})
    assert "district%5B0%5D=13" in builder.get_url()


def test_additional_settings_district_multiple():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({"district": ["Арбат", "Тверской"]})
    url = builder.get_url()
    assert "district%5B0%5D=13" in url
    assert "district%5B1%5D=20" in url


def test_additional_settings_district_id():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({"district_id": 13})
    assert "district%5B0%5D=13" in builder.get_url()


def test_additional_settings_district_id_list():
    builder = URLBuilder(is_newobject=False)
    builder.add_additional_settings({"district_id": [13, 20]})
    url = builder.get_url()
    assert "district%5B0%5D=13" in url
    assert "district%5B1%5D=20" in url


@pytest.mark.parametrize("location_id, expected_id", [("1", "16"), ("2", "143")])
def test_district_names_resolve_within_selected_city(location_id, expected_id):
    url = _build_url(location_id, "sale", "flat", additional_settings={"district": "Красносельский"})
    query = parse_qs(urlsplit(url.format(1)).query)
    assert query["district[0]"] == [expected_id]
    assert "district[1]" not in query


@pytest.mark.parametrize("settings", [
    {"start_page": 0}, {"end_page": -1}, {"start_page": True},
    {"end_page": 1.5}, {"start_page": "2"}, {"start_page": 2, "end_page": 1},
    {"min_price": -1}, {"min_price": float("nan")}, {"max_price": float("inf")},
    {"min_price": 20, "max_price": 10}, {"min_floor": 5, "max_floor": 2},
    {"district": "Not a district"}, {"district": []}, {"district_id": []},
    {"district_id": True}, {"district_id": "13&region=2"},
    {"metro": "Московский"}, {"metro_station": "Маяковская"},
    {"metro": "Московский", "metro_station": "Unknown"},
    {"metro": "Unknown", "metro_station": "Маяковская"},
    {"object_type": "Unknown"}, {"sort_by": "Unknown"},
    {"min_price": "10&region=2"}, {"min_price": "{}"},
    {"only_flat": "False"}, {"is_by_homeowner": 2},
    {"min_floor": 2.5}, {"house_material_type": "1.2"},
    {"min_house_year": Decimal("2025.5")}, {"metro_foot_minute": 2.5},
    [], 42,
])
def test_invalid_filters_fail_before_producing_a_broader_or_malformed_query(settings):
    with pytest.raises(ValueError):
        _build_url("1", "sale", "flat", additional_settings=settings)


def test_numeric_strings_are_kept_compatible():
    url = _build_url("1", "sale", "flat", additional_settings={"min_price": "1000", "max_price": "2000"})
    assert parse_qs(urlsplit(url.format(3)).query)["minprice"] == ["1000"]


@pytest.mark.parametrize("value", ["1_000_000", "١٠٠٠٠٠٠", Decimal("1E+6"), 1e6])
def test_numeric_values_use_canonical_ascii_query_format(value):
    url = _build_url("1", "sale", "flat", additional_settings={"min_price": value, "min_floor": "2.0"})
    query = parse_qs(urlsplit(url.format(1)).query)
    assert query["minprice"] == ["1000000"]
    assert query["minfloor"] == ["2"]


def test_price_filters_preserve_decimal_amounts():
    url = _build_url("1", "sale", "flat", additional_settings={"min_price": Decimal("1000.50")})
    assert parse_qs(urlsplit(url.format(1)).query)["minprice"] == ["1000.5"]


def test_filter_values_cannot_inject_parameters_or_pagination_placeholders():
    builder = URLBuilder(is_newobject=False)
    builder.add_location("1&region={}")
    query = parse_qs(urlsplit(builder.get_url().format(2)).query)
    assert query["p"] == ["2"]
    assert query["region"] == ["1&region={}"]


def test_repeated_district_names_and_ids_are_deduplicated():
    url = _build_url("1", "sale", "flat", additional_settings={"district": ["Арбат", "Арбат"], "district_id": [13, 20]})
    query = parse_qs(urlsplit(url.format(1)).query)
    assert query["district[0]"] == ["13"]
    assert query["district[1]"] == ["20"]
    assert "district[2]" not in query


def test_same_named_metro_stations_keep_separate_query_indices():
    url = _build_url("1", "sale", "flat", additional_settings={
        "metro": "Московский", "metro_station": "Авиамоторная",
    })
    query = parse_qs(urlsplit(url.format(1)).query)
    assert query["metro[0]"] == ["1"]
    assert query["metro[1]"] == ["443"]


def test_flat_object_type_cannot_override_suburban_type():
    with pytest.raises(ValueError, match="object_type"):
        _build_url("1", "sale", "suburban", suburban_type="land-plot", additional_settings={"object_type": "secondary"})
