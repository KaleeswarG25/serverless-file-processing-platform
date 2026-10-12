
from src.analytics import build_analytics


def test_business_metrics():
    validation = {
        "total_rows": 3,
        "valid_rows": [
            {
                "order_id": "ORD001",
                "product": "Laptop",
                "quantity": 2,
                "unit_price": 100,
                "region": "South",
                "revenue": 200,
            },
            {
                "order_id": "ORD002",
                "product": "Mouse",
                "quantity": 3,
                "unit_price": 50,
                "region": "North",
                "revenue": 150,
            },
        ],
        "invalid_rows": [{"row_number": 4}],
        "missing_values_by_column": {"product": 1},
        "duplicate_order_ids": 0,
    }

    report = build_analytics(validation)

    assert report["summary"]["total_rows"] == 3
    assert report["summary"]["valid_rows"] == 2
    assert report["summary"]["invalid_rows"] == 1
    assert report["summary"]["validation_success_rate_percent"] == 66.67

    assert report["business_metrics"]["total_units_sold"] == 5
    assert report["business_metrics"]["total_revenue"] == 350
    assert report["business_metrics"]["average_order_value"] == 175

    assert (
        report["business_metrics"]["highest_value_order"]["order_id"]
        == "ORD001"
    )

    assert report["product_analysis"][0]["product"] == "Laptop"
    assert report["regional_analysis"][0]["region"] == "South"


def test_empty_dataset():
    validation = {
        "total_rows": 0,
        "valid_rows": [],
        "invalid_rows": [],
        "missing_values_by_column": {},
        "duplicate_order_ids": 0,
    }

    report = build_analytics(validation)

    assert report["business_metrics"]["total_revenue"] == 0
    assert report["business_metrics"]["average_order_value"] == 0
    assert report["business_metrics"]["highest_value_order"] is None
