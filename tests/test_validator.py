
import csv

import pytest

from src.validator import validate_csv, CSVValidationError


def write_csv(path, rows, headers=None):
    headers = headers or [
        "order_id", "product", "quantity", "unit_price", "region"
    ]

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_valid_csv(tmp_path):
    path = tmp_path / "sales.csv"
    write_csv(path, [
        {
            "order_id": "ORD001",
            "product": "Laptop",
            "quantity": "2",
            "unit_price": "50000",
            "region": "South",
        }
    ])

    result = validate_csv(path)

    assert result["total_rows"] == 1
    assert len(result["valid_rows"]) == 1
    assert result["invalid_rows"] == []
    assert result["valid_rows"][0]["revenue"] == 100000


def test_negative_quantity_is_rejected(tmp_path):
    path = tmp_path / "sales.csv"
    write_csv(path, [{
        "order_id": "ORD002",
        "product": "Mouse",
        "quantity": "-5",
        "unit_price": "500",
        "region": "North",
    }])

    result = validate_csv(path)

    assert len(result["valid_rows"]) == 0
    assert len(result["invalid_rows"]) == 1
    assert "quantity must be greater than zero" in (
        result["invalid_rows"][0]["errors"]
    )


def test_duplicate_order_id_is_rejected(tmp_path):
    path = tmp_path / "sales.csv"
    base = {
        "product": "Mouse",
        "quantity": "1",
        "unit_price": "500",
        "region": "North",
    }

    write_csv(path, [
        {"order_id": "ORD001", **base},
        {"order_id": "ORD001", **base},
    ])

    result = validate_csv(path)

    assert len(result["valid_rows"]) == 1
    assert len(result["invalid_rows"]) == 1
    assert result["duplicate_order_ids"] == 1
    assert "Duplicate order_id" in result["invalid_rows"][0]["errors"]


def test_missing_required_column_fails(tmp_path):
    path = tmp_path / "sales.csv"
    write_csv(path, [], headers=["order_id", "product"])

    with pytest.raises(CSVValidationError, match="Missing required columns"):
        validate_csv(path)


def test_empty_file_fails(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(CSVValidationError, match="empty"):
        validate_csv(path)


def test_missing_value_is_reported(tmp_path):
    path = tmp_path / "sales.csv"
    write_csv(path, [{
        "order_id": "ORD001",
        "product": "",
        "quantity": "1",
        "unit_price": "100",
        "region": "South",
    }])

    result = validate_csv(path)

    assert result["missing_values_by_column"]["product"] == 1
    assert len(result["invalid_rows"]) == 1

def test_file_size_limit_is_enforced(tmp_path):
    from src.validator import CSVValidationError, validate_csv

    file_path = tmp_path / "large.csv"
    file_path.write_text(
        "order_id,product\nORD1,Laptop\n",
        encoding="utf-8",
    )

    with pytest.raises(CSVValidationError, match="exceeds"):
        validate_csv(file_path, max_size_bytes=5)


def test_invalid_utf8_is_rejected(tmp_path):
    from src.validator import CSVValidationError, validate_csv

    file_path = tmp_path / "invalid-encoding.csv"
    file_path.write_bytes(
        b"order_id,product,quantity,unit_price,region\n\xff"
    )

    with pytest.raises(CSVValidationError, match="UTF-8"):
        validate_csv(file_path)


def test_header_only_csv_has_zero_data_rows(tmp_path):
    from src.validator import validate_csv

    file_path = tmp_path / "header-only.csv"
    file_path.write_text(
        "order_id,product,quantity,unit_price,region\n",
        encoding="utf-8",
    )

    result = validate_csv(file_path)

    assert result["total_rows"] == 0
    assert result["valid_rows"] == []
    assert result["invalid_rows"] == []