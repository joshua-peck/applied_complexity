import importlib
import pathlib

import click


@click.group()
def indicators():
    """Commands for indicator jobs (bronze/silver → silver indicators)."""
    pass


# Dynamic Command Registration
current_path = pathlib.Path(__file__).parent
for path in current_path.glob("*.py"):
    if path.name.startswith("__"):
        continue

    module = importlib.import_module(f".{path.stem}", package=__package__)
    if hasattr(module, "cli"):
        indicators.add_command(module.cli, name=path.stem)
