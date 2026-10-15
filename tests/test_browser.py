from unittest.mock import Mock

import pytest
from playwright.sync_api import Error as PlaywrightError

from cian_parser.browser import BrowserManager
from cian_parser.exceptions import BrowserNotInstalledError, CianParserError


@pytest.fixture
def runtime(monkeypatch):
    playwright = Mock()
    monkeypatch.setattr("cian_parser.browser.sync_playwright", lambda: Mock(start=lambda: playwright))
    return playwright


def test_context_creation_failure_releases_browser_and_driver(runtime):
    browser = runtime.chromium.launch.return_value
    browser.new_context.side_effect = PlaywrightError("context failed")
    manager = BrowserManager()
    with pytest.raises(PlaywrightError, match="context failed"):
        manager.start()
    browser.close.assert_called_once()
    runtime.stop.assert_called_once()
    assert not manager._started
    assert manager._browser is None


def test_launch_error_is_not_misreported_as_missing_install(runtime):
    runtime.chromium.launch.side_effect = PlaywrightError("BrowserType.launch: Target closed")
    with pytest.raises(PlaywrightError, match="Target closed"):
        BrowserManager().start()
    runtime.stop.assert_called_once()


def test_missing_browser_has_actionable_exception(runtime):
    runtime.chromium.launch.side_effect = PlaywrightError("Executable doesn't exist at /missing/chromium")
    with pytest.raises(BrowserNotInstalledError, match="install chromium"):
        BrowserManager().start()
    runtime.stop.assert_called_once()


def test_failed_page_initialization_closes_page(runtime):
    manager = BrowserManager()
    manager._stealth = Mock()
    manager._stealth.apply_stealth_sync.side_effect = RuntimeError("initialization failed")
    with pytest.raises(RuntimeError, match="initialization failed"):
        manager.new_page()
    runtime.chromium.launch.return_value.new_context.return_value.new_page.return_value.close.assert_called_once()
    manager.close()


def test_cleanup_attempts_all_resources_and_is_idempotent(runtime):
    manager = BrowserManager()
    manager.start()
    browser = runtime.chromium.launch.return_value
    browser.close.side_effect = PlaywrightError("browser gone")
    manager.close()
    manager.close()
    runtime.stop.assert_called_once()
    assert not manager._started
    assert manager._browser is manager._context is manager._playwright is None


@pytest.mark.parametrize("status", [404, 429, 500, 503])
def test_http_failure_cannot_be_returned_as_success(status):
    page = Mock()
    page.goto.return_value.status = status
    page.url = "https://www.cian.ru/cat.php"
    page.inner_text.return_value = "Service unavailable"
    page.query_selector.return_value = None
    with pytest.raises(CianParserError, match=str(status)):
        BrowserManager().navigate(page, page.url)


def test_isolated_page_inherits_settings_and_closes_only_its_context(runtime):
    shared, owned = Mock(), Mock()
    runtime.chromium.launch.return_value.new_context.side_effect = [shared, owned]
    shared.new_page.return_value.context = shared
    owned.new_page.return_value.context = owned
    manager = BrowserManager(proxy="http://proxy.example:8080")
    manager._stealth = Mock()
    shared_page = manager.new_page()
    isolated_page = manager.new_page(isolated=True)

    calls = runtime.chromium.launch.return_value.new_context.call_args_list
    assert calls[0].kwargs == calls[1].kwargs
    assert calls[1].kwargs["proxy"] == {"server": "http://proxy.example:8080"}
    assert calls[1].kwargs["locale"] == "ru-RU"
    assert calls[1].kwargs["timezone_id"] == "Europe/Moscow"
    assert manager._stealth.apply_stealth_sync.call_count == 2

    manager.close_page(isolated_page)
    owned.close.assert_called_once()
    shared.close.assert_not_called()
    shared_page.close.assert_not_called()
    assert manager._owned_contexts == set()
    manager.close_page(shared_page)
    shared_page.close.assert_called_once()
    manager.close()
    shared.close.assert_called_once()
    owned.close.assert_called_once()


@pytest.mark.parametrize("failure_stage", ["page", "stealth"])
def test_failed_isolated_page_creation_preserves_error_and_retries_context_cleanup(runtime, failure_stage):
    shared, owned = Mock(), Mock()
    runtime.chromium.launch.return_value.new_context.side_effect = [shared, owned]
    owned.close.side_effect = [PlaywrightError("cleanup failed"), None]
    manager = BrowserManager()
    manager._stealth = Mock()
    if failure_stage == "page":
        owned.new_page.side_effect = RuntimeError("page initialization failed")
    else:
        manager._stealth.apply_stealth_sync.side_effect = RuntimeError("page initialization failed")

    with pytest.raises(RuntimeError, match="page initialization failed"):
        manager.new_page(isolated=True)
    assert manager._owned_contexts == {owned}
    owned.close.assert_called_once()
    manager.close()
    assert owned.close.call_count == 2
    assert manager._owned_contexts == set()
    shared.close.assert_called_once()
    runtime.stop.assert_called_once()


def test_owned_context_cleanup_does_not_mask_collection_error(runtime):
    shared, owned = Mock(), Mock()
    runtime.chromium.launch.return_value.new_context.side_effect = [shared, owned]
    owned.new_page.return_value.context = owned
    owned.close.side_effect = [PlaywrightError("context disconnected"), None]
    manager = BrowserManager()
    manager._stealth = Mock()
    page = manager.new_page(isolated=True)
    with pytest.raises(RuntimeError, match="collection failed"):
        try:
            raise RuntimeError("collection failed")
        finally:
            manager.close_page(page)
    assert manager._owned_contexts == {owned}
    manager.close()
    assert owned.close.call_count == 2
    assert manager._owned_contexts == set()
