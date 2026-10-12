
import argparse
import hashlib
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.analytics import build_analytics
from src.report_builder import build_reports
from src.validator import validate_csv


def calculate_sha256(file_path: Path) -> str:
    """Calculate a file's SHA-256 hash without loading it all into memory."""
    hasher = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def process_file(
    file_path: str,
    output_root: str = "output",
    job_id: str | None = None,
) -> dict:
    """
    Process a CSV and generate JSON, summary CSV, validation-error CSV,
    and HTML reports.

    Args:
        file_path: Path to the input CSV.
        output_root: Parent directory for generated job reports.
        job_id: Optional stable job identifier. Lambda can supply this
                to associate an input event with its report artifacts.

    Returns:
        The complete analytics report as a dictionary.

    Raises:
        FileNotFoundError: If the input file does not exist.
        CSVValidationError: If CSV validation fails at the file level.
        OSError: If a file cannot be read or reports cannot be written.
    """
    path = Path(file_path).resolve()

    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    # Reuse a supplied ID for AWS processing; generate one for local runs.
    job_id = job_id or uuid.uuid4().hex

    started_at = datetime.now(timezone.utc)
    file_size = path.stat().st_size
    file_hash = calculate_sha256(path)

    # Validate rows and calculate business metrics.
    validation = validate_csv(path)
    analytics = build_analytics(validation)

    completed_at = datetime.now(timezone.utc)
    duration_ms = round(
        (completed_at - started_at).total_seconds() * 1000
    )

    report = {
        "report_version": "1.0",
        "job": {
            "job_id": job_id,
            "source_file": path.name,
            "status": "COMPLETED",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_ms": duration_ms,
        },
        "file": {
            "file_name": path.name,
            "file_type": (
                mimetypes.guess_type(path.name)[0] or "text/csv"
            ),
            "size_bytes": file_size,
            "sha256": file_hash,
        },
        **analytics,
    }

    # Use a unique directory per job to prevent report collisions.
    job_output_dir = Path(output_root) / job_id

    artifacts = build_reports(
        report=report,
        invalid_rows=validation["invalid_rows"],
        output_dir=str(job_output_dir),
    )

    # Return artifact locations to callers. The Lambda handler can replace
    # local paths with their corresponding S3 keys before publishing JSON.
    report["artifacts"] = artifacts

    print(f"\n{'=' * 55}")
    print("CSV ANALYTICS JOB COMPLETED")
    print(f"{'=' * 55}")
    print(f"Job ID          : {job_id}")
    print(f"Input file      : {path.name}")
    print(f"File size       : {file_size:,} bytes")
    print(f"SHA-256         : {file_hash}")
    print(f"Total rows      : {analytics['summary']['total_rows']}")
    print(f"Valid rows      : {analytics['summary']['valid_rows']}")
    print(f"Invalid rows    : {analytics['summary']['invalid_rows']}")
    print(
        "Total revenue   : "
        f"{analytics['business_metrics']['total_revenue']:,.2f}"
    )
    print(f"Duration        : {duration_ms} ms")
    print("\nGenerated reports:")

    for name, location in artifacts.items():
        print(f"  {name}: {location}")

    print(f"{'=' * 55}\n")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Intelligent CSV Analytics Platform"
    )

    parser.add_argument(
        "file",
        help="Path to the input CSV file",
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help="Parent directory for generated reports (default: output)",
    )

    parser.add_argument(
        "--job-id",
        default=None,
        help="Optional job ID; generated automatically when omitted",
    )

    args = parser.parse_args()

    try:
        process_file(
            file_path=args.file,
            output_root=args.output_dir,
            job_id=args.job_id,
        )
    except Exception as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
