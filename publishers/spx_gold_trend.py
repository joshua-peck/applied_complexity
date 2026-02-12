import os
from datetime import date, datetime
import logging

import click
import pandas as pd
import psycopg2
from google.cloud import bigquery

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_db_host() -> str:
    if os.path.exists("/cloudsql"):
        return f"/cloudsql/{os.environ.get('INSTANCE_CONNECTION_NAME', '')}"
    return os.getenv("GOLD_POSTGRES_HOST", "host.docker.internal")


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "macrocontext")
INDICATOR_ID = os.getenv("INDICATOR_ID", "gold_to_spx")
GOLD_TABLE = os.getenv("GOLD_TABLE", "gold.spx_gold_trend")
REGION = os.getenv("REGION", "us-central1")
SILVER_DATA_LAKE = os.getenv("SILVER_DATA_LAKE", "silver_lake")
SILVER_BQ_INDICATOR_TABLE = os.getenv(
    "SILVER_BQ_INDICATOR_TABLE", "silver_gold_to_spx_ext"
)
INSTANCE_CONNECTION_NAME = os.getenv(
    "INSTANCE_CONNECTION_NAME",
    f"{PROJECT_ID}:{REGION}:{PROJECT_ID}-db-instance-dev",
)
GOLD_POSTGRES_HOST = get_db_host()
GOLD_POSTGRES_PORT = int(os.getenv("GOLD_POSTGRES_PORT", "5432"))
GOLD_POSTGRES_USER = os.getenv("GOLD_POSTGRES_USER", "macrocontext")
GOLD_POSTGRES_DB = os.getenv("GOLD_POSTGRES_DB", "macrocontext-db")


def run(
    *,
    report_date: date | None = None,
) -> None:
    if report_date is None:
        rd = os.environ.get("REPORT_DATE")
        report_date = (
            datetime.strptime(rd, "%Y-%m-%d").date()
            if rd
            else datetime.now().date()
        )

    password = os.environ["GOLD_POSTGRES_PASSWORD"]
    conn = psycopg2.connect(
        user=GOLD_POSTGRES_USER,
        password=password,
        database=GOLD_POSTGRES_DB,
        host=GOLD_POSTGRES_HOST,
        port=GOLD_POSTGRES_PORT,
    )

    try:
        logging.info(f"Connected to database: {conn.dsn}")
        ind = _read_indicator(report_date.strftime("%Y-%m-%d"))
        logging.info(f"\n{ind}")
        gold_row = _make_gold_row(ind)
        logging.info(f"\n{gold_row}")
        _upsert_gold(conn, gold_row)
        print(f"Upserted {GOLD_TABLE} for dt={report_date}")
    finally:
        conn.close()


def _get_db_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        user=GOLD_POSTGRES_USER,
        password=os.environ["GOLD_POSTGRES_PASSWORD"],
        database=GOLD_POSTGRES_DB,
        host=GOLD_POSTGRES_HOST,
        port=GOLD_POSTGRES_PORT,
    )


def _read_indicator(report_date: str) -> pd.DataFrame:
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
        raise SystemExit(
            "No rows returned from Silver. Check SILVER_BQ_TABLE / columns / dates."
        )
    return df


def _make_gold_row(indicator_df: pd.DataFrame) -> pd.DataFrame:
    required = {
        "dt",
        "indicator",
        "trend",
        "gold_close",
        "spx_close",
        "gold_to_spx_ratio",
        "spx_to_gold_ratio",
        "sma_50",
        "sma_200",
    }
    assert required == set(indicator_df.columns), (
        f"`indicator_df` missing required columns: "
        f"{sorted(required - set(indicator_df.columns))}"
    )

    out = indicator_df[list(required)].copy()
    out["dt"] = pd.to_datetime(out["dt"]).dt.date
    for c in ["trend", "indicator"]:
        out[c] = out[c].astype(str)
    for c in [
        "spx_close",
        "gold_close",
        "gold_to_spx_ratio",
        "spx_to_gold_ratio",
        "sma_50",
        "sma_200",
    ]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    if out.isna().any(axis=None):
        raise SystemExit(
            "Computed gold row has nulls after type coercion. "
            "Check upstream indicator data."
        )

    return out.tail(1)


def _upsert_gold(conn: psycopg2.extensions.connection, df: pd.DataFrame) -> None:
    schema, _ = GOLD_TABLE.split(".", 1)
    create_sql = f"""
    CREATE SCHEMA IF NOT EXISTS {schema};
    CREATE TABLE IF NOT EXISTS {GOLD_TABLE} (
      dt DATE PRIMARY KEY,
      indicator TEXT NOT NULL,
      trend TEXT NOT NULL,
      spx_close DOUBLE PRECISION NOT NULL,
      gold_close DOUBLE PRECISION NOT NULL,
      gold_to_spx_ratio DOUBLE PRECISION NOT NULL,
      spx_to_gold_ratio DOUBLE PRECISION NOT NULL,
      sma_50 DOUBLE PRECISION NOT NULL,
      sma_200 DOUBLE PRECISION NOT NULL
    );
    """

    upsert_sql = f"""
    INSERT INTO {GOLD_TABLE} (
      dt, indicator, trend, spx_close, gold_close, gold_to_spx_ratio,
      spx_to_gold_ratio, sma_50, sma_200
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (dt) DO UPDATE SET
      indicator = EXCLUDED.indicator,
      trend = EXCLUDED.trend,
      spx_close = EXCLUDED.spx_close,
      gold_close = EXCLUDED.gold_close,
      gold_to_spx_ratio = EXCLUDED.gold_to_spx_ratio,
      spx_to_gold_ratio = EXCLUDED.spx_to_gold_ratio,
      sma_50 = EXCLUDED.sma_50,
      sma_200 = EXCLUDED.sma_200;
    """

    row = df.iloc[0]
    vals = (
        row["dt"],
        row["indicator"],
        row["trend"],
        float(row["spx_close"]),
        float(row["gold_close"]),
        float(row["gold_to_spx_ratio"]),
        float(row["spx_to_gold_ratio"]),
        float(row["sma_50"]),
        float(row["sma_200"]),
    )

    with conn.cursor() as cur:
        cur.execute(create_sql)
        cur.execute(upsert_sql, vals)
    conn.commit()


@click.command()
@click.option(
    "--report-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Report date (YYYY-MM-DD). Default: REPORT_DATE env or today.",
)
def cli(report_date: datetime | None) -> None:
    """Publish gold-to-SPX indicator from silver to gold Postgres."""
    rd = report_date.date() if report_date else None
    run(report_date=rd)
