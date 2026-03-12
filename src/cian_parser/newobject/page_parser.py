from __future__ import annotations

import logging
import re
from typing import Any

from cian_parser.browser import BrowserManager
from cian_parser.exceptions import CaptchaError

logger = logging.getLogger("cian_parser")


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
                if "Срок сдачи" in text and index + 1 < len(span_texts):
                    page_data["year_of_construction"] = span_texts[index + 1]

                if text == "Тип дома" and index + 1 < len(span_texts):
                    page_data["house_material_type"] = span_texts[index + 1]

                if text == "Отделка" and index + 1 < len(span_texts):
                    page_data["finish_type"] = span_texts[index + 1]

                if text == "Высота потолков" and index + 1 < len(span_texts):
                    page_data["ceiling_height"] = span_texts[index + 1]

                if text == "Класс" and index + 1 < len(span_texts):
                    page_data["class"] = span_texts[index + 1]

                if "Застройщик" in text and "Проектная декларация" in text:
                    page_data["builder"] = text.split(".")[0]

                if text == "Парковка" and index + 1 < len(span_texts):
                    page_data["parking_type"] = span_texts[index + 1]

                if text == "Этажность" and index + 1 < len(span_texts):
                    ints = re.findall(r'\d+', span_texts[index + 1])
                    if len(ints) == 2:
                        page_data["floors_from"] = int(ints[0])
                        page_data["floors_to"] = int(ints[1])
                    elif len(ints) == 1:
                        page_data["floors_from"] = int(ints[0])
                        page_data["floors_to"] = int(ints[0])

        except CaptchaError:
            raise
        except Exception as exc:
            logger.warning("Failed to parse newobject detail page %s: %s", url, exc)
        finally:
            page.close()

        return page_data
