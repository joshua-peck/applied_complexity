import os
import logging
from datetime import date, datetime, timedelta

import click
import pandas as pd
from google.cloud import bigquery, storage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "macrocontext")
BRONZE_DATA_LAKE = os.getenv("BRONZE_DATA_LAKE", "bronze_lake")
BRONZE_BQ_TABLE = os.getenv("BRONZE_BQ_TABLE", "bronze_massive_ext")
SILVER_BUCKET = os.getenv("SILVER_BUCKET", f"{PROJECT_ID}-silver")

SERIES = os.getenv("SERIES", "us_stocks_sip")
FREQUENCY = os.getenv("FREQUENCY", "daily")
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "400"))

SYMBOL_COL = os.getenv("SYMBOL_COL", "ticker")
CLOSE_COL = os.getenv("CLOSE_COL", "close")
ISSUED_DATE_COL = os.getenv("ISSUED_DATE_COL", "issued_date")


def run(
    *,
    end_dt: date | None = None,
    lookback_days: int = LOOKBACK_DAYS,
) -> None:
    if end_dt is None:
        end_dt = datetime.today().date()
    start_dt = end_dt - timedelta(days=lookback_days)

    logging.info(f"Reading data from {start_dt} to {end_dt}")
    df = _read_market_data(start_dt, end_dt)
    logging.info(f"Recv'd. {len(df)} rows")

    blob_path = _gcp_blob_path(end_dt)
    logging.info(f"Storing to silver: {blob_path}")
    _store_to_silver(df, blob_path)
    logging.info("Done")
    print(df.tail())


def _read_market_data(start_dt: date, end_dt: date) -> pd.DataFrame:
    bq = bigquery.Client(project=PROJECT_ID)
    sql = f"""
    SELECT
      {SYMBOL_COL} AS symbol,
      SAFE_CAST({ISSUED_DATE_COL} AS DATE) AS trade_date,
      SAFE_CAST({CLOSE_COL} AS FLOAT64) AS close
    FROM `{PROJECT_ID}`.`{BRONZE_DATA_LAKE}`.`{BRONZE_BQ_TABLE}`
    WHERE series = @series
      AND frequency = @frequency
      AND SAFE_CAST({ISSUED_DATE_COL} AS DATE) BETWEEN @start_dt AND @end_dt
      AND {CLOSE_COL} IS NOT NULL
    ORDER BY symbol, trade_date
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("series", "STRING", SERIES),
            bigquery.ScalarQueryParameter("frequency", "STRING", FREQUENCY),
            bigquery.ScalarQueryParameter("start_dt", "DATE", start_dt),
            bigquery.ScalarQueryParameter("end_dt", "DATE", end_dt),
        ]
    )
    df = bq.query(sql, job_config=job_config).to_dataframe()
    if df.empty:
        raise SystemExit("No rows returned from Bronze")
    return df


def _gcp_blob_path(end_date: date) -> str:
    fmt_end_date = end_date.strftime("%Y-%m-%d")
    return (
        f"series={SERIES}/frequency={FREQUENCY}/as_of={fmt_end_date}/"
        f"stock_features_daily-{fmt_end_date}.parquet"
    )


def _store_to_silver(df: pd.DataFrame, to: str) -> None:
    df = df.sort_values(["symbol", "trade_date"])
    df["sma_50"] = df.groupby("symbol")["close"].transform(
        lambda s: s.rolling(50, min_periods=1).mean()
    )
    df["sma_200"] = df.groupby("symbol")["close"].transform(
        lambda s: s.rolling(200, min_periods=200).mean()
    )

    storage_client = storage.Client()
    bucket = storage_client.bucket(SILVER_BUCKET)
    blob = bucket.blob(to)
    blob.upload_from_string(
        df.to_parquet(index=False), content_type="application/octet-stream"
    )


@click.command()
@click.option(
    "--report-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="As-of date (YYYY-MM-DD). Default: today.",
)
@click.option(
    "--lookback-days",
    type=int,
    default=LOOKBACK_DAYS,
    help=f"Days of history to read. Default: {LOOKBACK_DAYS}",
)
def cli(
    report_date: datetime | None,
    lookback_days: int,
) -> None:
    """Compute stock features (SMA50, SMA200) from bronze to silver."""
    end_dt = report_date.date() if report_date else None
    run(end_dt=end_dt, lookback_days=lookback_days)
