from __future__ import annotations

import re
from typing import Any

from playwright.sync_api import ElementHandle

from cian_parser.constants import STREET_TYPES, NOT_STREET_ADDRESS_ELEMENTS, FLOATS_NUMBERS_REG_EXPRESSION


def union_dicts(*dicts: dict) -> dict:
    result: dict = {}
    for d in dicts:
        result.update(d)
    return result


def define_rooms_count(description: str) -> int:
    if "1-комн" in description or "Студия" in description or "студия" in description:
        return 1
    if "2-комн" in description:
        return 2
    if "3-комн" in description:
        return 3
    if "4-комн" in description:
        return 4
    if "5-комн" in description:
        return 5
    return -1


def define_deal_url_id(url: str) -> str:
    url_path_elements = url.split("/")
    if len(url_path_elements[-1]) > 3:
        return url_path_elements[-1]
    if len(url_path_elements) >= 2 and len(url_path_elements[-2]) > 3:
        return url_path_elements[-2]
    return "-1"


def define_author(card: ElementHandle) -> dict[str, str]:
    """Extract author info from a Playwright card element."""
    author_data = {"author": "", "author_type": ""}

    brand_el = card.query_selector("[data-name='BrandingLevelWrapper']")
    if not brand_el:
        return author_data

    brand_text = brand_el.inner_text().strip()
    lines = [line.strip() for line in brand_text.split("\n") if line.strip()]

    full_text = brand_text

    type_map = [
        ("Агентство недвижимости", "real_estate_agent"),
        ("Собственник", "homeowner"),
        ("Риелтор", "realtor"),
        ("Ук・оф.Представитель", "official_representative"),
        ("Представитель застройщика", "representative_developer"),
        ("Застройщик", "developer"),
    ]

    for keyword, author_type in type_map:
        if keyword in full_text:
            for i, line in enumerate(lines):
                if keyword in line:
                    author_data["author"] = lines[i + 1].replace(",", ".").strip() if i + 1 < len(lines) else line
                    author_data["author_type"] = author_type
                    return author_data

    if any("ID" in line for line in lines):
        for line in lines:
            if "ID" in line:
                author_data["author"] = line
                author_data["author_type"] = "unknown"
                return author_data

    if lines:
        author_data["author"] = lines[1] if len(lines) > 1 else lines[0]
        author_data["author_type"] = "unknown"

    return author_data


def define_price_data(card: ElementHandle) -> dict[str, Any]:
    """Extract price data from a Playwright card element."""
    price_data: dict[str, Any] = {
        "price": -1,
        "price_per_month": -1,
        "price_per_day": -1,
        "commissions": 0,
    }

    price_el = card.query_selector("[data-mark='MainPrice']")
    if not price_el:
        price_rows = card.query_selector_all("[data-name='ContentRow']")
        for row in price_rows:
            text = row.inner_text().strip()
            if "₽" in text:
                price_el_text = text
                return _parse_price_text(price_el_text, price_data)
        return price_data

    price_el_text = price_el.inner_text().strip()
    return _parse_price_text(price_el_text, price_data)


def _parse_price_text(text: str, price_data: dict[str, Any]) -> dict[str, Any]:
    if "₽/мес" in text:
        price_str = text[:text.find("₽/мес")].strip()
        try:
            price_data["price_per_month"] = int("".join(price_str.split()))
        except ValueError:
            pass

        if "%" in text:
            pct_match = re.search(r'(\d+)\s*%', text)
            if pct_match:
                price_data["commissions"] = int(pct_match.group(1))

        return price_data

    if "₽/сут" in text:
        price_str = text[:text.find("₽/сут")].strip()
        try:
            price_data["price_per_day"] = int("".join(price_str.split()))
        except ValueError:
            pass
        return price_data

    if "₽" in text and "млн" not in text:
        price_str = text[:text.find("₽")].strip()
        try:
            price_data["price"] = int("".join(price_str.split()))
        except ValueError:
            pass
        return price_data

    return price_data


