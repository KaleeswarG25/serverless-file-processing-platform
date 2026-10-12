
import csv
import math
from collections import Counter
from pathlib import Path

REQUIRED_COLUMNS = {
    "order_id", "product", "quantity", "unit_price", "region"
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


class CSVValidationError(Exception):
    """Raised when a CSV cannot be safely processed."""


def validate_csv(file_path, max_size_bytes=MAX_FILE_SIZE_BYTES):
    path = Path(file_path)

    if not path.is_file():
        raise CSVValidationError("Input file does not exist.")

    size = path.stat().st_size

    if size == 0:
        raise CSVValidationError("CSV file is empty.")

    if size > max_size_bytes:
        raise CSVValidationError(
            f"File exceeds the configured limit of "
            f"{max_size_bytes} bytes."
        )

    valid_rows = []
    invalid_rows = []
    missing_values = Counter()
    seen_order_ids = set()
    duplicate_count = 0
    total_rows = 0

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames:
                raise CSVValidationError("CSV header is missing.")

            headers = [
                header.strip() if header else ""
                for header in reader.fieldnames
            ]

            if "" in headers or len(headers) != len(set(headers)):
                raise CSVValidationError(
                    "Empty or duplicate column names are not allowed."
                )

            missing_columns = REQUIRED_COLUMNS - set(headers)

            if missing_columns:
                raise CSVValidationError(
                    "Missing required columns: "
                    + ", ".join(sorted(missing_columns))
                )

            for row_number, raw in enumerate(reader, start=2):
                total_rows += 1
                errors = []

                # DictReader stores extra CSV fields under key None.
                if None in raw:
                    errors.append("Row has more fields than the header")

                row = {
                    key.strip(): (value or "").strip()
                    for key, value in raw.items()
                    if key is not None and key.strip()
                }

                for column in REQUIRED_COLUMNS:
                    if not row.get(column, ""):
                        missing_values[column] += 1
                        errors.append(f"Missing value: {column}")

                order_id = row.get("order_id", "")
                product = row.get("product", "")
                region = row.get("region", "")

                if order_id:
                    if order_id in seen_order_ids:
                        duplicate_count += 1
                        errors.append("Duplicate order_id")
                    else:
                        seen_order_ids.add(order_id)

                quantity = None
                unit_price = None

                try:
                    quantity = int(row.get("quantity", ""))
                    if quantity <= 0:
                        errors.append("quantity must be greater than zero")
                except (ValueError, TypeError):
                    errors.append("quantity must be a whole number")

                try:
                    unit_price = float(row.get("unit_price", ""))
                    if not math.isfinite(unit_price):
                        errors.append("unit_price must be finite")
                    elif unit_price < 0:
                        errors.append("unit_price cannot be negative")
                except (ValueError, TypeError):
                    errors.append("unit_price must be numeric")

                if errors:
                    invalid_rows.append({
                        "row_number": row_number,
                        "order_id": order_id,
                        "product": product,
                        "quantity": row.get("quantity", ""),
                        "unit_price": row.get("unit_price", ""),
                        "region": region,
                        "errors": "; ".join(errors),
                    })
                    continue

                valid_rows.append({
                    "order_id": order_id,
                    "product": product,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "region": region,
                    "revenue": round(quantity * unit_price, 2),
                })

    except UnicodeDecodeError as exc:
        raise CSVValidationError(
            "File must contain valid UTF-8 text."
        ) from exc
    except csv.Error as exc:
        raise CSVValidationError(f"Malformed CSV: {exc}") from exc

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "missing_values_by_column": dict(missing_values),
        "duplicate_order_ids": duplicate_count,
    }

def test_file_size_limit_is_enforced(tmp_path):
    from src.validator import CSVValidationError, validate_csv

    file_path = tmp_path / "large.csv"
    file_path.write_text("order_id,product\nORD1,Laptop\n", encoding="utf-8")

    with pytest.raises(CSVValidationError, match="exceeds"):
        validate_csv(file_path, max_size_bytes=5)


def test_invalid_utf8_is_rejected(tmp_path):
    from src.validator import CSVValidationError, validate_csv

    file_path = tmp_path / "invalid-encoding.csv"
    file_path.write_bytes(b"order_id,product,quantity,unit_price,region\n\xff")

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
