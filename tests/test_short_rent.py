from unittest.mock import Mock

import pytest
from playwright.sync_api import Locator, sync_playwright, TimeoutError as PlaywrightTimeoutError

from cian_parser.flat.list_parser import FlatListParser
from cian_parser.suburban.list_parser import SuburbanListParser
from cian_parser.exceptions import CaptchaError


def daily_card(listing_id="101", accommodation_type="flat"):
    return f'''<div data-name="OfferCardHorizontal" data-testid="OfferCard">
        <a href="/rent/{accommodation_type}/{listing_id}/">Открыть</a>
        <div data-name="Features"><span>1-комн. квартира</span><span>32,5 м²</span><span>4/15 этаж</span></div>
        <div data-name="Price"><span data-testid="price">от 4 990 ₽/сут.</span></div>
        <span data-name="Address">Москва, Ходынский бульвар, 2</span>
        <div><i data-name="UndergroundIcon"></i><span>ЦСКА</span><span data-name="GeoTravelTime">5 мин.</span></div>
    </div>'''


def sidebar(contents, *, disabled=False):
    return f'''<aside data-name="Sidebar">{contents}
        <footer data-name="ListingDesktopFooter">
            <button disabled>Назад</button><button {'disabled' if disabled else ''}>Дальше</button>
        </footer></aside>'''


@pytest.fixture
def html_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser.new_page()
        finally:
            browser.close()


def make_parser(browser=None, *, start_page=1, end_page=1, suburban=False):
    parser_class = SuburbanListParser if suburban else FlatListParser
    return parser_class(
        browser or Mock(), "suburban" if suburban else "flat", "rent", 2, "Москва",
        additional_settings={"start_page": start_page, "end_page": end_page},
        object_type="house" if suburban else None,
    )


@pytest.mark.parametrize("suburban", [False, True])
def test_daily_cards_preserve_schema_and_extract_starting_nightly_rate(html_page, suburban):
    kind = "suburban" if suburban else "flat"
    html_page.set_content(sidebar(daily_card(accommodation_type=kind)))
    parser = make_parser(suburban=suburban)
    card = html_page.query_selector("[data-testid='OfferCard']")
    parser._process_card(card)
    record = parser.result[0]
    assert record["url"] == f"https://www.cian.ru/rent/{kind}/101/"
    assert record["price_per_day"] == 4990
    assert record["street"] == "Ходынский бульвар"
    assert record["house_number"] == "2"
    assert record["underground"] == "ЦСКА"
    assert record["author"] == record["author_type"] == ""
    assert not {"price", "price_per_month", "commissions"} & record.keys()
    if suburban:
        assert record["suburban_type"] == "house"
    else:
        assert (record["rooms_count"], record["floor"], record["floors_count"], record["total_meters"]) == (1, 4, 15, 32.5)


def test_daily_search_waits_for_cards_after_sidebar_shell(html_page):
    html_page.set_content('<aside data-name="Sidebar"></aside>')
    html_page.evaluate("html => setTimeout(() => document.querySelector('aside').innerHTML = html, 100)", daily_card())
    assert len(make_parser()._get_cards(html_page)) == 1


def test_daily_search_recognizes_observed_empty_state(html_page):
    html_page.set_content(sidebar('<div data-name="EmptyListing">Нет вариантов по вашему запросу</div>', disabled=True))
    parser = make_parser()
    assert parser._get_cards(html_page) == []
    assert not parser._has_next_page(html_page, 1)


def install_pages(page, *, count=3, delay=0):
    page.set_content(sidebar(daily_card()))
    page.evaluate("""({count, delay}) => {
        window.dailyPage = 1;
        window.nextClicks = 0;
        const next = document.querySelector('footer button:last-child');
        next.addEventListener('click', () => {
            window.nextClicks += 1;
            next.disabled = true;
            setTimeout(() => {
                window.dailyPage += 1;
                document.querySelector('[data-testid="OfferCard"] a').href = '/rent/flat/' + (100 + window.dailyPage) + '/';
                next.disabled = window.dailyPage >= count;
            }, delay);
        });
    }""", {"count": count, "delay": delay})


