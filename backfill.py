#!/usr/bin/env python3
"""Unified backfill script for pipeline setup. Run each stage in order: ingestors → processors → indicators → publishers."""

import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import click

ADC = str(Path("~/.config/gcloud/application_default_credentials.json").expanduser())
VERSION = "latest"

STAGE_CONFIG = {
    "ingestors": {
        "tag": "pipeline-ingestors",
        "cmd": ["ingestors", "massive"],
    },
    "processors": {
        "tag": "pipeline-processors",
        "cmd": ["processors", "stock_features_daily"],
    },
    "indicators": {
        "tag": "pipeline-indicators",
        "cmd": ["indicators", "spx_gold_daily"],
    },
    "publishers": {
        "tag": "pipeline-publishers",
        "cmd": ["publishers", "spx_gold_trend"],
    },
}


def run(
    rundate: str,
    stage: str,
    *,
    env_file: str = ".env",
    version: str = VERSION,
    series_id: str | None = None,
    interactive: bool = True,
) -> int:
    """Run the stage container for a single date. Returns 0 on success, non-zero on failure."""
    config = STAGE_CONFIG[stage]
    tag = config["tag"]
    cmd = [
        "docker",
        "run",
        "--rm",
        "--env-file",
        env_file,
        "-v",
        f"{ADC}:/tmp/keys/creds.json:ro",
        "-e",
        "GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json",
        "-e",
        f"REPORT_DATE={rundate}",
    ]
    if interactive:
        cmd.extend(["-it"])
    cmd.extend([
        "-t",
        f"{tag}:{version}",
        *config["cmd"],
        "--report-date",
        rundate,
    ])
    if series_id is not None and stage == "ingestors":
        cmd.extend(["--series-id", series_id])
    result = subprocess.run(cmd, text=True)
    return result.returncode


@click.command()
@click.option(
    "--stage",
    type=click.Choice(["ingestors", "processors", "indicators", "publishers"]),
    required=True,
    help="Pipeline stage to backfill.",
)
@click.option(
    "--start",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=False,
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--end",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=False,
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--days-ago",
    type=int,
    required=False,
    help="Run for date = today - DAYS_AGO",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    default=".env",
    help="Path to .env file",
)
@click.option(
    "--series-id",
    default=None,
    envvar="SERIES_ID",
    help="Series ID (ingestors only, e.g. us_stocks_sip). Passed through to massive ingestor.",
)
@click.option(
    "--version",
    default=VERSION,
    help=f"Docker image tag version. Default: {VERSION}",
)
@click.option(
    "--continue-on-error/--fail-fast",
    "continue_on_error",
    default=True,
    help="Skip missing dates (e.g. weekends, holidays) and continue. Default: True.",
)
@click.option(
    "--workers",
    type=int,
    default=3,
    help="Number of dates to run in parallel. Default: 3.",
)
def cli(
    stage: str,
    start: datetime | None,
    end: datetime | None,
    days_ago: int | None,
    env_file: str,
    series_id: str | None,
    version: str,
    continue_on_error: bool,
    workers: int,
) -> None:
    """Backfill pipeline by running container for each date. Run stages in order: ingestors → processors → indicators → publishers."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if days_ago is not None:
        report_date = (datetime.today() - timedelta(days=days_ago)).date()
        logging.info(f"[{stage}] Running for: {report_date}")
        rc = run(
            report_date.strftime("%Y-%m-%d"),
            stage,
            env_file=env_file,
            version=version,
            series_id=series_id,
            interactive=True,
        )
        if rc != 0 and not continue_on_error:
            raise SystemExit(rc)
        return

    if start is None or end is None:
        raise click.UsageError("Provide --start and --end, or --days-ago")

    delta = timedelta(days=1)
    current = start.date()
    end_date = end.date()
    dates = []
    while current < end_date:
        dates.append(current.strftime("%Y-%m-%d"))
        current += delta

    failed_dates: list[str] = []
    interactive = workers <= 1

    def run_one(rundate: str) -> tuple[str, int]:
        rc = run(
            rundate,
            stage,
            env_file=env_file,
            version=version,
            series_id=series_id,
            interactive=interactive,
        )
        return (rundate, rc)

    try:
        if workers <= 1:
            for rundate in dates:
                logging.info(f"[{stage}] Running for: {rundate}")
                _, rc = run_one(rundate)
                if rc != 0:
                    if continue_on_error:
                        logging.warning(f"[{stage}] Skipping {rundate} (failed, continuing)")
                        failed_dates.append(rundate)
                    else:
                        raise SystemExit(rc)
        else:
            logging.info(f"[{stage}] Running {len(dates)} dates with {workers} workers")
            executor = ThreadPoolExecutor(max_workers=workers)
            try:
                futures = {executor.submit(run_one, d): d for d in dates}
                for future in as_completed(futures):
                    rundate, rc = future.result()
                    if rc != 0:
                        if continue_on_error:
                            logging.warning(f"[{stage}] Skipping {rundate} (failed, continuing)")
                            failed_dates.append(rundate)
                        else:
                            executor.shutdown(wait=False, cancel_futures=True)
                            raise SystemExit(rc)
            except KeyboardInterrupt:
                logging.info(f"[{stage}] Interrupted (Ctrl+C), shutting down...")
                executor.shutdown(wait=False, cancel_futures=True)
                raise SystemExit(130)
            executor.shutdown(wait=True)
    except KeyboardInterrupt:
        logging.info(f"[{stage}] Interrupted (Ctrl+C)")
        raise SystemExit(130)

    if failed_dates:
        logging.info(f"[{stage}] Completed with {len(failed_dates)} skipped dates (e.g. weekends/holidays)")