def define_location_data(card: ElementHandle, is_sale: bool) -> dict[str, str]:
    """Extract location data from a Playwright card element (for flats)."""
    location_data: dict[str, str] = {
        "district": "",
        "street": "",
        "house_number": "",
        "underground": "",
    }

    if is_sale:
        location_data["residential_complex"] = ""

    geo_labels = card.query_selector_all("[data-name='GeoLabel']")
    geo_texts = [gl.inner_text().strip() for gl in geo_labels]

    # Try to find metro
    metro_el = card.query_selector("[data-name='SpecialGeo']")
    if metro_el:
        metro_text = metro_el.inner_text().strip()
        metro_lines = [line.strip() for line in metro_text.split("\n") if line.strip()]
        if metro_lines:
            location_data["underground"] = metro_lines[0]
    else:
        for text in geo_texts:
            if "м. " in text:
                location_data["underground"] = text

    # Build full address text from geo labels
    full_address = ", ".join(geo_texts)

    # Extract residential complex
    if is_sale:
        for text in geo_texts:
            if "ЖК" in text and "«" in text and "»" in text:
                location_data["residential_complex"] = text.split("«")[1].split("»")[0]
                break

    # Extract district
    for text in geo_texts:
        if "р-н" in text or "поселение" in text:
            location_data["district"] = text.replace("р-н", "").strip()
            break

    # Extract street and house number
    for i, text in enumerate(geo_texts):
        text_lower = text.lower()
        if any(st in text_lower for st in STREET_TYPES):
            location_data["street"] = text.replace("улица", "").strip()
            if i + 1 < len(geo_texts) and any(c.isdigit() for c in geo_texts[i + 1]):
                location_data["house_number"] = geo_texts[i + 1].strip()
            break

    # Fallback: parse comma-separated address
    if not location_data["street"] and full_address:
        address_elements = full_address.split(",")
        for j, elem in enumerate(address_elements):
            elem_stripped = elem.strip()
            elem_lower = elem_stripped.lower()

            if any(st in elem_lower for st in STREET_TYPES):
                location_data["street"] = elem_stripped.replace("улица", "").strip()
                if j + 1 < len(address_elements):
                    next_elem = address_elements[j + 1].strip()
                    if any(c.isdigit() for c in next_elem) and len(next_elem) < 10:
                        location_data["house_number"] = next_elem
                break

    return location_data


def parse_location_data(card: ElementHandle) -> dict[str, str]:
    """Extract location data from a Playwright card element (for suburban)."""
    location_data: dict[str, str] = {
        "district": "",
        "underground": "",
        "street": "",
        "house_number": "",
    }

    geo_labels = card.query_selector_all("[data-name='GeoLabel']")
    geo_texts = [gl.inner_text().strip() for gl in geo_labels]

    for i, text in enumerate(geo_texts):
        if "м. " in text:
            location_data["underground"] = text

        if "р-н" in text or "поселение" in text:
            location_data["district"] = text

        text_lower = text.lower()
        if any(st in text_lower for st in STREET_TYPES):
            location_data["street"] = text
            if i + 1 < len(geo_texts) and any(c.isdigit() for c in geo_texts[i + 1]):
                location_data["house_number"] = geo_texts[i + 1]

    return location_data


def define_specification_data(card: ElementHandle) -> dict[str, Any]:
    """Extract specification data (rooms, area, floor) from a Playwright card element."""
    specification_data: dict[str, Any] = {
        "floor": -1,
        "floors_count": -1,
        "rooms_count": -1,
        "total_meters": -1,
    }

    title_el = card.query_selector("[data-name='TitleComponent']")
    if not title_el:
        return specification_data

    title_text = title_el.inner_text().strip()

    # Extract total_meters
    if "м²" in title_text:
        meters_part = title_text[:title_text.find("м²")].replace(",", ".")
        floats = re.findall(FLOATS_NUMBERS_REG_EXPRESSION, meters_part)
        if floats:
            try:
                specification_data["total_meters"] = float(floats[-1].strip().replace(" ", "").replace("-", ""))
            except ValueError:
                pass

    # Extract floor info
    if "этаж" in title_text:
        floor_section = title_text[title_text.rfind("этаж") - 7:title_text.rfind("этаж")]
        floor_parts = floor_section.split("/")
        if len(floor_parts) == 2:
            ints = re.findall(r'\d+', floor_parts[0])
            if ints:
                specification_data["floor"] = int(ints[-1])
            ints = re.findall(r'\d+', floor_parts[1])
            if ints:
                specification_data["floors_count"] = int(ints[-1])

    # Extract rooms count
    specification_data["rooms_count"] = define_rooms_count(title_text)

    return specification_data
