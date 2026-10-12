
import json

from src.report_builder import build_reports


def test_all_reports_are_generated(tmp_path):
    report = {
        "report_version": "1.0",
        "job": {
            "job_id": "test-job",
            "status": "COMPLETED",
            "source_file": "sales.csv",
        },
        "file": {"file_name": "sales.csv"},
        "summary": {
            "total_rows": 1,
            "valid_rows": 1,
            "invalid_rows": 0,
            "validation_success_rate_percent": 100,
        },
        "business_metrics": {
            "total_units_sold": 2,
            "total_revenue": 200,
            "average_order_value": 200,
            "highest_value_order": {
                "order_id": "ORD001",
                "value": 200,
            },
        },
        "product_analysis": [],
        "regional_analysis": [],
        "data_quality": {
            "missing_values_by_column": {},
            "duplicate_order_ids": 0,
        },
    }

    artifacts = build_reports(report, [], str(tmp_path))

    assert len(artifacts) == 4

    for artifact in artifacts.values():
        assert (tmp_path / artifact.split("/")[-1]).exists() or (
            __import__("pathlib").Path(artifact).exists()
        )

    saved = json.loads(
        (tmp_path / "analytics-report.json").read_text(encoding="utf-8")
    )
    assert saved["job"]["job_id"] == "test-job"

    html_report = (
        tmp_path / "analytics-report.html"
    ).read_text(encoding="utf-8")

    assert "CSV Analytics Report" in html_report
    assert "Product performance" in html_report
