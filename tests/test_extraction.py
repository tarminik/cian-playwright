from unittest.mock import Mock

import pytest
from playwright.sync_api import sync_playwright

from cian_parser.exceptions import CaptchaError
from cian_parser.flat.page_parser import FlatDetailParser
from cian_parser.helpers import (
    define_author, define_deal_url_id, define_location_data, define_price_data,
    define_rooms_count, define_specification_data, parse_location_data,
)
from cian_parser.newobject.page_parser import NewObjectDetailParser
from cian_parser.page_utils import extract_phone
from cian_parser.suburban.page_parser import SuburbanDetailParser


DETAIL_PARSERS = [FlatDetailParser, SuburbanDetailParser, NewObjectDetailParser]


def make_page(*, body="", spans=(), phone="", html=""):
    page = Mock()
    page.url = "https://www.cian.ru/sale/flat/123456789/"
    page.inner_text.return_value = body
    page.content.return_value = html
    page.query_selector.side_effect = lambda selector: Mock() if "OfferCardPageLayout" in selector or "NewbuildingName" in selector else None
    elements = [Mock(inner_text=Mock(return_value=text)) for text in spans]
    phones = [Mock(get_attribute=Mock(return_value=phone))] if phone else []
    page.query_selector_all.side_effect = lambda selector: {
        "[data-name='OfferCardPageLayout'] a[href^='tel:']": phones, "span": elements,
        "[data-name='OfferCardPageLayout'] span": elements,
    }.get(selector, [])
    return page


@pytest.mark.parametrize("title,count", [
    ("6-комн. квартира", 6),
    ("11-комн. квартира", 11),
    ("СТУДИЯ, 25 м²", 1),
    ("Студия дизайна: 3-комн. квартира", 3),
])
def test_room_count_is_not_limited_to_five(title, count):
    assert define_rooms_count(title) == count


@pytest.mark.parametrize("suffix", ["/?source=search", "?source=search", "/#description"])
def test_deal_id_ignores_tracking_and_fragment(suffix):
    assert define_deal_url_id("https://www.cian.ru/sale/flat/123456789" + suffix) == "123456789"


@pytest.mark.parametrize("url", ["https://www.cian.ru", "https://www.cian.ru/sale/flat/", ""])
def test_non_listing_urls_have_no_deal_id(url):
    assert define_deal_url_id(url) == "-1"


def test_specification_handles_grouped_area_and_three_digit_floor():
    card = Mock()
    card.query_selector.return_value.inner_text.return_value = "6-комн. квартира, 1\u00a0250,5 м², 105 / 120 этаж"
    result = define_specification_data(card)
    assert result == {"floor": 105, "floors_count": 120, "rooms_count": 6, "total_meters": 1250.5}


def test_specification_prefers_offer_specs_to_marketing_title():
    title = Mock(inner_text=Mock(return_value="Студия дизайна, 99 м²\n3-комн. квартира, 55,8 м², 3/11 этаж"))
    subtitle = Mock(inner_text=Mock(return_value="3-комн. квартира, 55,8 м², 3/11 этаж"))
    card = Mock()
    card.query_selector.side_effect = lambda selector: subtitle if selector == "[data-mark='OfferSubtitle']" else title
    assert define_specification_data(card) == {"floor": 3, "floors_count": 11, "rooms_count": 3, "total_meters": 55.8}


@pytest.mark.parametrize("parser_class", DETAIL_PARSERS)
def test_detail_captcha_survives_cleanup_failure(parser_class):
    page = make_page(body="Captcha")
    page.close.side_effect = RuntimeError("already disconnected")
    browser = Mock(new_page=Mock(return_value=page))
    partial = [{"url": "previous"}]
    with pytest.raises(CaptchaError) as exc_info:
        parser_class(browser).parse(page.url, partial_results=partial)
    assert exc_info.value.partial_results == partial
    page.close.assert_called_once()


