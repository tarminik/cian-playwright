"""Public parser flows through Chromium with every request fulfilled locally."""

import csv
from html import escape
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page

from cian_parser import CaptchaError, CianParser


@pytest.fixture
def routed_parser(monkeypatch):
    monkeypatch.setattr(Page, "wait_for_timeout", lambda self, milliseconds: None)
    monkeypatch.setattr("cian_parser.base_list.time", SimpleNamespace(sleep=lambda seconds: None))
    requests = []
    unexpected = []
    with CianParser("Москва") as parser:
        parser._browser.start()
        context = parser._browser._context
        create_context = parser._browser._create_context

        def serve(response_for):
            def fulfill(route):
                url = urlsplit(route.request.url)
                requests.append(url)
                response = response_for(url)
                if response is None:
                    unexpected.append(route.request.url)
                    response = 404, "Unexpected test request"
                status, body = response
                route.fulfill(
                    status=status, content_type="text/html; charset=utf-8",
                    body='<!doctype html><meta charset="utf-8">' + body,
                )

            context.route("**/*", fulfill)

            def routed_context():
                isolated = create_context()
                isolated.route("**/*", fulfill)
                return isolated

            monkeypatch.setattr(parser._browser, "_create_context", routed_context)

        yield parser, serve, requests
        assert unexpected == []
        assert context.pages == [], "List and detail pages must close after each collection"
        assert parser._browser._browser.contexts == [context], "Isolated collection contexts must close"
    assert parser._browser._started is False


def offer(kind, offer_id, *, tracking=""):
    href = escape(f"/sale/{kind}/{offer_id}/{tracking}", quote=True)
    return f'''<article data-name="CardComponent">
        <div data-name="LinkArea"><a href="{href}">Объявление</a></div>
        <div data-name="TitleComponent">Выгодное предложение
            <span data-mark="OfferSubtitle">2-комн. квартира, 55,8 м², 3/11 этаж</span>
        </div>
        <span data-mark="MainPrice">12 500 000 ₽</span>
        <div data-name="BrandingLevelWrapper">Собственник<br>Иван</div>
        <span data-name="GeoLabel">р-н Арбат</span>
        <span data-name="GeoLabel">улица Арбат</span>
        <span data-name="GeoLabel">10</span>
    </article>'''


def pagination(next_page):
    if next_page is None:
        return '<nav data-name="Pagination"><a href="?p=1">Назад</a></nav>'
    return f'<nav data-name="Pagination"><a rel="next" href="?p={next_page}">Дальше</a></nav>'


def search_page(cards, *, recommendations="", next_page=None):
    return f'''<main data-name="SearchEngineResultsPageContainer">
        <div data-name="Offers">{cards}</div>
        <div data-name="SuggestionsLayout">{recommendations}</div>
    </main>{pagination(next_page)}'''


def catalog_response(url, pages, path="/cat.php"):
    if url.hostname != "cian.ru" or url.path != path:
        return None
    page = int(parse_qs(url.query)["p"][0])
    return (200, pages[page]) if page in pages else None


@pytest.mark.parametrize("kind", ["flat", "suburban"])
def test_public_collection_filters_recommendations_and_deduplicates_later_pages(routed_parser, kind):
    parser, serve, requests = routed_parser
    pages = {
        1: search_page(offer(kind, 100001), recommendations=offer(kind, 999999), next_page=2),
        2: search_page(offer(kind, 100001, tracking="?source=page2") + offer(kind, 100002)),
    }
    serve(lambda url: catalog_response(url, pages))

    settings = {"end_page": 5, "min_price": 10_000_000}
    if kind == "flat":
        result = parser.get_flats("sale", rooms=2, additional_settings=settings)
        assert all(row["rooms_count"] == 2 and row["total_meters"] == 55.8 for row in result)
    else:
        result = parser.get_suburban("house", "sale", additional_settings=settings)
        assert all(row["suburban_type"] == "house" for row in result)

    assert [row["url"] for row in result] == [
        f"https://www.cian.ru/sale/{kind}/100001/",
        f"https://www.cian.ru/sale/{kind}/100002/",
    ]
    assert all(row["price"] == 12_500_000 and row["author"] == "Иван" for row in result)
    assert all("price_per_month" not in row for row in result)
    queries = [parse_qs(url.query) for url in requests]
    assert [query["p"] for query in queries] == [["1"], ["2"]]
    assert all(query["region"] == ["1"] and query["minprice"] == ["10000000"] for query in queries)


