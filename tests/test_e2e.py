import csv
import glob
import os

import pytest

from cian_parser import CianParser, list_locations, list_metro_stations, list_districts
from cian_parser.exceptions import CaptchaError, CianParserError, LocationNotFoundError
from cian_parser.helpers import define_deal_url_id


# ---------------------------------------------------------------------------
# Helper: CAPTCHA-safe execution
# ---------------------------------------------------------------------------

def safe_run(fn):
    """Run parser function, return results or partial_results on CAPTCHA."""
    try:
        return fn()
    except CaptchaError as e:
        if e.partial_results:
            return e.partial_results
        pytest.skip("CAPTCHA with no partial results")


# ===========================================================================
# Group 1: Flat Sale
# ===========================================================================

@pytest.mark.live
class TestFlatSale:

    @pytest.fixture(scope="class")
    def sale_rooms_tuple(self, parser):
        return safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=(1, 2),
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )

    @pytest.fixture(scope="class")
    def sale_single_room(self, parser):
        return safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )

    def test_flat_sale_rooms_tuple(self, sale_rooms_tuple):
        result = sale_rooms_tuple
        assert len(result) > 0
        for r in result:
            assert r["rooms_count"] in {1, 2, -1}
            assert r["deal_type"] == "sale"
            assert r["url"].startswith("https://")

    def test_flat_sale_single_room(self, sale_single_room):
        result = sale_single_room
        assert len(result) > 0
        for r in result:
            assert r["rooms_count"] in {1, -1}

    def test_flat_sale_rooms_all(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms="all",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0
        for r in result:
            assert r["rooms_count"] in {1, 2, 3, 4, 5, -1}

    def test_flat_sale_rooms_studio(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms="studio",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0
        for r in result:
            assert r["rooms_count"] in {1, -1}

    def test_flat_sale_schema(self, sale_rooms_tuple):
        result = sale_rooms_tuple
        assert len(result) > 0

        expected_keys = {
            "url", "location", "deal_type", "accommodation_type",
            "author", "author_type", "floor", "floors_count",
            "rooms_count", "total_meters", "price",
            "district", "street", "house_number", "underground",
            "residential_complex",
        }
        forbidden_keys = {"price_per_month", "price_per_day", "commissions"}

        for r in result:
            for key in expected_keys:
                assert key in r, f"Missing key '{key}' in {r.get('url', 'unknown')}"
            for key in forbidden_keys:
                assert key not in r, f"Unexpected key '{key}' in {r.get('url', 'unknown')}"

            assert r["location"] == "Москва"
            assert r["deal_type"] == "sale"
            assert r["accommodation_type"] == "flat"

        prices_positive = [r["price"] for r in result if r["price"] > 0]
        assert len(prices_positive) >= len(result) * 0.5

    def test_flat_sale_dedup(self, sale_rooms_tuple):
        result = sale_rooms_tuple
        ids = [define_deal_url_id(r["url"]) for r in result]
        assert len(ids) == len(set(ids))


# ===========================================================================
# Group 2: Flat Rent Long
# ===========================================================================

@pytest.mark.live
class TestFlatRentLong:

    @pytest.fixture(scope="class")
    def rent_long_result(self, parser):
        return safe_run(
            lambda: parser.get_flats(
                deal_type="rent_long", rooms=1,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )

    def test_flat_rent_long_basic(self, rent_long_result):
        assert len(rent_long_result) > 0

    def test_flat_rent_long_schema(self, rent_long_result):
        result = rent_long_result
        assert len(result) > 0

        expected_keys = {
            "url", "location", "deal_type", "accommodation_type",
            "author", "author_type", "floor", "floors_count",
            "rooms_count", "total_meters", "price_per_month", "commissions",
            "district", "street", "house_number", "underground",
        }
        forbidden_keys = {"price", "residential_complex", "price_per_day", "object_type", "finish_type"}

        for r in result:
            for key in expected_keys:
                assert key in r, f"Missing key '{key}'"
            for key in forbidden_keys:
                assert key not in r, f"Unexpected key '{key}'"

            assert r["deal_type"] == "rent"
            assert r["accommodation_type"] == "flat"

        prices_positive = [r["price_per_month"] for r in result if r["price_per_month"] > 0]
        assert len(prices_positive) >= len(result) * 0.5

    def test_flat_rent_long_commissions(self, rent_long_result):
        for r in rent_long_result:
            assert isinstance(r["commissions"], int)
            assert r["commissions"] >= 0


# ===========================================================================
# Group 3: Flat Rent Short
# ===========================================================================

@pytest.mark.live
class TestFlatRentShort:

    @pytest.fixture(scope="class")
    def rent_short_result(self, parser):
        return safe_run(
            lambda: parser.get_flats(
                deal_type="rent_short", rooms=1,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )

    def test_flat_rent_short_basic(self, rent_short_result):
        if len(rent_short_result) == 0:
            pytest.skip("No rent_short listings available")
        assert len(rent_short_result) > 0

    def test_flat_rent_short_schema(self, rent_short_result):
        if len(rent_short_result) == 0:
            pytest.skip("No rent_short listings available")

        forbidden_keys = {"price", "price_per_month", "commissions", "residential_complex", "object_type", "finish_type"}

        for r in rent_short_result:
            assert "price_per_day" in r
            for key in forbidden_keys:
                assert key not in r, f"Unexpected key '{key}'"
            assert r["deal_type"] == "rent"

        for r in rent_short_result:
            assert isinstance(r["price_per_day"], int)


# ===========================================================================
# Group 4: Flat Extra Data
# ===========================================================================

@pytest.mark.live
@pytest.mark.slow
class TestFlatExtraData:

    def test_flat_sale_extra_data(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1, with_extra_data=True,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0

        extra_keys = {
            "year_of_construction", "object_type", "house_material_type",
            "heating_type", "finish_type", "living_meters", "kitchen_meters", "phone",
        }
        for r in result:
            for key in extra_keys:
                assert key in r, f"Missing extra key '{key}'"

        has_data = any(
            r.get("object_type", "") != "" or r.get("year_of_construction", -1) != -1
            for r in result
        )
        assert has_data, "Expected at least some records with extra data"

    def test_flat_rent_long_extra_data(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="rent_long", rooms=1, with_extra_data=True,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0

        expected_extra = {
            "year_of_construction", "house_material_type", "heating_type",
            "living_meters", "kitchen_meters", "phone",
        }
        removed_for_rent = {"object_type", "finish_type"}

        for r in result:
            for key in expected_extra:
                assert key in r, f"Missing extra key '{key}'"
            for key in removed_for_rent:
                assert key not in r, f"Unexpected key '{key}' for rent_long"


# ===========================================================================
# Group 5: Flat CSV
# ===========================================================================

@pytest.mark.live
class TestFlatCSV:

    @pytest.fixture(scope="class")
    def csv_result(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1, with_saving_csv=True,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        yield result
        # Cleanup CSV files
        for f in glob.glob("cian_flat_sale_*.csv"):
            os.remove(f)

    def test_flat_sale_csv_created(self, csv_result):
        assert len(csv_result) > 0
        csv_files = glob.glob("cian_flat_sale_*.csv")
        assert len(csv_files) >= 1

    def test_flat_sale_csv_delimiter(self, csv_result):
        csv_files = glob.glob("cian_flat_sale_*.csv")
        assert len(csv_files) >= 1
        with open(csv_files[0], encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader)
            assert len(header) > 1, "Header should have multiple columns with ';' delimiter"

    def test_flat_sale_csv_row_count(self, csv_result):
        csv_files = glob.glob("cian_flat_sale_*.csv")
        assert len(csv_files) >= 1
        with open(csv_files[0], encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader)
            rows = list(reader)
        assert len(rows) == len(csv_result)
        assert "url" in header
        assert "price" in header


# ===========================================================================
# Group 6: Flat Additional Settings / Filters
# ===========================================================================

@pytest.mark.live
class TestFlatFilters:

    def test_flat_sale_min_max_price(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1,
                additional_settings={
                    "start_page": 1, "end_page": 1,
                    "min_price": 5_000_000, "max_price": 15_000_000,
                },
            )
        )
        assert len(result) > 0
        for r in result:
            if r["price"] > 0:
                assert r["price"] >= 5_000_000 * 0.9, f"Price {r['price']} below min"
                assert r["price"] <= 15_000_000 * 1.1, f"Price {r['price']} above max"

    def test_flat_sale_sort_by_price(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1,
                additional_settings={
                    "start_page": 1, "end_page": 1,
                    "sort_by": "price_from_min_to_max",
                },
            )
        )
        assert len(result) > 0
        prices = [r["price"] for r in result if r["price"] > 0]
        for i in range(1, len(prices)):
            assert prices[i] >= prices[i - 1], f"Prices not sorted: {prices[i-1]} > {prices[i]}"

    def test_flat_sale_homeowner(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1,
                additional_settings={
                    "start_page": 1, "end_page": 1,
                    "is_by_homeowner": True,
                },
            )
        )
        assert len(result) > 0
        homeowner_count = sum(1 for r in result if r["author_type"] in ("homeowner", "unknown"))
        assert homeowner_count >= len(result) * 0.5

    def test_flat_sale_metro_filter(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1,
                additional_settings={
                    "start_page": 1, "end_page": 1,
                    "metro": "Московский", "metro_station": "Арбатская",
                },
            )
        )
        assert len(result) > 0

    def test_flat_sale_floor_filter(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1,
                additional_settings={
                    "start_page": 1, "end_page": 1,
                    "min_floor": 5, "max_floor": 10,
                },
            )
        )
        assert len(result) > 0
        valid_floors = [r for r in result if r["floor"] > 0]
        in_range = sum(1 for r in valid_floors if 5 <= r["floor"] <= 10)
        assert in_range >= len(valid_floors) * 0.5

    def test_flat_sale_district_filter(self, parser):
        result = safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1,
                additional_settings={
                    "start_page": 1, "end_page": 1,
                    "district": "Арбат",
                },
            )
        )
        assert len(result) > 0