@pytest.mark.parametrize("parser_class", DETAIL_PARSERS)
@pytest.mark.parametrize("partial", [[{"url": "previous"}], []])
def test_detail_navigation_captcha_keeps_explicit_partial_results(parser_class, partial):
    page = make_page()
    browser = Mock(new_page=Mock(return_value=page))
    browser.navigate.side_effect = CaptchaError("HTTP 403 CAPTCHA", partial_results=[{"url": "browser"}])
    with pytest.raises(CaptchaError) as exc_info:
        parser_class(browser).parse(page.url, partial_results=partial)
    assert exc_info.value.partial_results == partial
    assert exc_info.value.partial_results is not partial
    page.close.assert_called_once()


@pytest.mark.parametrize("parser_class", DETAIL_PARSERS)
def test_detail_navigation_failure_is_not_reported_as_empty_success(parser_class):
    page = make_page()
    browser = Mock(new_page=Mock(return_value=page))
    browser.navigate.side_effect = RuntimeError("navigation failed")
    with pytest.raises(RuntimeError, match="navigation failed"):
        parser_class(browser).parse(page.url)
    page.close.assert_called_once()


@pytest.mark.parametrize("parser_class", [FlatDetailParser, SuburbanDetailParser])
def test_detail_phone_comes_from_contact_link_not_unrelated_html(parser_class):
    page = make_page(phone="tel:+7 (999) 123-45-67", html='<script>"offset":"+7"</script>')
    browser = Mock(new_page=Mock(return_value=page))
    assert parser_class(browser).parse(page.url)["phone"] == "+79991234567"


def test_suburban_total_area_is_not_living_area():
    page = make_page(spans=["Общая площадь", "150 м²", "Жилая площадь", "80 м²"])
    browser = Mock(new_page=Mock(return_value=page))
    assert SuburbanDetailParser(browser).parse(page.url)["living_meters"] == "80 м²"


@pytest.mark.parametrize("body", ["CAPTCHA", "Подтвердите, что вы не робот"])
@pytest.mark.parametrize("parser_class", DETAIL_PARSERS)
def test_detail_detects_challenge_text(parser_class, body):
    page = make_page(body=body)
    browser = Mock(new_page=Mock(return_value=page))
    with pytest.raises(CaptchaError):
        parser_class(browser).parse(page.url)


def test_captcha_url_does_not_depend_on_readable_body():
    from cian_parser.page_utils import raise_for_captcha

    page = make_page()
    page.url = "https://www.cian.ru/captcha/?redirect=/sale/flat/123456789/"
    page.inner_text.side_effect = RuntimeError("body unavailable")
    partial = [{"url": "previous"}]
    with pytest.raises(CaptchaError) as exc_info:
        raise_for_captcha(page, partial)
    partial.clear()
    assert exc_info.value.partial_results == [{"url": "previous"}]


@pytest.mark.parametrize("parser_class", DETAIL_PARSERS)
def test_listing_mentions_of_captcha_do_not_discard_valid_page(parser_class):
    page = make_page(body="Описание квартиры. Для связи на сайте агентства используется captcha.")
    browser = Mock(new_page=Mock(return_value=page))
    assert isinstance(parser_class(browser).parse(page.url), dict)


@pytest.mark.parametrize("parser_class", DETAIL_PARSERS)
def test_unrelated_detail_page_is_not_reported_as_empty_success(parser_class):
    page = make_page(body="Объявление не найдено")
    page.query_selector.side_effect = None
    page.query_selector.return_value = None
    browser = Mock(new_page=Mock(return_value=page))
    with pytest.raises(RuntimeError, match="detail content is missing"):
        parser_class(browser).parse(page.url)
    page.close.assert_called_once()


