from cian_parser.exceptions import CaptchaError, CianParserError, LocationNotFoundError, BrowserNotInstalledError


def test_captcha_error_has_partial_results():
    data = [{"url": "http://example.com", "price": 100}]
    err = CaptchaError("captcha detected", partial_results=data)
    assert err.partial_results == data
    assert "captcha detected" in str(err)


def test_captcha_error_is_cian_parser_error():
    err = CaptchaError("test", partial_results=[])
    assert isinstance(err, CianParserError)


def test_location_not_found_is_value_error():
    err = LocationNotFoundError("not found")
    assert isinstance(err, ValueError)
    assert isinstance(err, CianParserError)


def test_browser_not_installed_is_runtime_error():
    err = BrowserNotInstalledError("not installed")
    assert isinstance(err, RuntimeError)
    assert isinstance(err, CianParserError)
