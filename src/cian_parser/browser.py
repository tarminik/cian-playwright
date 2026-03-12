from __future__ import annotations

import logging
from typing import Any

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright, Error as PlaywrightError
from playwright_stealth import Stealth

from cian_parser.exceptions import BrowserNotInstalledError

logger = logging.getLogger("cian_parser")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class BrowserManager:
    """Manages a single Playwright browser instance with stealth settings."""

    def __init__(self, *, headless: bool = True, proxy: str | None = None):
        self._headless = headless
        self._proxy = proxy
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._stealth = Stealth()
        self._started = False

    def start(self) -> None:
        if self._started:
            return

        self._playwright = sync_playwright().start()

        try:
            self._browser = self._playwright.chromium.launch(
                headless=self._headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
        except PlaywrightError as exc:
            self._playwright.stop()
            self._playwright = None
            if "Executable doesn't exist" in str(exc) or "browserType.launch" in str(exc):
                raise BrowserNotInstalledError(
                    "Chromium browser is not installed. "
                    "Run `playwright install chromium` to install it."
                ) from exc
            raise

        context_kwargs: dict[str, Any] = {
            "user_agent": USER_AGENT,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "ru-RU",
            "timezone_id": "Europe/Moscow",
        }
        if self._proxy:
            context_kwargs["proxy"] = {"server": self._proxy}

        self._context = self._browser.new_context(**context_kwargs)
        self._started = True
        logger.info("Browser started (headless=%s)", self._headless)

    def new_page(self) -> Page:
        self._ensure_started()
        page = self._context.new_page()
        self._stealth.apply_stealth_sync(page)
        return page

    def navigate(self, page: Page, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

    def close(self) -> None:
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._context = None
        self._started = False
        logger.info("Browser closed")

    def _ensure_started(self) -> None:
        if not self._started:
            self.start()

    def __enter__(self) -> "BrowserManager":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
