import pytest

from cian_parser import CianParser


def pytest_addoption(parser):
    parser.addoption("--headed", action="store_true", help="Run live Cian tests with a visible browser (requires a display).")


@pytest.fixture(scope="module")
def headless(request):
    return not request.config.getoption("--headed")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: end-to-end tests hitting real Cian.ru")
    config.addinivalue_line("markers", "slow: slow tests (newobject, extra_data with detail pages)")


@pytest.fixture(scope="module")
def parser(headless):
    """Shared parser for live tests — reuses single browser."""
    p = CianParser("Москва", headless=headless)
    yield p
    p.close()
