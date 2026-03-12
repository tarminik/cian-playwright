from cian_parser.constants import CITIES, METRO_STATIONS


def test_cities_count():
    assert len(CITIES) >= 150


def test_key_cities_present():
    city_names = {c[0] for c in CITIES}
    assert "Москва" in city_names
    assert "Санкт-Петербург" in city_names
    assert "Екатеринбург" in city_names
    assert "Краснодар" in city_names


def test_moscow_id():
    for name, cid in CITIES:
        if name == "Москва":
            assert cid == "1"
            break


def test_metro_systems():
    assert "Московский" in METRO_STATIONS
    assert "Петербургский" in METRO_STATIONS
    assert "Казанский" in METRO_STATIONS


def test_moscow_metro_has_mayakovskaya():
    stations = {s[0] for s in METRO_STATIONS["Московский"]}
    assert "Маяковская" in stations
