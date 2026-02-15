import os
from datetime import date, datetime, timedelta
import logging

import click
import gcsfs
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import bigquery

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "macrocontext")
SILVER_DATA_LAKE = os.getenv("SILVER_DATA_LAKE", "silver_lake")
SILVER_BQ_TABLE = os.getenv("SILVER_BQ_TABLE", "silver_us_stocks_sip_ext")
SILVER_BUCKET = os.getenv("SILVER_BUCKET", f"{PROJECT_ID}-silver")

SYMBOL_GOLD = os.getenv("SYMBOL_GOLD", "GLD")
SYMBOL_SPX = os.getenv("SYMBOL_SPX", "SPY")

DT_COL = os.getenv("DT_COL", "trade_date")
SYMBOL_COL = os.getenv("SYMBOL_COL", "symbol")
CLOSE_COL = os.getenv("CLOSE_COL", "close")

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "420"))


def run(
    *,
    end_dt: date | None = None,
    lookback_days: int = LOOKBACK_DAYS,
) -> None:
    if end_dt is None:
        rd = os.environ.get("REPORT_DATE")
        end_dt = (
            datetime.strptime(rd, "%Y-%m-%d").date()
            if rd
            else datetime.now().date()
        )

    raw = _pull_daily_prices(end_dt, lookback_days)
    indicator_df = _calculate_gold_to_spx(raw)
    _write_indicator(indicator_df, end_dt)


def _pull_daily_prices(end_dt: date, lookback_days: int) -> pd.DataFrame:
    start_dt = end_dt - timedelta(days=lookback_days)
    bq = bigquery.Client(project=PROJECT_ID)
    try:
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
            raise SystemExit(
                "No rows returned from Silver. Check SILVER_BQ_TABLE / columns / symbols / dates."
            )
        return df
    finally:
        bq.close()


def _calculate_gold_to_spx(df: pd.DataFrame) -> pd.DataFrame:
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

    wide["trend"] = [
        "up" if (pd.notna(a) and pd.notna(b) and a >= b) else "down"
        for a, b in zip(wide["sma_50"], wide["sma_200"])
    ]

    wide["trend_run_id"] = (wide["trend"] != wide["trend"].shift(1)).cumsum().astype(int)

    wide["indicator"] = "gold_to_spx"
    wide["base_symbol"] = SYMBOL_GOLD
    wide["quote_symbol"] = SYMBOL_SPX

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


def _gcs_output_path(dt: date) -> str:
    fname = f"gold_to_spx_{dt.isoformat()}.parquet"
    return (
        f"gs://{SILVER_BUCKET}/"
        f"indicator=gold_to_spx/"
        f"frequency=daily/"
        f"as_of={dt.isoformat()}/"
        f"{fname}"
    )


def _write_indicator(df: pd.DataFrame, dt: date) -> None:
    day = df[df["dt"] == dt].copy()
    if day.empty:
        raise SystemExit(
            f"No computed indicator row for dt={dt.isoformat()} "
            "(not enough history or missing prices)."
        )

    fs = gcsfs.GCSFileSystem()
    try:
        out_path = _gcs_output_path(dt)
        table = pa.Table.from_pandas(day, preserve_index=False)

        with fs.open(out_path, "wb") as f:
            pq.write_table(table, f, compression="snappy")

        print("Wrote", out_path)
        print(day.to_string(index=False))
    finally:
        fs.close()


@click.command()
@click.option(
    "--report-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="As-of date (YYYY-MM-DD). Default: REPORT_DATE env or today.",
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
    """Compute gold-to-SPX indicator from silver to silver indicator parquet."""
    end_dt = report_date.date() if report_date else None
    run(end_dt=end_dt, lookback_days=lookback_days)
