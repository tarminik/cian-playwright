from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import ElementHandle

from cian_parser.constants import STREET_TYPES


def union_dicts(*dicts: dict) -> dict:
    result: dict = {}
    for d in dicts:
        result.update(d)
    return result


def define_rooms_count(description: str) -> int:
    match = re.search(r"\b(\d+)\s*[-–‑]\s*комн", description, re.IGNORECASE)
    if match:
        return int(match.group(1))
    if re.search(r"\bстудия\b", description, re.IGNORECASE):
        return 1
    return -1


def define_deal_url_id(url: str) -> str:
    listing_id = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    return listing_id if listing_id.isdigit() else "-1"


def define_author(card: ElementHandle) -> dict[str, str]:
    """Extract author info from a Playwright card element."""
    author_data = {"author": "", "author_type": ""}

    brand_el = card.query_selector("[data-name='BrandingLevelWrapper']")
    if not brand_el:
        return author_data

    brand_text = brand_el.inner_text().strip()
    lines = [line.strip() for line in brand_text.split("\n") if line.strip()]

    type_map = [
        ("Агентство недвижимости", "real_estate_agent"),
        ("Собственник", "homeowner"),
        ("Риелтор", "realtor"),
        ("Ук・оф.Представитель", "official_representative"),
        ("Представитель застройщика", "representative_developer"),
        ("Застройщик", "developer"),
    ]

    for keyword, author_type in type_map:
        for i, line in enumerate(lines):
            if keyword.casefold() in line.casefold():
                author_data["author"] = lines[i + 1] if i + 1 < len(lines) else line
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
    if price_el:
        _parse_price_text(price_el.inner_text().strip(), price_data)
    else:
        price_rows = card.query_selector_all("[data-name='ContentRow']")
        for row in price_rows:
            text = row.inner_text().strip()
            if "₽" in text:
                _parse_price_text(text, price_data)
                break

    if price_data["price_per_month"] != -1:
        price_info = card.query_selector("[data-mark='PriceInfo']")
        if price_info:
            text = price_info.inner_text()
            commission = re.search(r"комисси[яи]\s*:?\s*(\d+)\s*%", text, re.IGNORECASE)
            if commission:
                price_data["commissions"] = int(commission.group(1))
            elif "без комиссии" in text.casefold():
                price_data["commissions"] = 0

    return price_data


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


def _is_street(text: str) -> bool:
    if re.search(r"^(?:м\.|метро\b|жк\b|жилой комплекс\b|мкр\.)|\b(?:р-н|район|поселение)\b", text, re.IGNORECASE):
        return False
    return any(
        re.search(r"(?<!\w)" + re.escape(street_type) + ("" if street_type.endswith(".") else r"(?!\w)"), text, re.IGNORECASE)
        for street_type in STREET_TYPES
    )


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
        if not location_data["residential_complex"]:
            for link in card.query_selector_all("a[href]"):
                match = re.match(r'ЖК\s*[«"]([^»"]+)[»"]', link.inner_text().strip(), re.IGNORECASE)
                if match:
                    location_data["residential_complex"] = match.group(1)
                    break

    # Extract district
    for text in geo_texts:
        if "р-н" in text or "поселение" in text:
            location_data["district"] = text.replace("р-н", "").strip()
            break

    # Extract street and house number
    for i, text in enumerate(geo_texts):
        if _is_street(text):
            location_data["street"] = text.replace("улица", "").strip()
            if i + 1 < len(geo_texts) and any(c.isdigit() for c in geo_texts[i + 1]):
                location_data["house_number"] = geo_texts[i + 1].strip()
            break

    # Fallback: parse comma-separated address
    if not location_data["street"] and full_address:
        address_elements = full_address.split(",")
        for j, elem in enumerate(address_elements):
            elem_stripped = elem.strip()
            if _is_street(elem_stripped):
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

        if _is_street(text):
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

    title_el = card.query_selector("[data-mark='OfferSubtitle']")
    if not title_el:
        title_el = card.query_selector("[data-name='TitleComponent']")
    if not title_el:
        return specification_data

    title_text = title_el.inner_text().strip()

    # Grouping spaces and decimal commas are common in Russian area labels.
    area_match = re.search(r"(\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?)\s*м[²2]", title_text)
    if area_match:
        specification_data["total_meters"] = float("".join(area_match.group(1).split()).replace(",", "."))

    # Extract floor info
    floor_match = re.search(r"(\d+)\s*/\s*(\d+)\s*эт", title_text, re.IGNORECASE)
    if floor_match:
        specification_data["floor"] = int(floor_match.group(1))
        specification_data["floors_count"] = int(floor_match.group(2))

    # Extract rooms count
    specification_data["rooms_count"] = define_rooms_count(title_text)

    return specification_data
