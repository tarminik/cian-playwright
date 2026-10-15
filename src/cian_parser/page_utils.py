from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlsplit

from playwright.sync_api import Page

from cian_parser.browser import BrowserManager
from cian_parser.exceptions import CaptchaError

logger = logging.getLogger("cian_parser")


def raise_for_captcha(page: Page, partial_results: list[dict[str, Any]] | None = None) -> None:
    """Detect challenge pages without treating a listing's mention as a challenge."""
    url = page.url
    parsed = urlsplit(url)
    challenge_url = "captcha" in parsed.path.lower().split("/") or parsed.hostname == "captcha.cian.ru"
    challenge_form = not challenge_url and page.query_selector("form[action*='captcha'], #captcha, [data-testid='captcha']")
    challenge_text = False
    if not challenge_url and not challenge_form:
        text = page.inner_text("body")
        challenge_text = any(
            re.fullmatch(
                r"captcha|капча|подтвердите,? что вы (?:не робот|человек)[.!]?|проверка,? что вы не робот[.!]?",
                line.strip(),
                re.IGNORECASE,
            )
            for line in text.splitlines()
        )
    if challenge_url or challenge_form or challenge_text:
        raise CaptchaError(f"CAPTCHA detected on page {url}", partial_results=list(partial_results or []))


def close_page(page: Page) -> None:
    """Close a page without losing collected data or masking the original error."""
    try:
        page.close()
    except Exception as exc:
        logger.warning("Failed to close page: %s", exc)


@contextmanager
def detail_page(
    browser: BrowserManager, url: str, partial_results: list[dict[str, Any]] | None = None,
    *, required_selector: str,
) -> Iterator[Page]:
    page = browser.new_page()
    try:
        browser.navigate(page, url)
        page.wait_for_timeout(2000)
        raise_for_captcha(page, partial_results)
        if not page.query_selector(required_selector):
            raise RuntimeError(f"Property detail content is missing on {url}")
        yield page
    except CaptchaError as exc:
        if partial_results is not None:
            exc.partial_results = list(partial_results)
        raise
    finally:
        close_page(page)


def read_span_texts(page: Page, selector: str = "span") -> list[str]:
    return [span.inner_text().strip() for span in page.query_selector_all(selector)]


def extract_phone(page: Page) -> str:
    """Read a complete contact number, excluding scripts and unrelated markup."""
    for link in page.query_selector_all("[data-name='OfferCardPageLayout'] a[href^='tel:']"):
        href = link.get_attribute("href") or ""
        number = re.sub(r"[\s()\-]", "", href.removeprefix("tel:").split(";", 1)[0])
        if re.fullmatch(r"\+7\d{10}", number):
            return number
        if re.fullmatch(r"8\d{10}", number):
            return "+7" + number[1:]
    return ""
