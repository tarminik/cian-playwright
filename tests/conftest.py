import pytest

from cian_parser import CianParser


def pytest_configure(config):
    config.addinivalue_line("markers", "live: end-to-end tests hitting real Cian.ru")
    config.addinivalue_line("markers", "slow: slow tests (newobject, extra_data with detail pages)")


@pytest.fixture(scope="module")
def parser():
    """Shared parser for live tests — reuses single browser."""
    p = CianParser("Москва")
    yield p
    p.close()
