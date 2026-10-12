
import csv
import hashlib
import html
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone ,timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from src.processor import process_file
from src.validator import CSVValidationError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

MAX_FILE_SIZE = int(
    os.environ.get("MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024))
)
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "reports").strip("/")


def create_job_id(bucket, key, version_id, etag, sequencer):
    identity = (
        f"{bucket}/{key}|{version_id or etag or ''}|"
        f"{sequencer or ''}"
    )
    return hashlib.sha256(identity.encode()).hexdigest()[:32]
PROCESSING_LOCK_TTL_SECONDS = 300


def claim_processing_lock(bucket, lock_key):
    """
    Atomically claim a job using S3 conditional writes.

    Returns True if this invocation acquires the lock.
    Raises RuntimeError if another invocation holds a recent lock.
    Reclaims an expired lock using its ETag to avoid overwriting
    a lock that another invocation has already replaced.
    """
    now = datetime.now(timezone.utc)
    lock_body = now.isoformat().encode("utf-8")

    try:
        s3.put_object(
            Bucket=bucket,
            Key=lock_key,
            Body=lock_body,
            ContentType="text/plain",
            IfNoneMatch="*",
        )
        logger.info("Acquired processing lock: %s", lock_key)
        return True

    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        status = exc.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode"
        )

        if status not in (409, 412) and code not in (
            "ConditionalRequestConflict",
            "PreconditionFailed",
        ):
            raise

    # A lock already exists. Inspect its age before attempting recovery.
    try:
        lock_head = s3.head_object(
            Bucket=bucket,
            Key=lock_key,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        status = exc.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode"
        )

        # The previous lock may have disappeared between requests.
        if status == 404 or code in ("404", "NoSuchKey", "NotFound"):
            raise RuntimeError(
                "Processing lock disappeared; retry the SQS message."
            ) from exc
        raise

    lock_age = (
        now - lock_head["LastModified"]
    ).total_seconds()

    if lock_age < PROCESSING_LOCK_TTL_SECONDS:
        raise RuntimeError(
            f"Another invocation holds a recent processing lock: "
            f"{lock_key}"
        )

    # Replace only the exact stale lock observed above.
    try:
        s3.put_object(
            Bucket=bucket,
            Key=lock_key,
            Body=lock_body,
            ContentType="text/plain",
            IfMatch=lock_head["ETag"],
        )
        logger.warning("Reclaimed stale processing lock: %s", lock_key)
        return True

    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        status = exc.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode"
        )

        if status in (409, 412) or code in (
            "ConditionalRequestConflict",
            "PreconditionFailed",
        ):
            raise RuntimeError(
                "Another invocation changed the processing lock; retry."
            ) from exc

        raise
    
def upload_reports(bucket, job_id, report_dir, report):
    prefix = f"{OUTPUT_PREFIX}/{job_id}"

    report["artifacts"] = {
        "analytics_report": f"{prefix}/analytics-report.json",
        "summary_csv": f"{prefix}/summary.csv",
        "validation_errors_csv": f"{prefix}/validation-errors.csv",
        "html_report": f"{prefix}/analytics-report.html",
    }

    report_path = Path(report_dir) / "analytics-report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    files = {
        "summary_csv": ("summary.csv", "text/csv"),
        "validation_errors_csv": (
            "validation-errors.csv", "text/csv"
        ),
        "html_report": ("analytics-report.html", "text/html"),
    }

    # Upload supporting artifacts first.
    for name, (filename, content_type) in files.items():
        local_path = Path(report_dir) / filename
        s3.upload_file(
            str(local_path),
            bucket,
            report["artifacts"][name],
            ExtraArgs={"ContentType": content_type},
        )

    # Publish the JSON report last. Its existence indicates that
    # all the other report uploads completed.
    s3.upload_file(
        str(report_path),
        bucket,
        report["artifacts"]["analytics_report"],
        ExtraArgs={"ContentType": "application/json"},
    )


def publish_failure_report(bucket, job_id, key, message):
    prefix = f"{OUTPUT_PREFIX}/{job_id}"
    now = datetime.now(timezone.utc).isoformat()

    report = {
        "report_version": "1.0",
        "job": {
            "job_id": job_id,
            "source_file": key.rsplit("/", 1)[-1],
            "status": "FAILED",
            "completed_at": now,
        },
        "error": {
            "message": message,
        },
        "artifacts": {
            "analytics_report": f"{prefix}/analytics-report.json",
            "summary_csv": f"{prefix}/summary.csv",
            "validation_errors_csv": (
                f"{prefix}/validation-errors.csv"
            ),
            "html_report": f"{prefix}/analytics-report.html",
        },
    }

    summary_buffer = io.StringIO(newline="")
    summary_writer = csv.writer(summary_buffer)
    summary_writer.writerow(["Metric", "Value"])
    summary_writer.writerow(["Status", "FAILED"])
    summary = summary_buffer.getvalue()

    errors_buffer = io.StringIO(newline="")
    errors_writer = csv.writer(errors_buffer)
    errors_writer.writerow(["error"])
    errors_writer.writerow([message])
    errors = errors_buffer.getvalue()

    html_report = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CSV Processing Failure</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 900px;
       margin: 40px auto; padding: 20px; background: #f5f7fb; }}
