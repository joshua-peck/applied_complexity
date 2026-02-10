import os
from datetime import date, datetime, timedelta
import logging

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import gcsfs
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# -- 0. Config via env
today: date = datetime.now().date()
report_date_str: str = os.environ.get('REPORT_DATE', f"{today.year}-{today.month}-{today.day}")
report_date: date = datetime.strptime(report_date_str, "%Y-%m-%d").date()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", 'macrocontext')
SILVER_DATA_LAKE = os.getenv("SILVER_DATA_LAKE", 'silver_lake')
SILVER_BQ_TABLE = os.getenv("SILVER_BQ_TABLE", 'silver_us_stocks_sip_ext')
SILVER_BUCKET = os.getenv("SILVER_BUCKET", f"{PROJECT_ID}-silver")

SYMBOL_GOLD = os.getenv("SYMBOL_GOLD", "GLD")
SYMBOL_SPX = os.getenv("SYMBOL_SPX", "SPY")

DT_COL = os.getenv("DT_COL", "trade_date")
SYMBOL_COL = os.getenv("SYMBOL_COL", "symbol")
CLOSE_COL = os.getenv("CLOSE_COL", "close")

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "420"))

# -- 1. Pull data
def pull_daily_prices(end_dt: date) -> pd.DataFrame:
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    bq = bigquery.Client(project=PROJECT_ID)

    sql = f"""
    SELECT
      {SYMBOL_COL} AS symbol,
      SAFE_CAST({DT_COL} AS DATE) AS dt,
      SAFE_CAST({CLOSE_COL} AS FLOAT64) AS close
    FROM `{PROJECT_ID}`.`{SILVER_DATA_LAKE}`.`{SILVER_BQ_TABLE}`
    WHERE {SYMBOL_COL} IN UNNEST(@symbols)
      AND frequency IN ('daily', 'Daily')
      AND SAFE_CAST({DT_COL} AS DATE) BETWEEN @start_dt AND @end_dt
      AND {CLOSE_COL} IS NOT NULL
    ORDER BY dt, symbol
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("symbols", "STRING", [SYMBOL_SPX, SYMBOL_GOLD]),
            bigquery.ScalarQueryParameter("start_dt", "DATE", start_dt),
            bigquery.ScalarQueryParameter("end_dt", "DATE", end_dt),
        ]
    )

    df = bq.query(sql, job_config=job_config).to_dataframe()
    if df.empty:
        raise SystemExit("No rows returned from Silver. Check SILVER_BQ_TABLE / columns / symbols / dates.")
    return df

# -- 2. Calculate indicator series
def calculate_gold_to_spx(df: pd.DataFrame) -> pd.DataFrame:
    wide = (
        df.pivot_table(index="dt", columns="symbol", values="close", aggfunc="last")
        .sort_index()
        .reset_index()
    )

    if SYMBOL_GOLD not in wide.columns or SYMBOL_SPX not in wide.columns:
        raise SystemExit(f"Missing required symbols. Found columns: {list(wide.columns)}")

    wide = wide.rename(columns={SYMBOL_GOLD: "gold_close", SYMBOL_SPX: "spx_close"})
    wide["value"] = wide["gold_close"] / wide["spx_close"]
    wide["inverse_value"] = wide["spx_close"] / wide["gold_close"]

    wide["sma_50"] = wide["value"].rolling(50, min_periods=50).mean()
    wide["sma_200"] = wide["value"].rolling(200, min_periods=200).mean()

    # Trend rule for shading: up when SMA50 >= SMA200
    wide["trend"] = [
        "up" if (pd.notna(a) and pd.notna(b) and a >= b) else "down"
        for a, b in zip(wide["sma_50"], wide["sma_200"])
    ]

    # contiguous run id (handy for shading segments)
    wide["trend_run_id"] = (wide["trend"] != wide["trend"].shift(1)).cumsum().astype(int)

    wide["indicator"] = "gold_to_spx"
    wide["base_symbol"] = SYMBOL_GOLD
    wide["quote_symbol"] = SYMBOL_SPX

    # keep only dates where we have enough history for SMA200
    out = wide[pd.notna(wide["sma_200"])].copy()

    return out[
        [
            "dt",
            "indicator",
            "base_symbol",
            "quote_symbol",
            "gold_close",
            "spx_close",
            "value",
            "inverse_value",
            "sma_50",
            "sma_200",
            "trend",
            "trend_run_id",
        ]
    ]

# -- 3. Store one-day parquet to GCS
def gcs_output_path(dt: date) -> str:
    # descriptive filename, one file per day
    fname = f"gold_to_spx_{dt.isoformat()}.parquet"
    return (
        f"gs://{SILVER_BUCKET}/"
        f"indicator=gold_to_spx/"
        f"frequency=daily/"
        f"as_of={dt.isoformat()}/"
        f"{fname}"
    )

def write_indicator(df: pd.DataFrame, dt: date) -> None:
    # write exactly one row for that day
    print(df)
    day = df[df["dt"] == dt].copy()
    if day.empty:
        raise SystemExit(f"No computed indicator row for dt={dt.isoformat()} (not enough history or missing prices).")

    fs = gcsfs.GCSFileSystem()

    out_path = gcs_output_path(dt)
    table = pa.Table.from_pandas(day, preserve_index=False)

    with fs.open(out_path, "wb") as f:
        pq.write_table(table, f, compression="snappy")

    print("Wrote", out_path)
    print(day.to_string(index=False))


if __name__ == "__main__":
    end_dt = report_date
    raw = pull_daily_prices(end_dt=end_dt)
    indicator_df = calculate_gold_to_spx(raw)
    write_indicator(indicator_df, dt=end_dt)
