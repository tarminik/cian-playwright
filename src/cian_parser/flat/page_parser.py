from __future__ import annotations

import re
from typing import Any

from cian_parser.browser import BrowserManager
from cian_parser.page_utils import detail_page, extract_phone, read_span_texts


class FlatDetailParser:
    def __init__(self, browser: BrowserManager):
        self.browser = browser

    def parse(self, url: str, partial_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        page_data: dict[str, Any] = {
            "year_of_construction": -1,
            "object_type": "",
            "house_material_type": "",
            "heating_type": "",
            "finish_type": "",
            "living_meters": -1,
            "kitchen_meters": -1,
            "floor": -1,
            "floors_count": -1,
            "phone": "",
        }

        with detail_page(
            self.browser, url, partial_results, required_selector="[data-name='OfferCardPageLayout']",
        ) as page:
            span_texts = read_span_texts(page, "[data-name='OfferCardPageLayout'] span")

            for index, text in enumerate(span_texts):
                if text == "Тип жилья" and index + 1 < len(span_texts):
                    page_data["object_type"] = span_texts[index + 1]

                if text == "Тип дома" and index + 1 < len(span_texts):
                    page_data["house_material_type"] = span_texts[index + 1]

                if text == "Отопление" and index + 1 < len(span_texts):
                    page_data["heating_type"] = span_texts[index + 1]

                if text == "Отделка" and index + 1 < len(span_texts):
                    page_data["finish_type"] = span_texts[index + 1]

                if text == "Площадь кухни" and index + 1 < len(span_texts):
                    page_data["kitchen_meters"] = span_texts[index + 1]

                if text == "Жилая площадь" and index + 1 < len(span_texts):
                    page_data["living_meters"] = span_texts[index + 1]

                if "Год постройки" in text and index + 1 < len(span_texts):
                    page_data["year_of_construction"] = span_texts[index + 1]

                if "Год сдачи" in text and index + 1 < len(span_texts):
                    page_data["year_of_construction"] = span_texts[index + 1]

                if text == "Этаж" and index + 1 < len(span_texts):
                    ints = re.findall(r'\d+', span_texts[index + 1])
                    if len(ints) == 2:
                        page_data["floor"] = int(ints[0])
                        page_data["floors_count"] = int(ints[1])

            page_data["phone"] = extract_phone(page)

        return page_data
