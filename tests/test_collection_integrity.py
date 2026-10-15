from unittest.mock import Mock

import pytest
from playwright.sync_api import sync_playwright

from cian_parser.flat.list_parser import FlatListParser
from cian_parser.suburban.list_parser import SuburbanListParser
from cian_parser.newobject.list_parser import NewObjectListParser
from cian_parser.exceptions import CaptchaError


def make_parser(browser):
    return FlatListParser(
        browser=browser, accommodation_type="flat", deal_type="sale",
        rent_period_type=None, location_name="Москва",
    )


def test_repeated_page_failure_raises_and_closes_page(monkeypatch):
    browser = Mock()
    parser = make_parser(browser)
    parser.result = [{"url": "https://www.cian.ru/sale/flat/1/"}]
    parser._parse_page = Mock(side_effect=[(True, False)] + [TimeoutError("page 2")] * 3)
    monkeypatch.setattr("cian_parser.base_list.time.sleep", lambda _: None)
    with pytest.raises(TimeoutError, match="page 2"):
        parser.run("https://www.cian.ru/cat.php?p={}")
    assert parser._parse_page.call_count == 4
    browser.new_page.return_value.close.assert_called_once()


def test_only_search_results_are_collected():
    parser = make_parser(Mock())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content('''<div data-name="SearchEngineResultsPageContainer">
                <div data-name="Offers"><div><article data-name="CardComponent" id="match"></article></div></div>
                <div data-name="SuggestionsLayout"><article data-name="CardComponent" id="recommendation"></article></div>
            </div>''')
            assert [card.get_attribute("id") for card in parser._get_cards(page)] == ["match"]
            page.set_content('''<div data-name="SearchEngineResultsPageContainer">
                <div data-name="SuggestionsLayout"><article data-name="CardComponent"></article></div>
            </div>''')
            assert parser._get_cards(page) == []
            page.set_content("<h1>Service unavailable</h1>")
            with pytest.raises(RuntimeError, match="container is missing"):
                parser._get_cards(page)
        finally:
            browser.close()


def test_newobject_failure_is_not_returned_as_completed_collection(monkeypatch):
    browser = Mock()
    parser = NewObjectListParser(browser, "Москва")
    parser._parse_page = Mock(side_effect=TimeoutError("page failed"))
    monkeypatch.setattr("time.sleep", lambda _: None)
    with pytest.raises(TimeoutError, match="page failed"):
        parser.run("https://www.cian.ru/newobjects/list?p={}")
    assert parser._parse_page.call_count == 3
    browser.new_page.return_value.close.assert_called_once()


def test_close_failure_preserves_captcha_and_partial_results(monkeypatch):
    browser = Mock()
    browser.new_page.return_value.close.side_effect = RuntimeError("page gone")
    parser = make_parser(browser)
    parser.result = [{"url": "https://www.cian.ru/sale/flat/1/"}]
    parser._paginate = Mock(side_effect=CaptchaError("captcha", []))
    with pytest.raises(CaptchaError) as error:
        parser.run("https://www.cian.ru/cat.php?p={}")
    assert error.value.partial_results == parser.result
    assert error.value.partial_results is not parser.result


def test_failed_csv_write_does_not_mark_record_collected(monkeypatch):
    parser = make_parser(Mock())
    parser.with_saving_csv = True
    parser.parse_card = Mock(return_value={"url": "https://www.cian.ru/sale/flat/1/", "price": 100})
    writer = Mock(side_effect=[OSError("disk full"), None])
    monkeypatch.setattr("cian_parser.base_list.save_to_csv", writer)
    with pytest.raises(OSError, match="disk full"):
        parser._process_card(Mock())
    assert parser.result == []
    parser._process_card(Mock())
    assert len(parser.result) == parser.count_parsed_offers == 1
    assert writer.call_count == 2


@pytest.fixture
def html_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser.new_page()
        finally:
            browser.close()


def test_suburban_excludes_recommendations_and_rejects_invalid_page(html_page):
    parser = SuburbanListParser(Mock(), "suburban", "sale", None, "Москва", object_type="house")
    html_page.set_content('''<div data-name="SearchEngineResultsPageContainer">
        <div data-name="Offers"><article data-name="CardComponent" id="match"></article></div>
        <div data-name="SuggestionsLayout"><article data-name="CardComponent" id="other"></article></div>
    </div>''')
    assert [card.get_attribute("id") for card in parser._get_cards(html_page)] == ["match"]
    html_page.set_content("<h1>Temporarily unavailable</h1>")
    with pytest.raises(RuntimeError):
        parser._get_cards(html_page)


def test_newobject_card_uses_title_link_and_preserves_project_paths(html_page, monkeypatch):
    parser = NewObjectListParser(Mock(), "Москва")
    details = Mock(return_value={"class": "Бизнес"})
    monkeypatch.setattr("cian_parser.newobject.page_parser.NewObjectDetailParser.parse", details)
    monkeypatch.setattr("time.sleep", lambda _: None)
    html_page.set_content('''<div data-mark="GKCard">
        <a data-mark="Link" href="https://www.cian.ru/otzyvy/">Отзывы</a>
        <div data-name="NewbuildingInfo"><div>
            <a href="/zhiloy-kompleks-first-1/?tracking=1">ЖК Первый</a>
        </div></div><div data-name="AddressLine">Москва, Арбат</div>
    </div><div data-mark="GKCard"><div data-testid="newbuildingTitle">
        <a href="https://www.cian.ru/zhiloy-kompleks-second-2/">ЖК Второй</a>
    </div><div data-name="AddressLine">Москва, Хамовники</div></div>''')
    for card in html_page.query_selector_all("[data-mark='GKCard']"):
        parser._process_card(card)
    assert [record["name"] for record in parser.result] == ["ЖК Первый", "ЖК Второй"]
    assert [record["url"] for record in parser.result] == [
        "https://www.cian.ru/zhiloy-kompleks-first-1/",
        "https://www.cian.ru/zhiloy-kompleks-second-2/",
    ]
    assert parser.result[0]["full_full_location_address"] == "Москва, Арбат"
    assert details.call_count == 2


@pytest.mark.parametrize("markup,expected", [
    ('<a href="/cat.php?p=2">Дальше</a>', True),
    ('<button class="foo--next--" disabled>Дальше</button>', False),
    ('<a href="/cat.php?p=1">Назад</a>', False),
    ('<li><a href="/cat.php?p=5">...</a></li>', True),
])
def test_pagination_follows_enabled_page_links(html_page, markup, expected):
    html_page.set_content(f'<nav data-name="Pagination">{markup}</nav>')
    assert make_parser(Mock())._has_next_page(html_page, 1) is expected


def test_newobject_missing_results_container_is_error(html_page):
    html_page.set_content("<h1>Something went wrong</h1>")
    parser = NewObjectListParser(Mock(), "Москва")
    with pytest.raises(RuntimeError):
        parser._get_cards(html_page)
