from __future__ import annotations

import pathlib
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Page

from cian_parser.base_list import BaseListParser
from cian_parser.browser import BrowserManager
from cian_parser.constants import FILE_NAME_NEWOBJECT_FORMAT
from cian_parser.newobject.page_parser import NewObjectDetailParser


class NewObjectListParser(BaseListParser):
    """Collect residential developments with the shared retry/cleanup lifecycle."""

    def __init__(
        self, browser: BrowserManager, location_name: str, with_saving_csv: bool = False,
        *, additional_settings: dict[str, Any] | None = None,
    ):
        settings = {"end_page": 50}
        if additional_settings is not None:
            settings.update(additional_settings)
        super().__init__(
            browser, "newobject", "sale", None, location_name,
            with_saving_csv=with_saving_csv, with_extra_data=True,
            additional_settings=settings,
        )

    def build_file_path(self) -> str:
        now_time = datetime.now().strftime("%d_%b_%Y_%H_%M_%S_%f")
        file_name = FILE_NAME_NEWOBJECT_FORMAT.format(
            self.accommodation_type, self.location_name.lower(), now_time,
        )
        return str(pathlib.Path.cwd() / file_name.replace("'", ""))

    def _get_cards(self, page: Page) -> list:
        container = page.query_selector("[data-name='OffersLayout']")
        if container is None:
            raise RuntimeError("Newbuilding results container is missing; refusing to return an empty result")
        return container.query_selector_all("[data-mark='GKCard']")

    def parse_card(self, card: Any) -> dict[str, Any]:
        link = card.query_selector("[data-testid='newbuildingTitle'] a[href]")
        if link is None:
            link = card.query_selector("[data-name='NewbuildingInfo'] a[href]")
        if link is None:
            link = card.query_selector("a[data-mark='Link']")
        href = link.get_attribute("href") if link else ""
        url = urlsplit(urljoin("https://www.cian.ru", href))._replace(query="", fragment="").geturl() if href else ""
        name = link.inner_text().strip() if link else ""
        if not name:
            name_el = card.query_selector("span[data-mark='Text']")
            name = name_el.inner_text().strip() if name_el else ""
        address = card.query_selector("[data-name='AddressLine'], [data-testid='CellAddressBlock'], [data-mark='CellAddressBlock']")
        return {
            "name": name,
            "location": self.location_name,
            "accommodation_type": self.accommodation_type,
            "url": url,
            "full_full_location_address": address.inner_text().strip() if address else "",
        }

    def parse_detail_page(self, url: str) -> dict[str, Any]:
        return NewObjectDetailParser(self.browser).parse(url, partial_results=list(self.result))

    def remove_unnecessary_fields(self, record: dict[str, Any]) -> dict[str, Any]:
        return record

    def _record_key(self, url: str) -> str:
        return urlsplit(url)._replace(query="", fragment="").geturl().rstrip("/")
