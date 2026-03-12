from __future__ import annotations

import csv
from typing import Any


def save_to_csv(data: list[dict[str, Any]], file_path: str) -> None:
    """Save list of dicts to CSV with semicolon delimiter."""
    if not data:
        return

    # Use union of all keys to handle heterogeneous records
    all_keys: list[str] = []
    seen: set[str] = set()
    for row in data:
        for key in row:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