@pytest.fixture(scope="module")
def local_browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.mark.parametrize("parser_class,html,expected", [
    (
        FlatDetailParser,
        '<main data-name="OfferCardPageLayout">'
        '<div><span>Жилая площадь</span><span>32,5&nbsp;м²</span></div>'
        '<div><span>Площадь кухни</span><span>12&nbsp;м²</span></div>'
        '<div><span>Этаж</span><span>3 из 11</span></div>'
        '<a href="tel:+7 (999) 123-45-67">Телефон</a></main>',
        {"living_meters": "32,5\u00a0м²", "kitchen_meters": "12\u00a0м²", "floor": 3, "floors_count": 11, "phone": "+79991234567"},
    ),
    (
        SuburbanDetailParser,
        '<main data-name="OfferCardPageLayout">'
        '<div><span>Общая площадь</span><span>4&nbsp;700&nbsp;м²</span></div>'
        '<div><span>Участок</span><span>2&nbsp;га</span></div>'
        '<div><span>Жилая площадь</span><span>800&nbsp;м²</span></div></main>',
        {"living_meters": "800\u00a0м²", "land_plot": "2\u00a0га"},
    ),
    (
        NewObjectDetailParser,
        '<div data-name="NewbuildingName"><h1>ЖК Пример</h1></div>'
        '<div><span data-testid="SpecificationTitle">Сдача</span><div data-testid="SpecificationValue">2026</div></div>'
        '<div><span data-testid="SpecificationTitle">Потолки</span><div data-testid="SpecificationValue"><span>3,65 м</span></div></div>'
        '<div><span data-testid="SpecificationTitle">Этажность</span><div data-testid="SpecificationValue">11–22</div></div>'
        '<div><span data-testid="SpecificationTitle">Класс</span><div data-testid="SpecificationValue">Премиум</div></div>'
        '<div data-name="BuilderInfoItem"><p>Застройщик</p><div data-name="BasicInfoLink"><a href="/zastroishchik-pioneer/"><span><span>PIONEER</span></span></a></div></div>',
        {"year_of_construction": "2026", "ceiling_height": "3,65 м", "floors_from": 11, "floors_to": 22, "class": "Премиум", "builder": "PIONEER"},
    ),
])
def test_detail_extraction_with_current_dom_in_local_chromium(local_browser, parser_class, html, expected):
    context = local_browser.new_context()
    browser = Mock(new_page=context.new_page)
    browser.navigate.side_effect = lambda page, url: page.set_content(html)
    try:
        result = parser_class(browser).parse("https://www.cian.ru/example/")
        assert {field: result[field] for field in expected} == expected
        assert context.pages == []
    finally:
        context.close()


@pytest.mark.parametrize("label,name,expected_type", [
    ("РИЕЛТОР", "Алёна Иванова", "realtor"),
    ("АГЕНТСТВО НЕДВИЖИМОСТИ", "АВИА-АПАРТ", "real_estate_agent"),
    ("Риелтор", "Иванов, Иван", "realtor"),
])
def test_author_labels_accept_current_uppercase_dom(local_browser, label, name, expected_type):
    page = local_browser.new_page()
    try:
        page.set_content(f'<article><div data-name="BrandingLevelWrapper">{label}<br>{name}<br>Суперагент</div></article>')
        assert define_author(page.query_selector("article")) == {"author": name, "author_type": expected_type}
    finally:
        page.close()


@pytest.mark.parametrize("price_info,expected_commission", [
    ("От года, комм. платежи включены (без счётчиков), комиссия 50%, залог 65 000 ₽", 50),
    ("Скидка 10%, комиссия 50%, залог 65 000 ₽", 50),
    ("От года, без комиссии, залог 65 000 ₽", 0),
])
def test_rent_commission_from_separate_price_info(local_browser, price_info, expected_commission):
    page = local_browser.new_page()
    try:
        page.set_content(
            '<article><span data-mark="MainPrice">65 000 ₽/мес.</span>'
            f'<div data-mark="PriceInfo">{price_info}</div></article>'
        )
        result = define_price_data(page.query_selector("article"))
        assert result["price_per_month"] == 65000
        assert result["commissions"] == expected_commission
        assert result["price"] == -1
    finally:
        page.close()


