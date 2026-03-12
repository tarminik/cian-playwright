"""E2E tests that create their own CianParser instances.

Separated from test_e2e.py because Playwright's sync API allows only one
active instance per process. The module-scoped parser fixture in test_e2e.py
must be torn down before these tests can start their own Playwright.
"""

import pytest

from cian_parser import CianParser
from cian_parser.exceptions import CaptchaError


def safe_run(fn):
    """Run parser function, return results or partial_results on CAPTCHA."""
    try:
        return fn()
    except CaptchaError as e:
        if e.partial_results:
            return e.partial_results
        pytest.skip("CAPTCHA with no partial results")


# ===========================================================================
# Group 12: Context Manager
# ===========================================================================

@pytest.mark.live
class TestContextManager:

    def test_context_manager_basic(self):
        with CianParser("Москва") as p:
            result = safe_run(
                lambda: p.get_flats(
                    deal_type="sale", rooms=1,
                    additional_settings={"start_page": 1, "end_page": 1},
                )
            )
        assert len(result) > 0

    def test_context_manager_browser_cleanup(self):
        p = CianParser("Москва")
        with p:
            safe_run(
                lambda: p.get_flats(
                    deal_type="sale", rooms=1,
                    additional_settings={"start_page": 1, "end_page": 1},
                )
            )
        assert p._browser._started is False


# ===========================================================================
# Group 18: Different Location (SPb)
# ===========================================================================

@pytest.mark.live
class TestDifferentLocation:

    def test_flat_sale_spb(self):
        with CianParser("Санкт-Петербург") as p:
            result = safe_run(
                lambda: p.get_flats(
                    deal_type="sale", rooms=1,
                    additional_settings={"start_page": 1, "end_page": 1},
                )
            )
        assert len(result) > 0
        assert all(r["location"] == "Санкт-Петербург" for r in result)