def test_daily_navigation_walks_start_page_and_does_not_advance_on_retry(html_page):
    from cian_parser.short_rent import ShortRentNavigation

    browser = Mock()
    browser.navigate.side_effect = lambda page, url: install_pages(page)
    navigation = ShortRentNavigation()
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 2)
    assert html_page.evaluate("window.dailyPage") == 2
    assert html_page.evaluate("window.nextClicks") == 1
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 2)
    assert html_page.evaluate("window.nextClicks") == 1
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 3)
    assert html_page.evaluate("window.dailyPage") == 3
    assert not navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 4)
    assert html_page.evaluate("window.nextClicks") == 2
    browser.navigate.assert_called_once()


def test_delayed_next_transition_is_reconciled_without_second_click(html_page):
    from cian_parser.short_rent import ShortRentNavigation

    browser = Mock()
    browser.navigate.side_effect = lambda page, url: install_pages(page, delay=500)
    navigation = ShortRentNavigation(timeout=250)
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 1)
    with pytest.raises(PlaywrightTimeoutError):
        navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 2)
    html_page.wait_for_timeout(600)
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 2)
    assert html_page.evaluate("window.dailyPage") == 2
    assert html_page.evaluate("window.nextClicks") == 1


def test_covered_next_action_can_retry_when_no_click_was_dispatched(html_page):
    from cian_parser.short_rent import ShortRentNavigation

    browser = Mock()
    browser.navigate.side_effect = lambda page, url: install_pages(page)
    navigation = ShortRentNavigation(timeout=250)
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 1)
    html_page.evaluate("""() => {
        const cover = document.createElement('div');
        cover.id = 'cover';
        cover.style = 'position:fixed;inset:0;z-index:99999;background:white';
        document.body.append(cover);
    }""")
    with pytest.raises(PlaywrightTimeoutError):
        navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 2)
    assert html_page.evaluate("window.nextClicks") == 0
    html_page.locator("#cover").evaluate("element => element.remove()")
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 2)
    assert html_page.evaluate("window.dailyPage") == 2
    assert html_page.evaluate("window.nextClicks") == 1


def test_detached_next_action_can_retry_when_button_returns(html_page, monkeypatch):
    from cian_parser.short_rent import ShortRentNavigation

    browser = Mock()
    browser.navigate.side_effect = lambda page, url: install_pages(page)
    navigation = ShortRentNavigation(timeout=250)
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 1)
    original_click = Locator.click
    detached = False

    def detach_before_action(locator, *args, **kwargs):
        nonlocal detached
        if not detached:
            detached = True
            locator.evaluate("button => { window.detachedNext = button; button.remove(); }")
        return original_click(locator, *args, **kwargs)

    monkeypatch.setattr(Locator, "click", detach_before_action)
    with pytest.raises(PlaywrightTimeoutError):
        navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 2)
    assert html_page.evaluate("window.nextClicks") == 0
    html_page.evaluate("document.querySelector('footer').append(window.detachedNext)")
    assert navigation.navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 2)
    assert html_page.evaluate("window.dailyPage") == 2
    assert html_page.evaluate("window.nextClicks") == 1


def test_daily_collection_honors_exact_bound_without_extra_click(html_page, monkeypatch):
    browser = Mock()
    browser.navigate.side_effect = lambda page, url: install_pages(page, count=4)
    browser.new_page.return_value = html_page
    monkeypatch.setattr(html_page, "wait_for_timeout", lambda _: None)
    monkeypatch.setattr("cian_parser.base_list.time.sleep", lambda _: None)
    parser = make_parser(browser, start_page=2, end_page=3)
    monkeypatch.setattr("cian_parser.base_list.close_page", lambda _: None)
    result = parser.run("https://www.cian.ru/cat.php?p={}")
    assert [row["url"] for row in result] == [
        "https://www.cian.ru/rent/flat/102/", "https://www.cian.ru/rent/flat/103/",
    ]
    assert html_page.evaluate("window.nextClicks") == 2
    browser.navigate.assert_called_once()


