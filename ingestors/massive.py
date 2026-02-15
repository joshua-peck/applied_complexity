import os
import tempfile
from datetime import date, datetime
import logging

import boto3
import botocore
import click
import pandas as pd
from google.cloud import storage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SOURCE_BUCKET_NAME = "flatfiles"
REPORT_AGGREGATIONS_MAP = {"daily": "day_aggs_v1"}


def _report_aggregation_stub(resolution: str) -> str:
    return REPORT_AGGREGATIONS_MAP[resolution]


def _massive_object_key(series_id: str, resolution: str, report_date: date) -> str:
    return (
        f"{series_id}/{resolution}/{report_date.year}/{report_date.month:02}/"
        f"{report_date.year}-{report_date.month:02}-{report_date.day:02}.csv.gz"
    )


def _gcp_blob_path(
    series_id: str, resolution: str, report_date: date, fmt: str
) -> str:
    ingest_date = datetime.now().date().strftime("%Y-%m-%d")
    fmt_report_date = f"{report_date.year}-{report_date.month:02}-{report_date.day:02}"
    return (
        f"provider=massive/series={series_id}/frequency={resolution}/"
        f"issued_date={fmt_report_date}/ingest_date={ingest_date}/"
        f"{fmt_report_date}{fmt}"
    )


def run(
    *,
    landing_zone_bucket: str,
    bronze_bucket: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    series_id: str = "us_stocks_sip",
    resolution: str = "daily",
    report_date: date | None = None,
) -> None:
    if report_date is None:
        report_date = datetime.now().date()

    storage_client = storage.Client()
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    s3 = session.client(
        "s3",
        endpoint_url="https://files.massive.com",
        config=botocore.config.Config(signature_version="s3v4"),
    )

    try:
        agg = _report_aggregation_stub(resolution)
        source_object_key = _massive_object_key(series_id, agg, report_date)

        with tempfile.TemporaryFile() as tmpfile:
            try:
                s3.download_fileobj(SOURCE_BUCKET_NAME, source_object_key, tmpfile)
                logging.info(
                    f"Massive source file downloaded: {SOURCE_BUCKET_NAME}/{source_object_key}"
                )

                tmpfile.seek(0)
                landing_zone_blob_path = _gcp_blob_path(
                    series_id, resolution, report_date, ".csv.gz"
                )
                bucket = storage_client.bucket(landing_zone_bucket)
                blob = bucket.blob(landing_zone_blob_path)
                blob.upload_from_file(tmpfile)
                logging.info(
                    f"Landing Zone file uploaded: {landing_zone_bucket}/{landing_zone_blob_path}"
                )

                tmpfile.seek(0)
                df = pd.read_csv(tmpfile, compression="gzip")
                bronze_blob_path = _gcp_blob_path(
                    series_id, resolution, report_date, ".parquet"
                )
                bucket = storage_client.bucket(bronze_bucket)
                blob = bucket.blob(bronze_blob_path)
                blob.upload_from_string(
                    df.to_parquet(index=False), content_type="application/octet-stream"
                )
                logging.info(f"Bronze file uploaded: {bronze_bucket}/{bronze_blob_path}")
            except Exception as e:
                raise SystemExit(
                    f"Error ingesting file ({source_object_key}): {type(e).__name__}: {e}"
                ) from e
    finally:
        storage_client.close()
        s3.close()


@click.command()
@click.option(
    "--report-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Report date (YYYY-MM-DD). Default: today.",
)
@click.option("--limit", type=int, default=None, help="Not used for massive")
@click.option(
    "--series-id",
    default="us_stocks_sip",
    envvar="SERIES_ID",
    help="Massive series ID. Default: us_stocks_sip.",
)
def cli(report_date: datetime | None, limit: int | None, series_id: str) -> None:
    """Ingest data from Massive S3 to landing zone and bronze."""
    landing_zone = os.environ.get("LANDING_ZONE_BUCKET")
    assert landing_zone, "Set LANDING_ZONE_BUCKET in .env or environment"
    bronze = os.environ.get("BRONZE_BUCKET")
    assert bronze, "Set BRONZE_BUCKET in .env or environment"
    aws_key = os.environ.get("MASSIVE_ACCESS_KEY_ID")
    assert aws_key, "Set MASSIVE_ACCESS_KEY_ID in .env or environment"
    aws_secret = os.environ.get("MASSIVE_SECRET_ACCESS_KEY")
    assert aws_secret, "Set MASSIVE_SECRET_ACCESS_KEY in .env or environment"
    resolution = os.environ.get("RESOLUTION", "daily")

    rd = report_date.date() if report_date else None
    run(
        landing_zone_bucket=landing_zone,
        bronze_bucket=bronze,
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        series_id=series_id,
        resolution=resolution,
        report_date=rd,
    )
