import os
from datetime import date, datetime
import logging

import pandas as pd
# import gcsfs
import pyarrow.parquet as pq
import psycopg2
# from google.cloud.sql.connector import Connector, IPTypes
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_host() -> str:
    # Check if the Cloud Run Unix socket directory exists
    if os.path.exists("/cloudsql"):
        return f"/cloudsql/{INSTANCE_CONNECTION_NAME}"
    
    # Fallback to local Docker host
    return os.getenv("GOLD_POSTGRES_HOST", "host.docker.internal")

def get_report_date() -> date:
    today: date = datetime.now().date()
    report_date: str = date.fromisoformat(os.environ.get('REPORT_DATE', f"{today.year}-{today.month}-{today.day}"))
    return report_date

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", 'macrocontext')
# SILVER_BUCKET = os.getenv("SILVER_BUCKET", f"{PROJECT_ID}-silver")
INDICATOR_ID = os.getenv("INDICATOR_ID", "gold_to_spx")
REPORT_DATE = get_report_date()
GOLD_TABLE = os.getenv("GOLD_TABLE", "gold.stock_signals_daily")
REGION = os.getenv("REGION", "us-central1")
SILVER_DATA_LAKE = os.getenv("SILVER_DATA_LAKE", 'silver_lake')
SILVER_BQ_INDICATOR_TABLE = os.getenv("SILVER_BQ_INDICATOR_TABLE", 'silver_gold_to_spx_ext')

INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME", f"{PROJECT_ID}:{REGION}:{PROJECT_ID}-db-instance-dev")
GOLD_POSTGRES_HOST = get_db_host()
GOLD_POSTGRES_PORT = int(os.getenv("GOLD_POSTGRES_PORT", "5432"))
GOLD_POSTGRES_USER = os.getenv("GOLD_POSTGRES_USER", 'macrocontext')
GOLD_POSTGRES_PASSWORD = os.environ["GOLD_POSTGRES_PASSWORD"]
GOLD_POSTGRES_DB = os.getenv("GOLD_POSTGRES_DB", 'macrocontext-db')

def get_db_connection() -> psycopg2.extensions.connection:
    conn: psycopg2.connection = psycopg2.connect(
        user=GOLD_POSTGRES_USER,
        password=GOLD_POSTGRES_PASSWORD,
        database=GOLD_POSTGRES_DB,
        host=GOLD_POSTGRES_HOST,
        port=GOLD_POSTGRES_PORT,
    )
    return conn

# -- 1. pull indicator data from silver tier
# {
#     "dt": "2026-02-06T00:00:00.000Z",
#     "indicator": "gold_to_spx",
#     "base_symbol": "GLD",
#     "quote_symbol": "SPY",
#     "gold_close": 455.46,
#     "spx_close": 690.62,
#     "value": 0.6594943673800353,
#     "inverse_value": 1.5163131778860932,
#     "sma_50": 0.6067351213027519,
#     "sma_200": 0.5423472022302134,
#     "trend": "up",
#     "trend_run_id": 2
# }


