from __future__ import annotations

import csv
import logging
import pathlib
import random
import time
import urllib.parse
from datetime import datetime
from typing import Any

from playwright.sync_api import Page

from cian_parser.browser import BrowserManager
from cian_parser.constants import FILE_NAME_NEWOBJECT_FORMAT
from cian_parser.csv_saver import save_to_csv
from cian_parser.exceptions import CaptchaError
from cian_parser.helpers import union_dicts

logger = logging.getLogger("cian_parser")


class NewObjectListParser:
    """Parser for new construction objects. Separate from BaseListParser due to different card structure."""

    def __init__(
        self,
        browser: BrowserManager,
        location_name: str,
        with_saving_csv: bool = False,
    ):
        self.browser = browser
        self.accommodation_type = "newobject"
        self.deal_type = "sale"
        self.location_name = location_name
        self.with_saving_csv = with_saving_csv

        self.result: list[dict[str, Any]] = []
        self.result_set: set[str] = set()
        self.count_parsed_offers = 0
        self.start_page = 1
        self.end_page = 50
        self.file_path = self._build_file_path()

    def _build_file_path(self) -> str:
        now_time = datetime.now().strftime("%d_%b_%Y_%H_%M_%S_%f")
        file_name = FILE_NAME_NEWOBJECT_FORMAT.format(
            self.accommodation_type,
            self.location_name.lower(),
            now_time,
        )
        return str(pathlib.Path(pathlib.Path.cwd(), file_name.replace("'", "")))

    def run(self, url_format: str) -> list[dict[str, Any]]:
        page = self.browser.new_page()
        try:
            self._paginate(page, url_format)
        finally:
            page.close()
        return self.result

    def _paginate(self, page: Page, url_format: str) -> None:
        logger.info("Starting newobject collection from page %d to %d", self.start_page, self.end_page)

        for page_number in range(self.start_page, self.end_page + 1):
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
                    logger.warning("Error on page %d (attempt %d/3): %s", page_number, attempt, exc)
                    if attempt >= 3:
                        logger.error("Failed to parse page %d after 3 attempts", page_number)
                        return
                    time.sleep(delay)

        logger.info("Newobject collection complete. Total parsed: %d", self.count_parsed_offers)

    def _parse_page(self, page: Page, url_format: str, page_number: int, attempt: int) -> tuple[bool, bool]:
        url = url_format.format(page_number)

        if page_number == self.start_page and attempt == 0:
            logger.info("Starting URL: %s", url)

        self.browser.navigate(page, url)
        page.wait_for_timeout(random.randint(3000, 5000))

        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        page.wait_for_timeout(1000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

        page_text = page.inner_text("body")
        if "Captcha" in page_text or "captcha" in page_text:
            logger.warning("CAPTCHA detected on page %d", page_number)
            raise CaptchaError(
                f"CAPTCHA detected on page {page_number}",
                partial_results=list(self.result),
            )

        cards = page.query_selector_all("div[data-mark='GKCard']")
        if not cards:
            logger.info("No newobject cards found on page %d, stopping.", page_number)
            return True, True

        logger.info("Page %d: %d newobject cards found", page_number, len(cards))

        for card in cards:
            self._process_card(card)

        time.sleep(random.uniform(2, 4))
        return True, False

    def _process_card(self, card: Any) -> None:
        common_data: dict[str, Any] = {}

        name_el = card.query_selector("span[data-mark='Text']")
        common_data["name"] = name_el.inner_text().strip() if name_el else ""

        common_data["location"] = self.location_name
        common_data["accommodation_type"] = self.accommodation_type

        link_el = card.query_selector("a[data-mark='Link']")
        if link_el:
            href = link_el.get_attribute("href") or ""
            parsed = urllib.parse.urlparse(href)
            common_data["url"] = f"https://{parsed.netloc}" if parsed.netloc else href
        else:
            common_data["url"] = ""

        address_el = card.query_selector("div[data-mark='CellAddressBlock']")
        common_data["full_full_location_address"] = address_el.inner_text().strip() if address_el else ""

        if not common_data["url"] or common_data["url"] in self.result_set:
            return

        from cian_parser.newobject.page_parser import NewObjectDetailParser
        detail_parser = NewObjectDetailParser(self.browser)
        page_data = detail_parser.parse(common_data["url"], partial_results=list(self.result))
        time.sleep(4)

        self.result_set.add(common_data["url"])
        self.count_parsed_offers += 1
        self.result.append(union_dicts(common_data, page_data))

        if self.with_saving_csv:
            save_to_csv(self.result, str(self.file_path))
