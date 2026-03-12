from cian_parser.helpers import define_rooms_count, define_deal_url_id, _parse_price_text


def _default_price_data():
    return {"price": -1, "price_per_month": -1, "price_per_day": -1, "commissions": 0}


def test_rooms_count_1():
    assert define_rooms_count("1-комн. квартира, 45 м²") == 1


def test_rooms_count_studio():
    assert define_rooms_count("Студия, 25 м²") == 1


def test_rooms_count_2():
    assert define_rooms_count("2-комн. квартира, 65 м²") == 2


def test_rooms_count_3():
    assert define_rooms_count("3-комн. квартира") == 3


def test_rooms_count_4():
    assert define_rooms_count("4-комн. апартаменты") == 4


def test_rooms_count_5():
    assert define_rooms_count("5-комн. квартира") == 5


def test_rooms_count_unknown():
    assert define_rooms_count("квартира") == -1


def test_deal_url_id_trailing_slash():
    assert define_deal_url_id("https://www.cian.ru/sale/flat/325862918/") == "325862918"


def test_deal_url_id_no_trailing_slash():
    assert define_deal_url_id("https://www.cian.ru/sale/flat/325862918") == "325862918"


def test_deal_url_id_fallback():
    assert define_deal_url_id("http://x") == "-1"


def test_parse_price_sale():
    result = _parse_price_text("70 000 000 ₽", _default_price_data())
    assert result["price"] == 70000000
    assert result["price_per_month"] == -1
    assert result["price_per_day"] == -1


def test_parse_price_rent_long():
    result = _parse_price_text("50 000 ₽/мес.", _default_price_data())
    assert result["price_per_month"] == 50000
    assert result["price"] == -1


def test_parse_price_rent_long_with_commission():
    result = _parse_price_text("50 000 ₽/мес. 50%", _default_price_data())
    assert result["price_per_month"] == 50000
    assert result["commissions"] == 50


def test_parse_price_rent_long_with_100_pct_commission():
    result = _parse_price_text("50 000 ₽/мес. 100%", _default_price_data())
    assert result["commissions"] == 100


def test_parse_price_rent_short():
    result = _parse_price_text("5 000 ₽/сут.", _default_price_data())
    assert result["price_per_day"] == 5000
    assert result["price"] == -1


def test_parse_price_mln_skipped():
    result = _parse_price_text("70 млн ₽", _default_price_data())
    assert result["price"] == -1


def test_parse_price_no_currency():
    result = _parse_price_text("no price here", _default_price_data())
    assert result["price"] == -1
    assert result["price_per_month"] == -1
