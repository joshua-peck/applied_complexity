import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import click

ADC = str(Path("~/.config/gcloud/application_default_credentials.json").expanduser())
TAG = "pipeline-ingestors"
VERSION = "latest"


def run(
    rundate: str,
    *,
    env_file: str = ".env",
    tag: str = TAG,
    version: str = VERSION,
    series_id: str | None = None,
) -> None:
    """Run the massive ingestor container for a single date."""
    cmd = [
        "docker",
        "run",
        "-it",
        "--env-file",
        env_file,
        "-v",
        f"{ADC}:/tmp/keys/creds.json:ro",
        "-e",
        "GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json",
        "-e",
        f"REPORT_DATE={rundate}",
        "-t",
        f"{tag}:{version}",
        "python",
        "mc.py",
        "ingestors",
        "massive",
        "--report-date",
        rundate,
    ]
    if series_id is not None:
        cmd.extend(["--series-id", series_id])
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


@click.command()
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
    help="Massive series ID. Passed through to massive ingestor.",
)
def cli(
    start: datetime | None,
    end: datetime | None,
    days_ago: int | None,
    env_file: str,
    series_id: str | None,
) -> None:
    """Backfill massive ingestor by running container for each date."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if days_ago is not None:
        report_date = (datetime.today() - timedelta(days=days_ago)).date()
        logging.info(f"Running for: {report_date}")
        run(report_date.strftime("%Y-%m-%d"), env_file=env_file, series_id=series_id)
        return

    if start is None or end is None:
        raise click.UsageError("Provide --start and --end, or --days-ago")

    delta = timedelta(days=1)
    current = start.date()
    end_date = end.date()
    while current < end_date:
        logging.info(f"Running for: {current}")
        run(current.strftime("%Y-%m-%d"), env_file=env_file, series_id=series_id)
        current += delta
