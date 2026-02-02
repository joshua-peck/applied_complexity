import os
from datetime import date, timedelta

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
# import gcsfs
from google.cloud import bigquery, storage


PROJECT_ID = os.getenv["GOOGLE_CLOUD_PROJECT", 'macrocontext')
BRONZE_BQ_TABLE = os.getenv("BRONZE_BQ_TABLE", 'bronze_provider_ext')
SILVER_BUCKET = os.getenv("SILVER_BUCKET", f"{PROJECT_ID}-silver")

SERIES = os.getenv("SERIES", "us_stocks_sip")
FREQUENCY = os.getenv("FREQUENCY", "daily")
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "250"))

SYMBOL_COL = os.getenv("SYMBOL_COL", "ticker")
CLOSE_COL = os.getenv("CLOSE_COL", "close")
ISSUED_DATE_COL = os.getenv("ISSUED_DATE_COL", "issued_date")


def main():
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)

    bq = bigquery.Client(project=PROJECT_ID)

    sql = f"""
    SELECT
      {SYMBOL_COL} AS symbol,
      SAFE_CAST({ISSUED_DATE_COL} AS DATE) AS trade_date,
      SAFE_CAST({CLOSE_COL} AS FLOAT64) AS close
    FROM `{BRONZE_BQ_TABLE}`
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

    df = df.sort_values(["symbol", "trade_date"])
    df["sma_50"] = df.groupby("symbol")["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    df["sma_200"] = df.groupby("symbol")["close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    df = df.dropna(subset=["sma_50", "sma_200"])

    # use the simler upload_from_string() function instead of gcsfs
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.upload_from_string(
        df.to_parquet(index=False), 
        content_type='application/octet-stream'
    )

    # fs = gcsfs.GCSFileSystem()

    # out_path = (
    #     f"gs://{SILVER_BUCKET}/"
    #     f"domain=market/dataset=features_daily/"
    #     f"series={SERIES}/frequency={FREQUENCY}/"
    #     f"as_of={end_dt.isoformat()}/"
    #     f"sma_features.parquet"
    # )

    # table = pa.Table.from_pandas(
    #     df[["symbol", "trade_date", "close", "sma_50", "sma_200"]],
    #     preserve_index=False,
    # )

    # with fs.open(out_path, "wb") as f:
    #     pq.write_table(table, f, compression="snappy")

    print(f"Wrote {out_path}")
    print(df.groupby("symbol").tail(1)[["symbol", "trade_date", "sma_50", "sma_200"]])


if __name__ == "__main__":
    main()