def test_residential_complex_can_be_separate_from_address(local_browser):
    page = local_browser.new_page()
    try:
        page.set_content(
            '<article><a href="https://zhk-opus-i.cian.ru/">ЖК «Клубный дом ОПУС»</a>'
            '<span data-name="GeoLabel">Москва</span>'
            '<span data-name="GeoLabel">Дербеневская набережная</span>'
            '<span data-name="GeoLabel">1/2</span></article>'
        )
        card = page.query_selector("article")
        result = define_location_data(card, is_sale=True)
        assert result["residential_complex"] == "Клубный дом ОПУС"
        assert result["street"] == "Дербеневская набережная"
        assert result["house_number"] == "1/2"
        assert "residential_complex" not in define_location_data(card, is_sale=False)
    finally:
        page.close()


@pytest.mark.parametrize("seller_phone,expected", [("+7 (999) 123-45-67", "+79991234567"), (None, "")])
def test_phone_does_not_return_website_support_number(local_browser, seller_phone, expected):
    page = local_browser.new_page()
    contact = f'<a href="tel:{seller_phone}">Телефон продавца</a>' if seller_phone else ""
    try:
        page.set_content(
            '<header><a href="tel:+78005553535">Поддержка</a></header>'
            f'<main data-name="OfferCardPageLayout">{contact}</main>'
            '<footer><a href="tel:+78005553535">Поддержка</a></footer>'
        )
        assert extract_phone(page) == expected
    finally:
        page.close()


@pytest.mark.parametrize("parser_class", [FlatDetailParser, SuburbanDetailParser])
def test_detail_fields_ignore_labels_outside_listing(local_browser, parser_class):
    html = (
        '<main data-name="OfferCardPageLayout">'
        '<div><span>Жилая площадь</span><span>80 м²</span></div>'
        '<div><span>Год постройки</span><span>2010</span></div></main>'
        '<aside><div><span>Жилая площадь</span><span>20 м²</span></div>'
        '<div><span>Год постройки</span><span>2025</span></div></aside>'
    )
    browser = Mock(new_page=local_browser.new_page)
    browser.navigate.side_effect = lambda page, url: page.set_content(html)
    result = parser_class(browser).parse("https://www.cian.ru/example/")
    assert result["living_meters"] == "80 м²"
    assert result["year_of_construction"] == "2010"


@pytest.mark.parametrize("non_street", ["м. Проспект Мира", "ЖК «Переулок 8»", "Мостовской р-н", "поселение Московский"])
@pytest.mark.parametrize("suburban", [False, True])
def test_address_does_not_confuse_metro_complex_or_district_with_street(non_street, suburban):
    # Place the false candidate first for flats and last for suburban: the old
    # implementations respectively kept the first and the last matching label.
    labels = ["Москва", non_street, "улица Гиляровского", "20"]
    if suburban:
        labels = ["Москва", "улица Гиляровского", "20", non_street]
    card = Mock(query_selector=Mock(return_value=None))
    card.query_selector_all.side_effect = lambda selector: [
        Mock(inner_text=Mock(return_value=text)) for text in labels
    ] if selector == "[data-name='GeoLabel']" else []
    result = parse_location_data(card) if suburban else define_location_data(card, is_sale=False)
    assert result["street"] == ("улица Гиляровского" if suburban else "Гиляровского")
    assert result["house_number"] == "20"


@pytest.mark.parametrize("street", ["Ленинградское шоссе", "Кузнецкий мост", "ул.Ленина", "проспект Мира"])
def test_valid_named_road_types_remain_streets(street):
    card = Mock(query_selector=Mock(return_value=None))
    card.query_selector_all.return_value = [Mock(inner_text=Mock(return_value=text)) for text in [street, "5"]]
    result = define_location_data(card, is_sale=False)
    assert result["street"] == street
    assert result["house_number"] == "5"
