import os
from datetime import datetime
import logging

import click
import pandas as pd
from fredapi import Fred
from google.cloud import storage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def run(
    *,
    api_key: str,
    landing_zone_bucket: str,
    bronze_bucket: str,
    series_id: str = "STLFSI3",
    resolution: str = "daily",
    report_date: datetime | None = None,
) -> None:
    today = report_date.strftime("%Y-%m-%d") if report_date else datetime.now().strftime("%Y-%m-%d")
    storage_client = storage.Client()

    fred = Fred(api_key=api_key)
    data = fred.get_series(series_id)
    info = fred.get_series_info(series_id)

    landing_zone_blob_path = (
        f"provider=fred/series={series_id}/frequency={info['frequency_short']}/"
        f"issued_date={info['last_updated'][:10]}/ingest_date={today}/"
        f"{info['id']}-{info['last_updated']}.csv"
    )
    bucket = storage_client.bucket(landing_zone_bucket)
    blob = bucket.blob(landing_zone_blob_path)
    blob.upload_from_string(data.to_csv(), content_type="application/octet-stream")
    print(f"Successfully uploaded {series_id} to {landing_zone_blob_path}")

    df = data.to_frame(name="value").reset_index()
    df.columns = ["date", "value"]
    bronze_blob_path = (
        f"provider=fred/series={series_id}/frequency={info['frequency_short']}/"
        f"issued_date={info['last_updated'][:10]}/ingest_date={today}/"
        f"{info['id']}-{info['last_updated']}.parquet"
    )
    bucket = storage_client.bucket(bronze_bucket)
    blob = bucket.blob(bronze_blob_path)
    blob.upload_from_string(
        df.to_parquet(index=False), content_type="application/octet-stream"
    )
    print(f"Successfully uploaded {series_id} to {bronze_blob_path}")


@click.command()
@click.option(
    "--report-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Report date (YYYY-MM-DD). Default: today.",
)
@click.option("--limit", type=int, default=None, help="Limit number of observations (not used for FRED)")
@click.option(
    "--series-id",
    default="STLFSI3",
    envvar="SERIES_ID",
    help="FRED series ID. Default: STLFSI3.",
)
def cli(limit: int | None, report_date: datetime | None, series_id: str) -> None:
    """Ingest data from FRED API to landing zone and bronze."""
    api_key = os.environ.get("FRED_API_KEY")
    assert api_key, "Set FRED_API_KEY in .env or environment"
    landing_zone = os.environ.get("LANDING_ZONE_BUCKET")
    assert landing_zone, "Set LANDING_ZONE_BUCKET in .env or environment"
    bronze = os.environ.get("BRONZE_BUCKET")
    assert bronze, "Set BRONZE_BUCKET in .env or environment"
    resolution = os.environ.get("RESOLUTION", "daily")
    logging.info(f"{series_id}")
    run(
        api_key=api_key,
        landing_zone_bucket=landing_zone,
        bronze_bucket=bronze,
        series_id=series_id,
        resolution=resolution,
        report_date=report_date
    )
