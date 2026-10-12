
import csv
import html
import json
from pathlib import Path


def build_reports(report: dict, invalid_rows: list, output_dir: str) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    json_path = output / "analytics-report.json"
    summary_path = output / "summary.csv"
    errors_path = output / "validation-errors.csv"
    html_path = output / "analytics-report.html"

    # Machine-readable report.
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Spreadsheet-friendly metrics.
    metrics = [
        ("Total rows", report["summary"]["total_rows"]),
        ("Valid rows", report["summary"]["valid_rows"]),
        ("Invalid rows", report["summary"]["invalid_rows"]),
        (
            "Validation success rate (%)",
            report["summary"]["validation_success_rate_percent"],
        ),
        ("Total units sold", report["business_metrics"]["total_units_sold"]),
        ("Total revenue", report["business_metrics"]["total_revenue"]),
        (
            "Average order value",
            report["business_metrics"]["average_order_value"],
        ),
    ]

    with summary_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["Metric", "Value"])
        writer.writerows(metrics)

    # Every rejected row, including its validation reasons.
    error_columns = [
        "row_number",
        "order_id",
        "product",
        "quantity",
        "unit_price",
        "region",
        "errors",
    ]

    with errors_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=error_columns)
        writer.writeheader()
        writer.writerows(invalid_rows)

    # Escape dynamic text so CSV values cannot inject HTML.
    def safe(value):
        return html.escape(str(value if value is not None else ""))

    def make_table(title, columns, rows):
        header = "".join(f"<th>{safe(column)}</th>" for column in columns)
        body = "".join(
            "<tr>" + "".join(
                f"<td>{safe(row.get(column, ''))}</td>"
                for column in columns
            ) + "</tr>"
            for row in rows
        )

        if not rows:
            body = (
                f'<tr><td colspan="{len(columns)}">'
                "No data available</td></tr>"
            )

        return (
            f"<section><h2>{safe(title)}</h2>"
            f"<div class='table-wrap'><table><thead><tr>{header}"
            f"</tr></thead><tbody>{body}</tbody></table></div></section>"
        )

    summary = report["summary"]
    business = report["business_metrics"]
    quality = report["data_quality"]

    cards = [
        ("Total rows", summary["total_rows"]),
        ("Valid rows", summary["valid_rows"]),
        ("Invalid rows", summary["invalid_rows"]),
        ("Total revenue", f'{business["total_revenue"]:,.2f}'),
    ]

    card_html = "".join(
        f"<article class='card'><span>{safe(label)}</span>"
        f"<strong>{safe(value)}</strong></article>"
        for label, value in cards
    )

    product_table = make_table(
        "Product performance",
        ["product", "units_sold", "order_count", "revenue",
         "revenue_share_percent"],
        report["product_analysis"],
    )

    region_table = make_table(
        "Regional performance",
        ["region", "units_sold", "order_count", "revenue",
         "revenue_share_percent"],
        report["regional_analysis"],
    )

    error_table = make_table(
        "Validation errors",
        error_columns,
        invalid_rows,
    )

    missing_table = make_table(
        "Missing values by column",
        ["column", "missing_count"],
        [
            {"column": name, "missing_count": count}
            for name, count in quality["missing_values_by_column"].items()
        ],
    )

    html_document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CSV Analytics Report</title>
<style>
:root {{ color-scheme: light; }}
body {{
  margin: 0; background: #f3f6fb; color: #172033;
  font-family: Arial, sans-serif; line-height: 1.5;
}}
main {{ max-width: 1100px; margin: auto; padding: 28px 18px; }}
header {{ background: #172554; color: white; padding: 28px;
          border-radius: 14px; }}
h1 {{ margin: 0 0 8px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit,
         minmax(180px, 1fr)); gap: 14px; margin: 22px 0; }}
.card, section {{ background: white; border-radius: 12px;
                  padding: 18px; margin-bottom: 18px; }}
.card span {{ display: block; color: #5b6475; }}
.card strong {{ display: block; font-size: 1.5rem; margin-top: 8px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e5e9f0; }}
th {{ background: #f8fafc; }}
footer {{ color: #667085; font-size: .85rem; }}
</style>
</head>
<body>
<main>
<header>
  <h1>CSV Analytics Report</h1>
  <div>Job ID: {safe(report["job"]["job_id"])}</div>
  <div>Source: {safe(report["file"]["file_name"])}</div>
  <div>Status: {safe(report["job"]["status"])}</div>
</header>
<div class="cards">{card_html}</div>
<section>
  <h2>Business overview</h2>
  <p>Total units sold: {safe(business["total_units_sold"])}</p>
  <p>Average order value: {safe(business["average_order_value"])}</p>
  <p>Validation success rate:
     {safe(summary["validation_success_rate_percent"])}%</p>
  <p>Duplicate order IDs:
     {safe(quality["duplicate_order_ids"])}</p>
</section>
{product_table}
{region_table}
{missing_table}
{error_table}
<footer>Generated by the Intelligent CSV Analytics Platform.</footer>
</main>
</body>
</html>
"""

    html_path.write_text(html_document, encoding="utf-8")

    return {
        "json_report": str(json_path),
        "summary_csv": str(summary_path),
        "errors_csv": str(errors_path),
        "html_report": str(html_path),
    }
