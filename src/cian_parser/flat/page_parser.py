from __future__ import annotations

import logging
import re
from typing import Any

from cian_parser.browser import BrowserManager
from cian_parser.exceptions import CaptchaError

logger = logging.getLogger("cian_parser")


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