article {{ background: white; padding: 24px; border-radius: 12px; }}
h1 {{ color: #b42318; }}
</style>
</head>
<body><article>
<h1>CSV processing failed</h1>
<p>Job ID: {html.escape(job_id)}</p>
<p>Source: {html.escape(key)}</p>
<p>Error: {html.escape(message)}</p>
</article></body></html>
"""

    s3.put_object(
        Bucket=bucket,
        Key=report["artifacts"]["summary_csv"],
        Body=summary.encode("utf-8"),
        ContentType="text/csv",
    )
    s3.put_object(
        Bucket=bucket,
        Key=report["artifacts"]["validation_errors_csv"],
        Body=errors.encode("utf-8"),
        ContentType="text/csv",
    )
    s3.put_object(
        Bucket=bucket,
        Key=report["artifacts"]["html_report"],
        Body=html_report.encode("utf-8"),
        ContentType="text/html",
    )
    s3.put_object(
        Bucket=bucket,
        Key=report["artifacts"]["analytics_report"],
        Body=json.dumps(report, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def process_s3_event(s3_event):
    if not s3_event.get("eventName", "").startswith("ObjectCreated:"):
        return

    bucket = s3_event["s3"]["bucket"]["name"]
    obj = s3_event["s3"]["object"]
    key = urllib.parse.unquote_plus(obj["key"])

    # Process uploads only. Generated reports must never re-trigger us.
    if not key.startswith("uploads/"):
        logger.info("Ignoring object outside uploads/: %s", key)
        return
    if key.endswith("/") or not key.lower().endswith(".csv"):
        logger.warning("Ignoring non-CSV upload: %s", key)
        return

    version_id = obj.get("versionId")
    etag = obj.get("eTag", "")
    sequencer = obj.get("sequencer", "")

    job_id = create_job_id(
        bucket, key, version_id, etag, sequencer
    )

    report_key = f"{OUTPUT_PREFIX}/{job_id}/analytics-report.json"
    lock_key = f"{OUTPUT_PREFIX}/{job_id}/_PROCESSING.lock"     

    # Best-effort duplicate-event handling. This is not a distributed
    # lock, so concurrent deliveries still require careful design.
    try:
        s3.head_object(Bucket=bucket, Key=report_key)
        logger.info("Report already exists for job %s", job_id)
        return
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode"
        )
        code = exc.response.get("Error", {}).get("Code")
        if status != 404 and code not in ("404", "NoSuchKey", "NotFound"):
            raise

    
    # Resolve the exact object version that triggered this event.
    # The string "null" represents a null version in S3.
    version_args = (
        {"VersionId": version_id}
        if version_id and version_id != "null"
        else {}
    )

    head = s3.head_object(
        Bucket=bucket,
        Key=key,
        **version_args,
    )
    size = head["ContentLength"]

    if size > MAX_FILE_SIZE:
        publish_failure_report(
            bucket,
            job_id,
            key,
            f"File size {size} exceeds limit {MAX_FILE_SIZE} bytes.",
        )
        return

    local_input = Path("/tmp") / f"{job_id}.csv"
    local_dir = Path("/tmp") / "reports" / job_id
    local_dir.mkdir(parents=True, exist_ok=True)

    # ExtraArgs must be supplied only when a specific version exists.
    if version_args:
        s3.download_file(
            bucket,
            key,
            str(local_input),
            ExtraArgs=version_args,
        )
    else:
        s3.download_file(bucket, key, str(local_input))


    try:
        report = process_file(
            str(local_input),
            output_root=str(local_dir.parent),
            job_id=job_id,
        )
    except CSVValidationError as exc:
        publish_failure_report(bucket, job_id, key, str(exc))
        return

    report["file"]["size_bytes"] = size
    report["file"]["version_id"] = version_id
    report["file"]["etag"] = etag

    upload_reports(
        bucket,
        job_id,
        local_dir,
        report,
    )

    logger.info(
        "Processing completed: job_id=%s source=%s",
        job_id,
        key,
    )

def lambda_handler(event, context):
    failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]

        try:
            body = json.loads(record["body"])

            if body.get("Event") == "s3:TestEvent":
                continue

            for s3_event in body.get("Records", []):
                if s3_event.get("eventSource") != "aws:s3":
                    continue

                process_s3_event(s3_event)

        except Exception:
            logger.exception(
                "Transient or unexpected failure processing SQS message %s",
                message_id,
            )
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}