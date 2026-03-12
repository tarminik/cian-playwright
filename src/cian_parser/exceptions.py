from __future__ import annotations

from typing import Any


class CianParserError(Exception):
    """Base exception for cian_parser."""


class CaptchaError(CianParserError):
    """Raised when CAPTCHA is detected. Contains partial results collected before CAPTCHA."""

    def __init__(self, message: str, partial_results: list[dict[str, Any]]):
        super().__init__(message)
        self.partial_results = partial_results


class LocationNotFoundError(CianParserError, ValueError):
    """Raised when the specified location is not found in the database."""


class BrowserNotInstalledError(CianParserError, RuntimeError):
    """Raised when Playwright browser (chromium) is not installed."""
