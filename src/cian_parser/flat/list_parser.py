from __future__ import annotations

import pathlib
from datetime import datetime
from typing import Any

from cian_parser.base_list import BaseListParser
from cian_parser.constants import FILE_NAME_FLAT_FORMAT
from cian_parser.helpers import union_dicts, define_author, define_location_data, define_price_data, define_specification_data


class FlatListParser(BaseListParser):
    def build_file_path(self) -> str:
        now_time = datetime.now().strftime("%d_%b_%Y_%H_%M_%S_%f")
        file_name = FILE_NAME_FLAT_FORMAT.format(
            self.accommodation_type, self.deal_type,
            self.start_page, self.end_page,
            self.location_name.lower(),
            now_time,
        )
        return str(pathlib.Path(pathlib.Path.cwd(), file_name.replace("'", "")))

    def parse_card(self, card: Any) -> dict[str, Any]:
        common_data: dict[str, Any] = {}

        link = card.query_selector("a[data-name='LinkArea']")
        if not link:
            link = card.query_selector("a[href*='/flat/']")
        common_data["url"] = link.get_attribute("href") if link else ""
        common_data["location"] = self.location_name
        common_data["deal_type"] = self.deal_type
        common_data["accommodation_type"] = self.accommodation_type

        author_data = define_author(card)
        location_data = define_location_data(card, is_sale=self.is_sale())
        price_data = define_price_data(card)
        specification_data = define_specification_data(card)

        return union_dicts(common_data, author_data, specification_data, price_data, location_data)

    def parse_detail_page(self, url: str) -> dict[str, Any]:
        from cian_parser.flat.page_parser import FlatDetailParser
        parser = FlatDetailParser(self.browser)
        return parser.parse(url, partial_results=list(self.result))
