from __future__ import annotations

import csv
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
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

    destination = Path(file_path)
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=destination.parent,
            prefix=f".{destination.name}.", suffix=".tmp", delete=False,
        ) as f:
            temporary_path = Path(f.name)
            writer = csv.DictWriter(f, fieldnames=all_keys, delimiter=";", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