def test_http_failure_retries_page_without_losing_records_or_repeating_details(routed_parser):
    parser, serve, requests = routed_parser
    attempts = {1: 0, 2: 0}
    pages = {
        1: search_page(offer("flat", 100001), next_page=2),
        2: search_page(offer("flat", 100002)),
    }
    detail = '''<main data-name="OfferCardPageLayout">
        <div><span>Жилая площадь</span><span>32,5 м²</span></div>
    </main>'''

    def response_for(url):
        if url.path == "/cat.php":
            page = int(parse_qs(url.query)["p"][0])
            if page in attempts:
                attempts[page] += 1
                if page == 2 and attempts[page] == 1:
                    return 503, "Service unavailable"
            return catalog_response(url, pages)
        if url.hostname == "www.cian.ru" and url.path in ("/sale/flat/100001/", "/sale/flat/100002/"):
            return 200, detail
        return None

    serve(response_for)
    result = parser.get_flats("sale", with_extra_data=True, additional_settings={"end_page": 5})
    assert attempts == {1: 1, 2: 2}
    assert [row["url"] for row in result] == [
        "https://www.cian.ru/sale/flat/100001/", "https://www.cian.ru/sale/flat/100002/",
    ]
    assert all(row["living_meters"] == "32,5 м²" and row["floor"] == 3 for row in result)
    assert [url.path for url in requests if url.path != "/cat.php"] == [
        "/sale/flat/100001/", "/sale/flat/100002/",
    ]


def test_page_two_http_captcha_preserves_partial_results_and_latest_csv(routed_parser, tmp_path, monkeypatch):
    parser, serve, requests = routed_parser
    monkeypatch.chdir(tmp_path)
    first_page = search_page(offer("flat", 100001) + offer("flat", 100002), next_page=2)

    def response_for(url):
        if url.hostname != "cian.ru" or url.path != "/cat.php":
            return None
        page = parse_qs(url.query)["p"][0]
        if page == "1":
            return 200, first_page
        if page == "2":
            return 403, '<form action="/captcha/"><h1>Подтвердите, что вы не робот</h1></form>'
        return None

    serve(response_for)
    with pytest.raises(CaptchaError) as exc_info:
        parser.get_flats("sale", with_saving_csv=True, additional_settings={"end_page": 5})
    partial = exc_info.value.partial_results
    assert [row["url"] for row in partial] == [
        "https://www.cian.ru/sale/flat/100001/", "https://www.cian.ru/sale/flat/100002/",
    ]
    assert [parse_qs(url.query)["p"] for url in requests] == [["1"], ["2"]]
    csv_files = list(tmp_path.glob("*.csv"))
    assert len(csv_files) == 1
    with csv_files[0].open(newline="", encoding="utf-8") as source:
        saved = list(csv.DictReader(source, delimiter=";"))
    assert saved == [{key: str(value) for key, value in row.items()} for row in partial]
    assert not list(tmp_path.glob("*.tmp"))


def newobject_card(url, name):
    return f'''<div data-mark="GKCard">
        <a data-mark="Link" href="/reviews/">Отзывы</a>
        <div data-testid="newbuildingTitle"><a href="{escape(url, quote=True)}">{name}</a></div>
        <div data-name="AddressLine">Москва, Арбат</div>
    </div>'''


NEWOBJECT_DETAIL = '''<div data-name="NewbuildingName"><h1>ЖК Пример</h1></div>
    <div><span data-testid="SpecificationTitle">Сдача</span><div data-testid="SpecificationValue">2027</div></div>
    <div><span data-testid="SpecificationTitle">Класс</span><div data-testid="SpecificationValue">Бизнес</div></div>
    <div><span data-testid="SpecificationTitle">Этажность</span><div data-testid="SpecificationValue">11–22</div></div>'''


