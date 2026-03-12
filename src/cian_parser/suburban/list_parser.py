from __future__ import annotations

import pathlib
from datetime import datetime
from typing import Any

from cian_parser.base_list import BaseListParser
from cian_parser.constants import FILE_NAME_SUBURBAN_FORMAT
from cian_parser.helpers import union_dicts, define_author, parse_location_data, define_price_data


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

        link = card.query_selector("a[data-name='LinkArea']")
        if not link:
            link = card.query_selector("a[href]")
        common_data["url"] = link.get_attribute("href") if link else ""
        common_data["location"] = self.location_name
        common_data["deal_type"] = self.deal_type
        common_data["accommodation_type"] = self.accommodation_type
        common_data["suburban_type"] = self.object_type

        author_data = define_author(card)
        location_data = parse_location_data(card)
        price_data = define_price_data(card)

        return union_dicts(common_data, author_data, price_data, location_data)

    def parse_detail_page(self, url: str) -> dict[str, Any]:
        from cian_parser.suburban.page_parser import SuburbanDetailParser
        parser = SuburbanDetailParser(self.browser)
        return parser.parse(url, partial_results=list(self.result))