def test_challenge_during_next_transition_preserves_partial_results(html_page, monkeypatch):
    browser = Mock()

    def load_page(page, url):
        page.set_content(sidebar(daily_card()))
        page.evaluate("""() => {
            window.nextClicks = 0;
            document.querySelector('footer button:last-child').addEventListener('click', () => {
                window.nextClicks += 1;
                setTimeout(() => document.body.innerHTML = '<form id="captcha">Подтвердите, что вы не робот</form>', 40);
            });
        }""")

    browser.navigate.side_effect = load_page
    browser.new_page.return_value = html_page
    monkeypatch.setattr(html_page, "wait_for_timeout", lambda _: None)
    monkeypatch.setattr("cian_parser.base_list.time.sleep", lambda _: None)
    monkeypatch.setattr("cian_parser.base_list.close_page", lambda _: None)
    parser = make_parser(browser, end_page=2)
    parser._short_rent.timeout = 300
    with pytest.raises(CaptchaError) as error:
        parser.run("https://www.cian.ru/cat.php?p={}")
    assert [record["url"] for record in error.value.partial_results] == ["https://www.cian.ru/rent/flat/101/"]
    assert error.value.partial_results is not parser.result
    assert html_page.evaluate("window.nextClicks") == 1
    browser.navigate.assert_called_once()


@pytest.mark.parametrize("initial", ['<h1>Загрузка</h1>', '<aside data-name="Sidebar"></aside>'])
def test_challenge_while_initial_search_loads_is_not_hidden_by_timeout(html_page, initial):
    from cian_parser.short_rent import ShortRentNavigation

    browser = Mock()

    def load_page(page, url):
        page.set_content(initial)
        page.evaluate("setTimeout(() => document.body.innerHTML = '<form id=\"captcha\">Captcha</form>', 40)")

    browser.navigate.side_effect = load_page
    with pytest.raises(CaptchaError):
        ShortRentNavigation(timeout=100).navigate(browser, html_page, "https://www.cian.ru/cat.php?p={}", 1)

@pytest.mark.parametrize("hidden", [True, False])
def test_result_cards_take_precedence_over_stale_empty_state(html_page, hidden):
    empty = '<div data-name="EmptyListing" ' + ('hidden' if hidden else '') + '>Empty</div>'
    html_page.set_content(sidebar(empty + daily_card()))
    parser = make_parser()
    assert len(parser._get_cards(html_page)) == 1
    assert parser._has_next_page(html_page, 1)


def test_hidden_empty_state_alone_does_not_finish_search(html_page):
    from cian_parser.short_rent import ShortRentNavigation

    html_page.set_content(sidebar('<div data-name="EmptyListing" hidden>Empty</div>'))
    with pytest.raises(PlaywrightTimeoutError):
        ShortRentNavigation(timeout=100).cards(html_page)


def test_visible_loading_skeleton_prevents_temporary_empty_result(html_page):
    html_page.set_content(sidebar('<div data-name="EmptyListing">Empty</div><div data-name="ListingSkeleton">Loading</div>'))
    html_page.evaluate("html => setTimeout(() => document.querySelector('aside').innerHTML = html, 100)", daily_card())
    assert len(make_parser()._get_cards(html_page)) == 1


def test_next_transition_does_not_stop_at_temporary_empty_state(html_page, monkeypatch):
    browser = Mock()

    def load_page(page, url):
        page.set_content(sidebar(daily_card()))
        page.evaluate("""markup => {
            window.nextClicks = 0;
            document.querySelector('footer button:last-child').addEventListener('click', () => {
                window.nextClicks += 1;
                const sidebar = document.querySelector('aside');
                sidebar.innerHTML = '<div data-name="EmptyListing">Empty</div><div data-name="ListingSkeleton">Loading</div>';
                setTimeout(() => sidebar.innerHTML = markup, 150);
            });
        }""", daily_card(listing_id="102"))

    browser.navigate.side_effect = load_page
    browser.new_page.return_value = html_page
    monkeypatch.setattr(html_page, "wait_for_timeout", lambda _: None)
    monkeypatch.setattr("cian_parser.base_list.time.sleep", lambda _: None)
    monkeypatch.setattr("cian_parser.base_list.close_page", lambda _: None)
    parser = make_parser(browser, end_page=2)
    result = parser.run("https://www.cian.ru/cat.php?p={}")
    assert [row["url"] for row in result] == [
        "https://www.cian.ru/rent/flat/101/", "https://www.cian.ru/rent/flat/102/",
    ]
    assert html_page.evaluate("window.nextClicks") == 1