def test_newobjects_preserve_paths_and_subdomains_and_stop_at_last_page(routed_parser):
    parser, serve, requests = routed_parser
    projects = [
        ("https://www.cian.ru/zhiloy-kompleks-first-101/", "Первый"),
        ("https://www.cian.ru/zhiloy-kompleks-second-102/", "Второй"),
        ("https://zhk-third.cian.ru/", "Третий"),
        ("https://zhk-fourth.cian.ru/", "Четвертый"),
    ]
    pages = {
        1: '<main data-name="OffersLayout">' + "".join(newobject_card(*project) for project in projects[:2])
           + "</main>" + pagination(2) + newobject_card("/unrelated/", "Рекомендация"),
        2: '<main data-name="OffersLayout">' + newobject_card(projects[0][0] + "?source=page2", projects[0][1])
           + "".join(newobject_card(*project) for project in projects[2:]) + "</main>" + pagination(None),
    }

    def response_for(url):
        if url.geturl() in {project[0] for project in projects}:
            return 200, NEWOBJECT_DETAIL
        return catalog_response(url, pages, path="/newobjects/list/")

    serve(response_for)
    result = parser.get_newobjects(additional_settings={"end_page": 5})
    assert [(row["url"], row["name"]) for row in result] == projects
    assert all(row["class"] == "Бизнес" and row["year_of_construction"] == "2027" for row in result)
    assert all(row["floors_from"] == 11 and row["floors_to"] == 22 for row in result)
    catalog = [url for url in requests if url.path == "/newobjects/list/"]
    assert [parse_qs(url.query)["p"] for url in catalog] == [["1"], ["2"]]
    assert [url.geturl() for url in requests if url.path != "/newobjects/list/"] == [project[0] for project in projects]


def test_newobject_public_page_limit_stops_before_next_catalog_page(routed_parser):
    parser, serve, requests = routed_parser
    project_url = "https://www.cian.ru/zhiloy-kompleks-first-101/"
    pages = {1: '<main data-name="OffersLayout">' + newobject_card(project_url, "Первый") + "</main>" + pagination(2)}
    serve(lambda url: (200, NEWOBJECT_DETAIL) if url.geturl() == project_url else catalog_response(url, pages, "/newobjects/list/"))
    result = parser.get_newobjects(additional_settings={"end_page": 1})
    assert [row["url"] for row in result] == [project_url]
    assert len(requests) == 2  # One catalog page and its detail page.


def test_repeated_daily_collections_isolate_site_storage_and_preserve_shared_context(routed_parser):
    parser, serve, requests = routed_parser

    def response_for(url):
        if url.hostname != "cian.ru":
            return None
        if url.path == "/shared/":
            return 200, "Shared browser page"
        if url.path != "/cat.php":
            return None
        query = parse_qs(url.query)
        kind = query["offer_type"][0]
        if query["type"] != ["2"] or kind not in ("flat", "suburban"):
            return None
        return 200, f'''<aside data-name="Sidebar">
            <div data-testid="OfferCard">
                <a href="/rent/{kind}/100001/">Объявление</a>
                <div data-name="Features">1-комн. квартира, 32,5 м², 4/15 этаж</div>
                <span data-testid="price">от 4 990 ₽/сут.</span>
            </div>
        </aside><script>
            if (localStorage.getItem('daily-search')) {{
                document.querySelector('aside').innerHTML =
                    '<div data-name="EmptyListing">Нет вариантов</div>';
            }}
            localStorage.setItem('daily-search', 'visited');
        </script>'''

    serve(response_for)
    manager = parser._browser
    chromium = manager._browser
    shared = manager._context
    shared_page = manager.new_page()
    try:
        manager.navigate(shared_page, "https://cian.ru/shared/")
        shared_page.evaluate("localStorage.setItem('daily-search', 'shared-state')")
        for kind in ("flat", "suburban", "flat"):
            if kind == "flat":
                result = parser.get_flats("rent_short", additional_settings={"end_page": 1})
            else:
                result = parser.get_suburban("house", "rent_short", additional_settings={"end_page": 1})
            assert len(result) == 1
            assert result[0]["url"] == f"https://www.cian.ru/rent/{kind}/100001/"
            assert result[0]["price_per_day"] == 4990
            assert chromium.contexts == [shared]
            assert manager._owned_contexts == set()
            assert shared_page.evaluate("localStorage.getItem('daily-search')") == "shared-state"
    finally:
        manager.close_page(shared_page)
    assert len(requests) == 4  # Shared page and three independent daily searches.


def test_daily_captcha_closes_owned_context_and_preserves_shared_browser(routed_parser):
    parser, serve, requests = routed_parser
    serve(lambda url: (403, '<form id="captcha">Подтвердите, что вы не робот</form>'))
    with pytest.raises(CaptchaError) as exc_info:
        parser.get_flats("rent_short", additional_settings={"end_page": 1})
    assert exc_info.value.partial_results == []
    assert len(requests) == 1
    assert parser._browser._owned_contexts == set()
    assert parser._browser._browser.contexts == [parser._browser._context]
