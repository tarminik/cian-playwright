from __future__ import annotations

import pathlib
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from cian_parser.base_list import BaseListParser
from cian_parser.constants import FILE_NAME_SUBURBAN_FORMAT
from cian_parser.helpers import union_dicts, define_author, parse_location_data, define_price_data
from cian_parser.short_rent import extract_short_rent_card, is_short_rent_card


class SuburbanListParser(BaseListParser):
    def build_file_path(self) -> str:
        now_time = datetime.now().strftime("%d_%b_%Y_%H_%M_%S_%f")
        file_name = FILE_NAME_SUBURBAN_FORMAT.format(
            self.accommodation_type, self.object_type, self.deal_type,
            self.start_page, self.end_page,
            self.location_name.lower(),
            now_time,
        )
        return str(pathlib.Path(pathlib.Path.cwd(), file_name.replace("'", "")))

    def parse_card(self, card: Any) -> dict[str, Any]:
        common_data: dict[str, Any] = {}

        link = card.query_selector("a[data-name='LinkArea'], [data-name='LinkArea'] a[href*='/suburban/']")
        if not link:
            link = card.query_selector("a[href*='/suburban/']")
        href = link.get_attribute("href") if link else ""
        common_data["url"] = urljoin("https://www.cian.ru", href) if href else ""
        common_data["location"] = self.location_name
        common_data["deal_type"] = self.deal_type
        common_data["accommodation_type"] = self.accommodation_type
        common_data["suburban_type"] = self.object_type

        if self.is_rent_short() and is_short_rent_card(card):
            return union_dicts(common_data, extract_short_rent_card(card, flat=False))

        author_data = define_author(card)
        location_data = parse_location_data(card)
        price_data = define_price_data(card)

        return union_dicts(common_data, author_data, price_data, location_data)

    def parse_detail_page(self, url: str) -> dict[str, Any]:
        from cian_parser.suburban.page_parser import SuburbanDetailParser
        parser = SuburbanDetailParser(self.browser)
        return parser.parse(url, partial_results=list(self.result))
