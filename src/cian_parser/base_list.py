from __future__ import annotations

import logging
import random
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page

from cian_parser.browser import BrowserManager
from cian_parser.csv_saver import save_to_csv
from cian_parser.constants import SPECIFIC_FIELDS_FOR_RENT_LONG, SPECIFIC_FIELDS_FOR_RENT_SHORT, SPECIFIC_FIELDS_FOR_SALE
from cian_parser.exceptions import CaptchaError, CianParserError
from cian_parser.helpers import define_deal_url_id
from cian_parser.page_utils import close_page, raise_for_captcha
from cian_parser.short_rent import SIDEBAR, ShortRentNavigation

logger = logging.getLogger("cian_parser")


class BaseListParser:
    def __init__(
        self,
        browser: BrowserManager,
        accommodation_type: str,
        deal_type: str,
        rent_period_type: int | None,
        location_name: str,
        with_saving_csv: bool = False,
        with_extra_data: bool = False,
        additional_settings: dict[str, Any] | None = None,
        object_type: str | None = None,
    ):
        self.browser = browser
        self.accommodation_type = accommodation_type
        self.deal_type = deal_type
        self.rent_period_type = rent_period_type
        self.location_name = location_name
        self.with_saving_csv = with_saving_csv
        self.with_extra_data = with_extra_data
        self.additional_settings = additional_settings
        self.object_type = object_type
        self._short_rent = ShortRentNavigation() if self.is_rent_short() else None

        self.result: list[dict[str, Any]] = []
        self.result_set: set[str] = set()
        self.count_parsed_offers = 0
        self.start_page = 1 if (additional_settings is None or "start_page" not in additional_settings) else additional_settings["start_page"]
        self.end_page = 100 if (additional_settings is None or "end_page" not in additional_settings) else additional_settings["end_page"]
        self.file_path = self.build_file_path()

    def is_sale(self) -> bool:
        return self.deal_type == "sale"

    def is_rent_long(self) -> bool:
        return self.deal_type == "rent" and self.rent_period_type == 4

    def is_rent_short(self) -> bool:
        return self.deal_type == "rent" and self.rent_period_type == 2

    def build_file_path(self) -> str:
        raise NotImplementedError

    def parse_card(self, card: Any) -> dict[str, Any]:
        raise NotImplementedError

    def parse_detail_page(self, url: str) -> dict[str, Any]:
        raise NotImplementedError

    def remove_unnecessary_fields(self, record: dict[str, Any]) -> dict[str, Any]:
        if self.is_sale():
            for field in SPECIFIC_FIELDS_FOR_RENT_LONG | SPECIFIC_FIELDS_FOR_RENT_SHORT:
                record.pop(field, None)
        elif self.is_rent_long():
            for field in SPECIFIC_FIELDS_FOR_RENT_SHORT | SPECIFIC_FIELDS_FOR_SALE:
                record.pop(field, None)
        elif self.is_rent_short():
            for field in SPECIFIC_FIELDS_FOR_RENT_LONG | SPECIFIC_FIELDS_FOR_SALE:
                record.pop(field, None)
        return record

    def run(self, url_format: str) -> list[dict[str, Any]]:
        """Run pagination loop. Returns collected results."""
        isolated = self.is_rent_short()
        page = self.browser.new_page(isolated=True) if isolated else self.browser.new_page()

        try:
            self._paginate(page, url_format)
        except CaptchaError as exc:
            exc.partial_results = list(self.result)
            raise
        finally:
            if isolated:
                self.browser.close_page(page)
            else:
                close_page(page)

        return self.result

    def _paginate(self, page: Page, url_format: str) -> None:
        logger.info("Starting collection from page %d to %d", self.start_page, self.end_page)

        if self.with_saving_csv:
            logger.info("CSV will be saved to: %s", self.file_path)

        page_number = self.start_page - 1

        while page_number < self.end_page:
            page_number += 1
            attempt = 0
            page_parsed = False

            while attempt < 3 and not page_parsed:
                try:
                    page_parsed, should_stop = self._parse_page(page, url_format, page_number, attempt)
                    if should_stop:
                        return
                except CaptchaError:
                    raise
                except Exception as exc:
                    attempt += 1
                    delay = attempt * 5
                    if attempt >= 3:
                        logger.error("Failed to parse page %d after 3 attempts: %s", page_number, exc)
                        raise
                    logger.warning("Error on page %d (attempt %d/3): %s. Retrying in %ds...", page_number, attempt, exc, delay)
                    time.sleep(delay)

        logger.info("Collection complete. Total parsed: %d", self.count_parsed_offers)

    def _parse_page(self, page: Page, url_format: str, page_number: int, attempt: int) -> tuple[bool, bool]:
        """Parse a single list page. Returns (page_parsed, should_stop)."""
        url = url_format.format(page_number)

        if page_number == self.start_page and attempt == 0:
            logger.info("Starting URL: %s", url)

        if self._short_rent is not None:
            if not self._short_rent.navigate(self.browser, page, url_format, page_number):
                return True, True
        else:
            self.browser.navigate(page, url)
        page.wait_for_timeout(random.randint(3000, 5000))

        # Scroll to load lazy content
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        page.wait_for_timeout(1000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

        raise_for_captcha(page, self.result)

        cards = self._get_cards(page)
        if not cards:
            logger.info("No cards found on page %d, stopping.", page_number)
            return True, True

        logger.info("Page %d: %d cards found", page_number, len(cards))

        for card in cards:
            self._process_card(card)

        logger.info("Total parsed so far: %d", self.count_parsed_offers)

        if page_number >= self.end_page:
            return True, True

        # Check pagination
        has_next = self._has_next_page(page, page_number)
        if not has_next:
            logger.info("Last page reached (%d).", page_number)
            return True, True

        time.sleep(random.uniform(2, 4))
        return True, False

    def _get_cards(self, page: Page) -> list:
        if self._short_rent is not None and page.query_selector(SIDEBAR) is not None:
            return self._short_rent.cards(page)
        container = page.query_selector("[data-name='SearchEngineResultsPageContainer']")
        if container is None:
            raise RuntimeError("Search results container is missing; refusing to return an empty result")
        # Suggestions can ignore the requested location, price and property type.
        return container.query_selector_all("[data-name='Offers'] article[data-name='CardComponent']")

    def _has_next_page(self, page: Page, current_page: int) -> bool:
        if self._short_rent is not None and page.query_selector(SIDEBAR) is not None:
            return self._short_rent.has_next(page)
        pag = page.query_selector("[data-name='Pagination']")
        if not pag:
            return False

        next_btn = pag.query_selector("[class*='--next--'], [rel='next']")
        if next_btn and next_btn.get_attribute("disabled") is None and next_btn.get_attribute("aria-disabled") != "true":
            return True

        for link in pag.query_selector_all("a[href]"):
            if link.get_attribute("aria-disabled") == "true":
                continue
            query = parse_qs(urlsplit(link.get_attribute("href") or "").query)
            if any(value.isdigit() and int(value) > current_page for value in query.get("p", [])):
                return True

        page_links = pag.query_selector_all("li")
        last_page = current_page
        for pl in page_links:
            txt = pl.inner_text().strip()
            if txt.isdigit():
                last_page = max(last_page, int(txt))

        return current_page < last_page

    def _process_card(self, card: Any) -> None:
        card_data = self.parse_card(card)
        url = card_data.get("url", "")

        if not url:
            raise CianParserError("Listing card has no URL; collection would be incomplete")

        url_id = self._record_key(url)
        if url_id in self.result_set:
            return

        page_data: dict[str, Any] = {}
        if self.with_extra_data:
            page_data = self.parse_detail_page(url)
            time.sleep(4)

        # Merge detail data without overwriting valid card-level values with sentinels
        for key, value in page_data.items():
            if key in card_data and card_data[key] not in (-1, "", None):
                # Only overwrite if detail value is also non-sentinel
                if value in (-1, "", None):
                    continue
            card_data[key] = value
        card_data = self.remove_unnecessary_fields(card_data)
        if self.with_saving_csv:
            save_to_csv([*self.result, card_data], str(self.file_path))

        self.result_set.add(url_id)
        self.result.append(card_data)
        self.count_parsed_offers += 1

    def _record_key(self, url: str) -> str:
        url_id = define_deal_url_id(url)
        return url_id if url_id != "-1" else urlsplit(url)._replace(query="", fragment="").geturl()
