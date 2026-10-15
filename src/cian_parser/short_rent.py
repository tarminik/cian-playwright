from __future__ import annotations

import re
from typing import Any

from playwright.sync_api import ElementHandle, Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from cian_parser.browser import BrowserManager
from cian_parser.exceptions import CianParserError
from cian_parser.helpers import _is_street, define_author, define_rooms_count
from cian_parser.page_utils import raise_for_captcha

SIDEBAR = "[data-name='Sidebar']"
CARDS = SIDEBAR + " [data-testid='OfferCard']"
EMPTY = SIDEBAR + " [data-name='EmptyListing']"
FOOTER = SIDEBAR + " [data-name='ListingDesktopFooter']"
SKELETON = SIDEBAR + " [data-name='ListingSkeleton']"
_SELECTORS = {"cards": CARDS, "empty": EMPTY, "skeleton": SKELETON}

# A Sidebar is mounted before its asynchronous search has produced any results.
_RESULT_STATE = """({cards, empty, skeleton}) => {
    const visible = element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && getComputedStyle(element).visibility === 'visible';
    };
    return {
        loading: [...document.querySelectorAll(skeleton)].some(visible),
        empty: [...document.querySelectorAll(empty)].some(visible),
        cards: [...document.querySelectorAll(cards)].filter(visible).map(card =>
            card.querySelector('a[href*="/rent/"]')?.getAttribute('href')).filter(Boolean),
    };
}"""
_READY = "args => { const state = (" + _RESULT_STATE + ")(args); return !state.loading && (state.cards.length > 0 || state.empty); }"
_SIGNATURE = "args => (" + _RESULT_STATE + ")(args).cards"
_CHANGED = "args => { const state = (" + _RESULT_STATE + """\n)(args);
    if (state.loading) return false;
    if (state.cards.length > 0) return JSON.stringify(state.cards) !== JSON.stringify(args.previous);
    return state.empty;
}"""


class ShortRentNavigation:
    """Track daily search pages whose Next button does not change the URL."""

    def __init__(self, timeout: int = 15000):
        self.timeout = timeout
        self._page: Page | None = None
        self._modern = False
        self._current_page = 1
        self._pending_signature: list[str] | None = None

    def _wait_ready(self, page: Page) -> None:
        raise_for_captcha(page)
        try:
            page.wait_for_function(_READY, arg=_SELECTORS, timeout=self.timeout)
        except PlaywrightTimeoutError:
            raise_for_captcha(page)
            raise
        raise_for_captcha(page)

    def cards(self, page: Page) -> list[ElementHandle]:
        self._wait_ready(page)
        return [card for card in page.query_selector_all(CARDS) if card.is_visible()]

    def has_next(self, page: Page) -> bool:
        if not self.cards(page):
            return False
        button = page.locator(FOOTER).get_by_role("button", name="Дальше", exact=True)
        if button.count() != 1:
            raise CianParserError("Daily rental pagination controls are missing; collection may be incomplete")
        return not button.is_disabled()

    def _finish_pending(self, page: Page) -> None:
        # Keep pending state on a timeout. A retry must observe completion of the
        # original click rather than click again and silently skip a result page.
        try:
            page.wait_for_function(
                _CHANGED,
                arg={**_SELECTORS, "previous": self._pending_signature},
                timeout=self.timeout,
            )
        except PlaywrightTimeoutError:
            raise_for_captcha(page)
            raise
        raise_for_captcha(page)
        self._current_page += 1
        self._pending_signature = None

    def _click_next(self, page: Page) -> None:
        # Actionability can time out before any click is sent. Track dispatch
        # separately from result rendering so that only real clicks stay pending.
        tracker = page.evaluate_handle("""footerSelector => {
            const state = {dispatched: false};
            const listener = event => {
                const button = event.target.closest?.('button');
                if (button?.closest(footerSelector) && button.textContent.trim() === 'Дальше') {
                    state.dispatched = true;
                }
            };
            document.addEventListener('click', listener, true);
            state.dispose = () => document.removeEventListener('click', listener, true);
            return state;
        }""", FOOTER)
        try:
            self._pending_signature = page.evaluate(_SIGNATURE, _SELECTORS)
            try:
                page.locator(FOOTER).get_by_role("button", name="Дальше", exact=True).click(timeout=self.timeout)
            except PlaywrightTimeoutError:
                try:
                    dispatched = tracker.evaluate("state => state.dispatched")
                except PlaywrightError:
                    # A destroyed execution context leaves dispatch uncertain;
                    # retain pending state rather than risk skipping a page.
                    dispatched = True
                if not dispatched:
                    self._pending_signature = None
                raise_for_captcha(page)
                raise
        finally:
            try:
                tracker.evaluate("state => state.dispose()")
            except PlaywrightError:
                pass
            try:
                tracker.dispose()
            except PlaywrightError:
                pass

    def navigate(self, browser: BrowserManager, page: Page, url_format: str, page_number: int) -> bool:
        if self._page is not page:
            browser.navigate(page, url_format.format(page_number))
            raise_for_captcha(page)
            try:
                layout = page.wait_for_selector(
                    SIDEBAR + ", [data-name='SearchEngineResultsPageContainer']",
                    state="attached", timeout=self.timeout,
                )
            except PlaywrightTimeoutError:
                raise_for_captcha(page)
                raise
            self._modern = layout.get_attribute("data-name") == "Sidebar"
            if self._modern:
                self._wait_ready(page)
            self._page = page
            self._current_page = 1 if self._modern else page_number
            self._pending_signature = None
        elif not self._modern:
            browser.navigate(page, url_format.format(page_number))

        if not self._modern:
            return True

        if self._pending_signature is not None:
            self._finish_pending(page)
        if page_number < self._current_page:
            raise CianParserError("Daily rental pagination cannot move backwards during collection")
        while self._current_page < page_number:
            if not self.has_next(page):
                return False
            self._click_next(page)
            self._finish_pending(page)
        return True


