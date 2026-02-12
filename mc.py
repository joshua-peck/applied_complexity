#!/usr/bin/env python3
"""Unified pipeline CLI: ingestors, processors, indicators, publishers."""

import click

from ingestors import ingestors
from processors import processors
from indicators import indicators
from publishers import publishers
from backfill import cli as backfill_cli


@click.group()
def cli():
    """Medallion data pipeline."""
    pass


cli.add_command(ingestors)
cli.add_command(processors)
cli.add_command(indicators)
cli.add_command(publishers)
cli.add_command(backfill_cli, "backfill")


if __name__ == "__main__":
    cli()
