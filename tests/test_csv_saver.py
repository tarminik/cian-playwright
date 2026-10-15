import csv

import pytest

from cian_parser.csv_saver import save_to_csv


def test_csv_preserves_heterogeneous_records_and_quotes(tmp_path):
    path = tmp_path / "results.csv"
    rows = [{"url": "first", "description": "Москва; квартира\nс ремонтом"}, {"url": "second", "floor": 8}]
    save_to_csv(rows, str(path))
    with path.open(newline="", encoding="utf-8") as source:
        assert list(csv.DictReader(source, delimiter=";")) == [
            {"url": "first", "description": "Москва; квартира\nс ремонтом", "floor": ""},
            {"url": "second", "description": "", "floor": "8"},
        ]


def test_failed_export_preserves_previous_results_and_removes_temporary_file(tmp_path):
    class Unserializable:
        def __str__(self):
            raise ValueError("bad value")

    path = tmp_path / "results.csv"
    save_to_csv([{"url": "saved"}], str(path))
    original = path.read_bytes()
    with pytest.raises(ValueError, match="bad value"):
        save_to_csv([{"url": "saved"}, {"url": "new", "value": Unserializable()}], str(path))
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
