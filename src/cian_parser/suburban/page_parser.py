from __future__ import annotations

import logging
from typing import Any

from cian_parser.browser import BrowserManager
from cian_parser.exceptions import CaptchaError

logger = logging.getLogger("cian_parser")


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

        page = self.browser.new_page()
        try:
            self.browser.navigate(page, url)
            page.wait_for_timeout(2000)

            # Check for CAPTCHA on detail page
            body_text = page.inner_text("body")
            if "Captcha" in body_text or "captcha" in body_text:
                raise CaptchaError(
                    f"CAPTCHA detected on detail page {url}",
                    partial_results=partial_results or [],
                )

            spans = page.query_selector_all("span")
            span_texts = []
            for span in spans:
                try:
                    span_texts.append(span.inner_text().strip())
                except Exception:
                    span_texts.append("")

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
                "Общая площадь": "living_meters",
                "Этажей в доме": "floors_count",
            }

            for index, text in enumerate(span_texts):
                if text in field_map and index + 1 < len(span_texts):
                    page_data[field_map[text]] = span_texts[index + 1]

                if "Год постройки" in text and index + 1 < len(span_texts):
                    page_data["year_of_construction"] = span_texts[index + 1]

                if "Год сдачи" in text and index + 1 < len(span_texts):
                    page_data["year_of_construction"] = span_texts[index + 1]

            html = page.content()
            if "+7" in html:
                phone_start = html.find("+7")
                raw_phone = html[phone_start:phone_start + 16].split('"')[0]
                page_data["phone"] = raw_phone.replace(" ", "").replace("-", "")

        except CaptchaError:
            raise
        except Exception as exc:
            logger.warning("Failed to parse detail page %s: %s", url, exc)
        finally:
            page.close()

        return page_data