# ===========================================================================
# Group 7: Suburban Sale — all 4 types
# ===========================================================================

@pytest.mark.live
class TestSuburbanSale:

    def test_suburban_house_sale(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="house", deal_type="sale",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0
        for r in result:
            assert r["accommodation_type"] == "suburban"

    def test_suburban_townhouse_sale(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="townhouse", deal_type="sale",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0

    def test_suburban_house_part_sale(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="house-part", deal_type="sale",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0

    def test_suburban_land_plot_sale(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="land-plot", deal_type="sale",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0


# ===========================================================================
# Group 8: Suburban Rent + Schema
# ===========================================================================

@pytest.mark.live
class TestSuburbanRent:

    def test_suburban_house_rent_long(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="house", deal_type="rent_long",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0
        for r in result:
            assert r["deal_type"] == "rent"

    def test_suburban_house_rent_short(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="house", deal_type="rent_short",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        if len(result) == 0:
            pytest.skip("No suburban rent_short listings available")
        for r in result:
            assert r["deal_type"] == "rent"

    def test_suburban_sale_schema(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="house", deal_type="sale",
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0

        expected_keys = {
            "url", "location", "deal_type", "accommodation_type",
            "author", "author_type", "price",
            "district", "underground", "street", "house_number",
        }

        for r in result:
            for key in expected_keys:
                assert key in r, f"Missing key '{key}'"
            assert r["accommodation_type"] == "suburban"


# ===========================================================================
# Group 9: Suburban Extra Data
# ===========================================================================

@pytest.mark.live
@pytest.mark.slow
class TestSuburbanExtraData:

    def test_suburban_house_sale_extra_data(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="house", deal_type="sale", with_extra_data=True,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0

        extra_keys = {
            "year_of_construction", "house_material_type", "land_plot",
            "land_plot_status", "heating_type", "gas_type",
            "water_supply_type", "sewage_system", "bathroom",
            "living_meters", "kitchen_meters", "floors_count", "phone",
        }
        for r in result:
            for key in extra_keys:
                assert key in r, f"Missing extra key '{key}'"


# ===========================================================================
# Group 10: Suburban CSV
# ===========================================================================

@pytest.mark.live
class TestSuburbanCSV:

    def test_suburban_sale_csv(self, parser):
        result = safe_run(
            lambda: parser.get_suburban(
                suburban_type="house", deal_type="sale", with_saving_csv=True,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )
        assert len(result) > 0

        csv_files = glob.glob("cian_suburban_*.csv")
        assert len(csv_files) >= 1

        with open(csv_files[0], encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader)
            rows = list(reader)
        assert len(rows) == len(result)

        # Cleanup
        for f in csv_files:
            os.remove(f)


# ===========================================================================
# Group 11: Newobject
# ===========================================================================

@pytest.mark.live
@pytest.mark.slow
class TestNewobject:

    def test_newobject_basic(self, parser, monkeypatch):
        from cian_parser.newobject.list_parser import NewObjectListParser

        original_init = NewObjectListParser.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.end_page = 1

        monkeypatch.setattr(NewObjectListParser, "__init__", patched_init)

        result = safe_run(lambda: parser.get_newobjects())
        assert len(result) > 0

        expected_keys = {"name", "location", "accommodation_type", "url", "full_full_location_address"}
        for r in result:
            for key in expected_keys:
                assert key in r, f"Missing key '{key}'"
            assert r["accommodation_type"] == "newobject"

        extra_keys = {
            "year_of_construction", "house_material_type", "finish_type",
            "ceiling_height", "class", "builder", "parking_type",
            "floors_from", "floors_to",
        }
        for r in result:
            for key in extra_keys:
                assert key in r, f"Missing extra key '{key}'"


# ===========================================================================
# Group 13: Proxy Handling (no browser)
# ===========================================================================

class TestProxyHandling:

    def test_proxy_none(self):
        p = CianParser("Москва", proxies=None)
        assert p._browser._proxy is None
        p.close()

    def test_proxy_string(self):
        p = CianParser("Москва", proxies="http://proxy:8080")
        assert p._browser._proxy == "http://proxy:8080"
        p.close()

    def test_proxy_list_uses_first(self):
        p = CianParser("Москва", proxies=["http://proxy1:8080", "http://proxy2:8080"])
        assert p._browser._proxy == "http://proxy1:8080"
        p.close()


# ===========================================================================
# Group 14: Validation Errors (no browser)
# ===========================================================================

class TestValidationErrors:

    def test_invalid_location(self):
        with pytest.raises(LocationNotFoundError):
            CianParser("НесуществующийГород")

    def test_invalid_deal_type(self, parser):
        with pytest.raises(ValueError, match="deal_type"):
            parser.get_flats(deal_type="invalid")

    def test_invalid_rooms(self, parser):
        with pytest.raises(ValueError):
            parser.get_flats(deal_type="sale", rooms=10)

    def test_invalid_suburban_type(self, parser):
        with pytest.raises(ValueError, match="suburban_type"):
            parser.get_suburban(suburban_type="castle", deal_type="sale")


# ===========================================================================
# Group 15: Utility Functions (no browser)
# ===========================================================================

class TestUtilityFunctions:

    def test_list_locations(self):
        locs = list_locations()
        assert len(locs) >= 150
        assert any(name == "Москва" for name, _ in locs)
        assert any(name == "Санкт-Петербург" for name, _ in locs)

    def test_list_metro_stations(self):
        metros = list_metro_stations()
        assert "Московский" in metros
        assert "Петербургский" in metros
        assert len(metros["Московский"]) > 100

    def test_list_locations_id_format(self):
        for name, city_id in list_locations():
            assert city_id.isdigit(), f"City '{name}' has non-digit ID: {city_id}"

    def test_list_districts_moscow(self):
        districts = list_districts("Москва")
        assert len(districts) >= 120
        assert any(name == "Арбат" for name, _ in districts)
        assert any(name == "Тверской" for name, _ in districts)

    def test_list_districts_spb(self):
        districts = list_districts("Санкт-Петербург")
        assert len(districts) >= 18

    def test_list_districts_unknown(self):
        districts = list_districts("НесуществующийГород")
        assert districts == []


# ===========================================================================
# Group 16: CaptchaError Contract (no browser)
# ===========================================================================

class TestCaptchaErrorContract:

    def test_captcha_error_partial_results(self):
        err = CaptchaError("test", partial_results=[{"url": "x"}])
        assert err.partial_results == [{"url": "x"}]
        assert isinstance(err, CianParserError)


# ===========================================================================
# Group 17: Data Types Integrity
# ===========================================================================

@pytest.mark.live
class TestDataTypes:

    @pytest.fixture(scope="class")
    def sale_result(self, parser):
        return safe_run(
            lambda: parser.get_flats(
                deal_type="sale", rooms=1,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )

    @pytest.fixture(scope="class")
    def rent_long_result(self, parser):
        return safe_run(
            lambda: parser.get_flats(
                deal_type="rent_long", rooms=1,
                additional_settings={"start_page": 1, "end_page": 1},
            )
        )

    def test_flat_sale_data_types(self, sale_result):
        assert len(sale_result) > 0
        for r in sale_result:
            assert isinstance(r["url"], str)
            assert isinstance(r["price"], int)
            assert isinstance(r["floor"], int)
            assert isinstance(r["floors_count"], int)
            assert isinstance(r["rooms_count"], int)
            assert isinstance(r["total_meters"], (int, float))
            assert isinstance(r["author"], str)
            assert isinstance(r["author_type"], str)
            assert isinstance(r["district"], str)
            assert isinstance(r["street"], str)
            assert isinstance(r["house_number"], str)
            assert isinstance(r["underground"], str)

    def test_flat_rent_long_data_types(self, rent_long_result):
        assert len(rent_long_result) > 0
        for r in rent_long_result:
            assert isinstance(r["price_per_month"], int)
            assert isinstance(r["commissions"], int)


