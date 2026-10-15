from __future__ import annotations

import logging
from typing import Any

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright, Error as PlaywrightError
from playwright_stealth import Stealth

from cian_parser.exceptions import BrowserNotInstalledError, CianParserError

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
        self._owned_contexts: set[BrowserContext] = set()
        self._stealth = Stealth()
        self._started = False

    def start(self) -> None:
        if self._started:
            return

        self._playwright = sync_playwright().start()

        try:
            self._browser = self._playwright.chromium.launch(
                headless=self._headless,
                # Use full Chromium's unified headless mode. The default
                # headless shell advertises HeadlessChrome in Client Hints.
                channel="chromium",
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            self._context = self._create_context()
        except Exception as exc:
            self.close()
            if isinstance(exc, PlaywrightError) and "Executable doesn't exist" in str(exc):
                raise BrowserNotInstalledError(
                    "Chromium browser is not installed. "
                    "Run `playwright install chromium` to install it."
                ) from exc
            raise

        self._started = True
        logger.info("Browser started (headless=%s)", self._headless)

    def _create_context(self) -> BrowserContext:
        context_kwargs: dict[str, Any] = {
            "user_agent": USER_AGENT,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "ru-RU",
            "timezone_id": "Europe/Moscow",
        }
        if self._proxy:
            context_kwargs["proxy"] = {"server": self._proxy}
        return self._browser.new_context(**context_kwargs)

    def new_page(self, *, isolated: bool = False) -> Page:
        """Create a page; release isolated pages with close_page()."""
        self._ensure_started()
        context = self._create_context() if isolated else self._context
        if isolated:
            self._owned_contexts.add(context)
        page = None
        try:
            page = context.new_page()
            self._stealth.apply_stealth_sync(page)
        except Exception:
            if isolated:
                self._close_owned_context(context)
            elif page is not None:
                from cian_parser.page_utils import close_page
                close_page(page)
            raise
        return page

    def _close_owned_context(self, context: BrowserContext) -> None:
        try:
            context.close()
        except Exception:
            # Keep failed contexts tracked so manager shutdown retries cleanup.
            logger.warning("Failed to close isolated browser context", exc_info=True)
        else:
            self._owned_contexts.discard(context)

    def close_page(self, page: Page) -> None:
        """Close a page and its owned context without masking collection errors."""
        if page.context in self._owned_contexts:
            self._close_owned_context(page.context)
        else:
            from cian_parser.page_utils import close_page
            close_page(page)

    def navigate(self, page: Page, url: str) -> None:
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if response is not None and response.status >= 400:
            from cian_parser.page_utils import raise_for_captcha
            raise_for_captcha(page)
            raise CianParserError(f"HTTP {response.status} while loading {url}")

    def close(self) -> None:
        context, browser, playwright = self._context, self._browser, self._playwright
        owned_contexts = tuple(self._owned_contexts)
        self._owned_contexts.clear()
        self._context = None
        self._browser = None
        self._playwright = None
        self._started = False
        resources = [(owned, "close") for owned in owned_contexts]
        resources.extend(((context, "close"), (browser, "close"), (playwright, "stop")))
        for resource, method in resources:
            if resource is not None:
                try:
                    getattr(resource, method)()
                except Exception:
                    logger.warning("Failed to %s browser resource", method, exc_info=True)
        logger.info("Browser closed")

    def _ensure_started(self) -> None:
        if not self._started:
            self.start()

    def __enter__(self) -> "BrowserManager":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
