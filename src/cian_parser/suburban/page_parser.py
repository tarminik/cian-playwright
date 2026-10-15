from __future__ import annotations

from typing import Any

from cian_parser.browser import BrowserManager
from cian_parser.page_utils import detail_page, extract_phone, read_span_texts


class SuburbanDetailParser:
    def __init__(self, browser: BrowserManager):
        self.browser = browser

    def parse(self, url: str, partial_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        page_data: dict[str, Any] = {
            "year_of_construction": -1,
            "house_material_type": "",
            "land_plot": "",
            "land_plot_status": "",
            "heating_type": "",
            "gas_type": "",
            "water_supply_type": "",
            "sewage_system": "",
            "bathroom": "",
            "living_meters": -1,
            "kitchen_meters": -1,
            "floors_count": -1,
            "phone": "",
        }

        with detail_page(
            self.browser, url, partial_results, required_selector="[data-name='OfferCardPageLayout']",
        ) as page:
            span_texts = read_span_texts(page, "[data-name='OfferCardPageLayout'] span")

            field_map = {
                "Материал дома": "house_material_type",
                "Участок": "land_plot",
                "Статус участка": "land_plot_status",
                "Отопление": "heating_type",
                "Газ": "gas_type",
                "Водоснабжение": "water_supply_type",
                "Канализация": "sewage_system",
                "Санузел": "bathroom",
                "Площадь кухни": "kitchen_meters",
                "Жилая площадь": "living_meters",
                "Этажей в доме": "floors_count",
            }

            for index, text in enumerate(span_texts):
                if text in field_map and index + 1 < len(span_texts):
                    page_data[field_map[text]] = span_texts[index + 1]

                if "Год постройки" in text and index + 1 < len(span_texts):
                    page_data["year_of_construction"] = span_texts[index + 1]

                if "Год сдачи" in text and index + 1 < len(span_texts):
                    page_data["year_of_construction"] = span_texts[index + 1]

            page_data["phone"] = extract_phone(page)

        return page_data
