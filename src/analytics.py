
from collections import defaultdict


def build_analytics(validation_result: dict) -> dict:
    rows = validation_result["valid_rows"]
    total_rows = validation_result["total_rows"]
    invalid_rows = validation_result["invalid_rows"]

    total_units = sum(row["quantity"] for row in rows)
    total_revenue = round(sum(row["revenue"] for row in rows), 2)
    order_count = len(rows)

    products = defaultdict(
        lambda: {"units_sold": 0, "order_count": 0, "revenue": 0.0}
    )
    regions = defaultdict(
        lambda: {"units_sold": 0, "order_count": 0, "revenue": 0.0}
    )

    for row in rows:
        product = products[row["product"]]
        product["units_sold"] += row["quantity"]
        product["order_count"] += 1
        product["revenue"] += row["revenue"]

        region = regions[row["region"]]
        region["units_sold"] += row["quantity"]
        region["order_count"] += 1
        region["revenue"] += row["revenue"]

    product_analysis = []

    for name, values in products.items():
        revenue = round(values["revenue"], 2)
        product_analysis.append({
            "product": name,
            "units_sold": values["units_sold"],
            "order_count": values["order_count"],
            "revenue": revenue,
            "revenue_share_percent": (
                round(revenue / total_revenue * 100, 2)
                if total_revenue else 0.0
            ),
        })

    product_analysis.sort(
        key=lambda item: item["revenue"],
        reverse=True,
    )

    regional_analysis = []

    for name, values in regions.items():
        revenue = round(values["revenue"], 2)
        regional_analysis.append({
            "region": name,
            "units_sold": values["units_sold"],
            "order_count": values["order_count"],
            "revenue": revenue,
            "revenue_share_percent": (
                round(revenue / total_revenue * 100, 2)
                if total_revenue else 0.0
            ),
        })

    regional_analysis.sort(
        key=lambda item: item["revenue"],
        reverse=True,
    )

    highest_order = max(
        rows,
        key=lambda row: row["revenue"],
        default=None,
    )

    return {
        "summary": {
            "total_rows": total_rows,
            "valid_rows": len(rows),
            "invalid_rows": len(invalid_rows),
            "validation_success_rate_percent": (
                round(len(rows) / total_rows * 100, 2)
                if total_rows else 0.0
            ),
        },
        "business_metrics": {
            "total_units_sold": total_units,
            "total_revenue": total_revenue,
            "average_order_value": (
                round(total_revenue / order_count, 2)
                if order_count else 0.0
            ),
            "highest_value_order": (
                {
                    "order_id": highest_order["order_id"],
                    "product": highest_order["product"],
                    "value": highest_order["revenue"],
                }
                if highest_order else None
            ),
        },
        "product_analysis": product_analysis,
        "regional_analysis": regional_analysis,
        "data_quality": {
            "missing_values_by_column":
                validation_result["missing_values_by_column"],
            "duplicate_order_ids":
                validation_result["duplicate_order_ids"],
        },
    }
