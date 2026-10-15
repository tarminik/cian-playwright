from copy import deepcopy
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from cian_parser import CianParser
from cian_parser import parser as parser_module


@pytest.mark.parametrize("method, args, parser_class", [
    ("get_flats", ("sale",), "FlatListParser"),
    ("get_suburban", ("house", "sale"), "SuburbanListParser"),
])
def test_invalid_page_range_fails_before_collection(monkeypatch, method, args, parser_class):
    collector = Mock()
    monkeypatch.setattr(parser_module, parser_class, collector)
    with CianParser("Москва") as parser:
        with pytest.raises(ValueError, match="start_page"):
            getattr(parser, method)(*args, additional_settings={"start_page": 2, "end_page": 1})
    collector.assert_not_called()


def test_valid_call_preserves_filters_pagination_and_input(monkeypatch):
    collector = Mock()
    collector.return_value.run.return_value = [{"url": "https://www.cian.ru/rent/flat/123/"}]
    monkeypatch.setattr(parser_module, "FlatListParser", collector)
    settings = {"start_page": 2, "end_page": 3, "district": ["Красносельский"], "min_price": "1000"}
    original = deepcopy(settings)
    with CianParser("Санкт-Петербург") as parser:
        result = parser.get_flats("rent_short", rooms=(6, "studio"), additional_settings=settings)
    assert result == collector.return_value.run.return_value
    query = parse_qs(urlsplit(collector.return_value.run.call_args.args[0].format(2)).query)
    assert query["region"] == ["2"]
    assert query["deal_type"] == ["rent"]
    assert query["type"] == ["2"]
    assert query["room6"] == query["room9"] == ["1"]
    assert query["district[0]"] == ["143"]
    assert query["p"] == ["2"]
    assert settings == original
    assert collector.call_args.kwargs["additional_settings"] == original


@pytest.mark.parametrize("proxies", [123, {}, ("http://proxy:8080",), [123], [None]])
def test_invalid_proxy_configuration_does_not_silently_disable_proxy(proxies):
    with pytest.raises(ValueError, match="proxies"):
        CianParser("Москва", proxies=proxies)


def test_district_metadata_cannot_be_modified_by_callers(monkeypatch):
    districts = {"Москва": [("Арбат", "13")]}
    monkeypatch.setattr(parser_module, "DISTRICTS", districts)
    parser_module.list_districts("Москва").clear()
    assert districts == {"Москва": [("Арбат", "13")]}


def test_metro_metadata_cannot_be_modified_by_callers(monkeypatch):
    stations = {"Московский": [["Маяковская", "68"]]}
    monkeypatch.setattr(parser_module, "METRO_STATIONS", stations)
    returned = parser_module.list_metro_stations()
    returned["Московский"][0][1] = "999"
    returned["Московский"].clear()
    returned.clear()
    assert stations == {"Московский": [["Маяковская", "68"]]}


def test_newobjects_default_limit_preserves_positional_csv_argument(monkeypatch):
    collector = Mock()
    monkeypatch.setattr(parser_module, "NewObjectListParser", collector)
    with CianParser("Москва") as parser:
        assert parser.get_newobjects(True) == collector.return_value.run.return_value
    assert collector.call_args.kwargs["with_saving_csv"] is True
    assert collector.call_args.kwargs["additional_settings"] == {"end_page": 50}


def test_newobjects_accepts_bounded_pages_without_mutating_input(monkeypatch):
    collector = Mock()
    monkeypatch.setattr(parser_module, "NewObjectListParser", collector)
    settings = {"start_page": 2, "end_page": 3}
    with CianParser("Москва") as parser:
        parser.get_newobjects(additional_settings=settings)
    passed_settings = collector.call_args.kwargs["additional_settings"]
    assert passed_settings == settings
    assert passed_settings is not settings
    query = parse_qs(urlsplit(collector.return_value.run.call_args.args[0].format(2)).query)
    assert query["p"] == ["2"]
    assert query["region"] == ["1"]
    assert "start_page" not in query and "end_page" not in query


@pytest.mark.parametrize("settings", [
    {"start_page": 51}, {"end_page": 0}, {"start_page": True},
    {"start_page": 3, "end_page": 2}, {"end_page": 2.5},
    {"min_price": 1000}, {"district": "Арбат"}, [], 42,
])
def test_newobjects_rejects_invalid_pages_and_unsupported_filters_before_collection(monkeypatch, settings):
    collector = Mock()
    monkeypatch.setattr(parser_module, "NewObjectListParser", collector)
    with CianParser("Москва") as parser:
        with pytest.raises(ValueError):
            parser.get_newobjects(additional_settings=settings)
    collector.assert_not_called()


def test_newobject_collector_copies_settings_and_keeps_default_limit():
    from cian_parser.newobject.list_parser import NewObjectListParser

    settings = {"start_page": 2}
    parser = NewObjectListParser(Mock(), "Москва", additional_settings=settings)
    assert (parser.start_page, parser.end_page) == (2, 50)
    assert settings == {"start_page": 2}
    assert parser.additional_settings is not settings


@pytest.mark.parametrize("headless", [True, False])
def test_parser_forwards_explicit_browser_mode(monkeypatch, headless):
    browser_manager = Mock()
    monkeypatch.setattr(parser_module, "BrowserManager", browser_manager)
    with CianParser("Москва", "http://proxy:8080", headless=headless):
        pass
    browser_manager.assert_called_once_with(proxy="http://proxy:8080", headless=headless)
    browser_manager.return_value.close.assert_called_once()


def test_parser_preserves_headless_default(monkeypatch):
    browser_manager = Mock()
    monkeypatch.setattr(parser_module, "BrowserManager", browser_manager)
    with CianParser("Москва"):
        pass
    browser_manager.assert_called_once_with(proxy=None, headless=True)


@pytest.mark.parametrize("headless", [None, 0, 1, "false", []])
def test_invalid_browser_mode_fails_before_creating_manager(monkeypatch, headless):
    browser_manager = Mock()
    monkeypatch.setattr(parser_module, "BrowserManager", browser_manager)
    with pytest.raises(ValueError, match="headless"):
        CianParser("Москва", headless=headless)
    browser_manager.assert_not_called()
