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