def is_short_rent_card(card: ElementHandle) -> bool:
    return card.get_attribute("data-testid") == "OfferCard"


def extract_short_rent_card(card: ElementHandle, *, flat: bool) -> dict[str, Any]:
    """Extract the current daily-card fields, retaining existing output schemas."""
    result: dict[str, Any] = {
        **define_author(card),
        "price_per_day": -1,
        "district": "",
        "street": "",
        "house_number": "",
        "underground": "",
    }
    price = card.query_selector("[data-testid='price']")
    if price:
        match = re.search(r"(\d[\d\s]*)\s*₽\s*/\s*сут", price.inner_text())
        if match:
            result["price_per_day"] = int("".join(match.group(1).split()))

    address = card.query_selector("[data-name='Address']")
    if address:
        parts = [part.strip() for part in address.inner_text().split(",")]
        for index, part in enumerate(parts):
            if "р-н" in part or "поселение" in part:
                result["district"] = part.replace("р-н", "").strip() if flat else part
            if not result["street"] and _is_street(part):
                result["street"] = part.replace("улица", "").strip() if flat else part
                if index + 1 < len(parts) and any(character.isdigit() for character in parts[index + 1]):
                    result["house_number"] = parts[index + 1]

    metro_icon = card.query_selector("[data-name='UndergroundIcon']")
    if metro_icon:
        parent = metro_icon.query_selector("xpath=..")
        if parent:
            result["underground"] = parent.evaluate("""element => {
                const clone = element.cloneNode(true);
                clone.querySelectorAll('[data-name="UndergroundIcon"], [data-name="GeoTravelTime"]')
                    .forEach(node => node.remove());
                return clone.textContent.trim();
            }""")

    if flat:
        result.update({"floor": -1, "floors_count": -1, "rooms_count": -1, "total_meters": -1})
        features = card.query_selector("[data-name='Features']")
        if features:
            text = features.inner_text()
            result["rooms_count"] = define_rooms_count(text)
            area = re.search(r"(\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?)\s*м[²2]", text)
            if area:
                result["total_meters"] = float("".join(area.group(1).split()).replace(",", "."))
            floor = re.search(r"(\d+)\s*/\s*(\d+)\s*эт", text, re.IGNORECASE)
            if floor:
                result["floor"], result["floors_count"] = map(int, floor.groups())
    return result
