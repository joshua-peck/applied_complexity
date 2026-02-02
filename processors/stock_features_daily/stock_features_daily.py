import os
import logging
from datetime import datetime as dt
from datetime import timedelta

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import bigquery, storage

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", 'macrocontext')
BRONZE_DATA_LAKE = os.getenv("BRONZE_DATA_LAKE", 'bronze_lake')
BRONZE_BQ_TABLE = os.getenv("BRONZE_BQ_TABLE", 'bronze_massive_ext')
SILVER_BUCKET = os.getenv("SILVER_BUCKET", f"{PROJECT_ID}-silver")

SERIES = os.getenv("SERIES", "us_stocks_sip")
FREQUENCY = os.getenv("FREQUENCY", "daily")
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "400"))

SYMBOL_COL = os.getenv("SYMBOL_COL", "ticker")
CLOSE_COL = os.getenv("CLOSE_COL", "close")
ISSUED_DATE_COL = os.getenv("ISSUED_DATE_COL", "issued_date")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def read_market_data(start: dt.date, end: dt.date):
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
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("series", "STRING", SERIES),
        bigquery.ScalarQueryParameter("frequency", "STRING", FREQUENCY),
        bigquery.ScalarQueryParameter("start_dt", "DATE", start_dt),
        bigquery.ScalarQueryParameter("end_dt", "DATE", end_dt),
    ])
    df = bq.query(sql, job_config=job_config).to_dataframe()
    if df.empty:
        raise SystemExit("No rows returned from Bronze")
    return df

#     f"gs://{SILVER_BUCKET}/"
#     f"domain=market/dataset=features_daily/"
#     f"series={SERIES}/frequency={FREQUENCY}/"
#     f"as_of={end_dt.isoformat()}/"
#     f"sma_features.parquet"
def gcp_blob_path(end_date: dt.date):
    fmt_end_date = end_date.strftime("%Y-%m-%d")
    return f"series={SERIES}/frequency={FREQUENCY}/as_of={fmt_end_date}/stock_features_daily-{fmt_end_date}.parquet"

def store_to_silver(df: pd.DataFrame, to: str):
    df = df.sort_values(["symbol", "trade_date"])
    df["sma_50"] = df.groupby("symbol")["close"].transform(lambda s: s.rolling(50, min_periods=1).mean())
    df["sma_200"] = df.groupby("symbol")["close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    # df = df.dropna(subset=["sma_50", "sma_200"])
    # df = df.dropna(subset=["sma_50"])

    # use the simler upload_from_string() function instead of gcsfs
    storage_client = storage.Client()
    bucket = storage_client.bucket(SILVER_BUCKET)
    blob = bucket.blob(to)
    return blob.upload_from_string(
        df.to_parquet(index=False), 
        content_type='application/octet-stream'
    )

if __name__ == "__main__":
    end_dt = dt.today().date()
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    logging.info(f"Reading data from {start_dt} to {end_dt}")
    df = read_market_data(start_dt, end_dt)
    logging.info(f"Recv'd. {len(df)} rows")
    blob_path = gcp_blob_path(end_dt)
    logging.info(f"Storing to silver: {blob_path}")
    gcp_resp = store_to_silver(df, blob_path)
    logging.info(gcp_resp)
    print(df.tail())
