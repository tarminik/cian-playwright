import pytest

from cian_parser.parser import _validate_location, _validate_deal_type, _validate_rooms, _validate_suburban_type
from cian_parser.exceptions import LocationNotFoundError


def test_valid_location():
    assert _validate_location("Москва") == "1"


def test_invalid_location():
    with pytest.raises(LocationNotFoundError):
        _validate_location("НесуществующийГород")


def test_valid_deal_types():
    for dt in ("sale", "rent_long", "rent_short"):
        _validate_deal_type(dt)


def test_invalid_deal_type():
    with pytest.raises(ValueError):
        _validate_deal_type("buy")


def test_valid_rooms_int():
    for r in range(1, 7):
        _validate_rooms(r)


def test_valid_rooms_str():
    _validate_rooms("studio")
    _validate_rooms("all")


def test_valid_rooms_tuple():
    _validate_rooms((1, 3, "studio"))


def test_invalid_rooms_int():
    with pytest.raises(ValueError):
        _validate_rooms(0)
    with pytest.raises(ValueError):
        _validate_rooms(7)


def test_invalid_rooms_str():
    with pytest.raises(ValueError):
        _validate_rooms("big")


def test_invalid_rooms_type():
    with pytest.raises(ValueError):
        _validate_rooms(3.5)


def test_valid_suburban_types():
    for st in ("house", "house-part", "land-plot", "townhouse"):
        _validate_suburban_type(st)


def test_invalid_suburban_type():
    with pytest.raises(ValueError):
        _validate_suburban_type("castle")
