from __future__ import annotations

import re
from typing import Any

from cian_parser.browser import BrowserManager
from cian_parser.page_utils import detail_page, read_span_texts


class NewObjectDetailParser:
    def __init__(self, browser: BrowserManager):
        self.browser = browser

    def parse(self, url: str, partial_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        page_data: dict[str, Any] = {
            "year_of_construction": -1,
            "house_material_type": "",
            "finish_type": "",
            "ceiling_height": "",
            "class": "",
            "builder": "",
            "parking_type": "",
            "floors_from": -1,
            "floors_to": -1,
        }

        with detail_page(
            self.browser, url, partial_results,
            required_selector="[data-name='NewbuildingName']",
        ) as page:
            span_texts = read_span_texts(page)

            # Current specification values are DIVs, so do not depend on their
            # contents continuing to be wrapped in a SPAN.
            for label in page.query_selector_all("[data-testid='SpecificationTitle']"):
                parent = label.query_selector("xpath=..")
                value = parent.query_selector("[data-testid='SpecificationValue']") if parent else None
                if value:
                    span_texts.extend([label.inner_text().strip(), value.inner_text().strip()])

            field_map = {
                "Сдача": "year_of_construction",
                "Тип дома": "house_material_type",
                "Отделка": "finish_type",
                "Высота потолков": "ceiling_height",
                "Потолки": "ceiling_height",
                "Класс": "class",
                "Парковка": "parking_type",
            }

            for index, text in enumerate(span_texts):
                if "Срок сдачи" in text and index + 1 < len(span_texts):
                    page_data["year_of_construction"] = span_texts[index + 1]

                if text in field_map and index + 1 < len(span_texts):
                    page_data[field_map[text]] = span_texts[index + 1]

                if "Застройщик" in text and "Проектная декларация" in text:
                    page_data["builder"] = text.split(".")[0]

                if text == "Этажность" and index + 1 < len(span_texts):
                    ints = re.findall(r'\d+', span_texts[index + 1])
                    if len(ints) == 2:
                        page_data["floors_from"] = int(ints[0])
                        page_data["floors_to"] = int(ints[1])
                    elif len(ints) == 1:
                        page_data["floors_from"] = int(ints[0])
                        page_data["floors_to"] = int(ints[0])

            builder = page.query_selector("[data-name='BuilderInfoItem'] [data-name='BasicInfoLink'] a")
            if builder:
                page_data["builder"] = builder.inner_text().strip()

        return page_data