def read_indicator(report_date: str) -> pd.DataFrame:
    # start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    bq = bigquery.Client(project=PROJECT_ID)
    sql = f"""
    SELECT
      SAFE_CAST(dt AS DATE) AS dt,
      SAFE_CAST(indicator AS STRING) AS indicator,
      SAFE_CAST(gold_close AS FLOAT64) AS gold_close,
      SAFE_CAST(spx_close AS FLOAT64) AS spx_close,
      SAFE_CAST(value AS FLOAT64) AS gold_to_spx_ratio,
      SAFE_CAST(inverse_value AS FLOAT64) AS spx_to_gold_ratio,
      SAFE_CAST(trend AS STRING) AS trend,
      SAFE_CAST(sma_50 AS FLOAT64) AS sma_50,
      SAFE_CAST(sma_200 AS FLOAT64) AS sma_200
    FROM `{PROJECT_ID}`.`{SILVER_DATA_LAKE}`.`{SILVER_BQ_INDICATOR_TABLE}`
    WHERE indicator = @indicator
      AND frequency IN ('daily', 'Daily')
      AND SAFE_CAST(dt AS DATE) = @report_date
    ORDER BY dt, indicator
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("indicator", "STRING", INDICATOR_ID),
            bigquery.ScalarQueryParameter("report_date", "DATE", report_date),
        ]
    )
    df = bq.query(sql, job_config=job_config).to_dataframe()
    if df.empty:
        raise SystemExit("No rows returned from Silver. Check SILVER_BQ_TABLE / columns / symbols / dates.")
    return df

# # 2) Calculate / reshape into the gold row format
# def make_gold_row(indicator_df: pd.DataFrame) -> pd.DataFrame:
#     # We expect columns from your indicator writer:
#     # dt, trend, gold_close, spx_close, value, inverse_value
#     # plus other fields (sma_50, sma_200, etc.) that we ignore.
#     required = {"dt", "trend", "gold_close", "spx_close", "value", "inverse_value"}
#     missing = required - set(indicator_df.columns)
#     if missing:
#         raise SystemExit(f"Indicator parquet missing required columns: {sorted(missing)}")

#     out = indicator_df.copy()

#     out = out.rename(columns={
#         "value": "gold_to_spx_ratio",
#         "inverse_value": "spx_to_gold_ratio",
#     })

#     # Select exactly what you want for Metabase charting
#     out = out[[
#         "dt",
#         "trend",
#         "spx_close",
#         "gold_close",
#         "gold_to_spx_ratio",
#         "spx_to_gold_ratio",
#     ]].copy()

#     # Coerce types
#     out["dt"] = pd.to_datetime(out["dt"]).dt.date
#     out["trend"] = out["trend"].astype(str)
#     for c in ["spx_close", "gold_close", "gold_to_spx_ratio", "spx_to_gold_ratio"]:
#         out[c] = pd.to_numeric(out[c], errors="coerce")

#     if out.isna().any(axis=None):
#         # keep it strict for a daily gold table
#         raise SystemExit("Computed gold row has nulls after type coercion. Check upstream indicator data.")

#     # Ensure exactly one row
#     return out.tail(1)


# # 3) Upsert into Postgres Gold
# def upsert_gold(df: pd.DataFrame) -> None:
#     schema, _ = GOLD_TABLE.split(".", 1)

#     create_sql = f"""
#     CREATE SCHEMA IF NOT EXISTS {schema};
#     CREATE TABLE IF NOT EXISTS {GOLD_TABLE} (
#       dt DATE PRIMARY KEY,
#       trend TEXT NOT NULL,
#       spx_close DOUBLE PRECISION NOT NULL,
#       gold_close DOUBLE PRECISION NOT NULL,
#       gold_to_spx_ratio DOUBLE PRECISION NOT NULL,
#       spx_to_gold_ratio DOUBLE PRECISION NOT NULL
#     );
#     """

#     upsert_sql = f"""
#     INSERT INTO {GOLD_TABLE} (
#       dt, trend, spx_close, gold_close, gold_to_spx_ratio, spx_to_gold_ratio
#     ) VALUES (%s,%s,%s,%s,%s,%s)
#     ON CONFLICT (dt) DO UPDATE SET
#       trend = EXCLUDED.trend,
#       spx_close = EXCLUDED.spx_close,
#       gold_close = EXCLUDED.gold_close,
#       gold_to_spx_ratio = EXCLUDED.gold_to_spx_ratio,
#       spx_to_gold_ratio = EXCLUDED.spx_to_gold_ratio;
#     """

#     row = df.iloc[0]
#     vals = (
#         row["dt"],
#         row["trend"],
#         float(row["spx_close"]),
#         float(row["gold_close"]),
#         float(row["gold_to_spx_ratio"]),
#         float(row["spx_to_gold_ratio"]),
#     )

#     conn = psycopg2.connect(
#         host=PGHOST, port=PGPORT, user=PGUSER, password=PGPASSWORD, dbname=PGDATABASE
#     )
#     with conn:
#         with conn.cursor() as cur:
#             cur.execute(create_sql)
#             cur.execute(upsert_sql, vals)
#     conn.close()


if __name__ == "__main__":
    conn = get_db_connection()
    logging.info(f"Connected to database: {conn.dsn}")
    ind = read_indicator(REPORT_DATE)
    logging.info(ind)
    # gold_row = make_gold_row(ind)
    # upsert_gold(gold_row)
    # print(f"Upserted {GOLD_TABLE} for dt={REPORT_DATE}")