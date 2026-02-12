import importlib
import pathlib

import click


@click.group()
def publishers():
    """Commands for publishers (silver → gold Postgres)."""
    pass


# Dynamic Command Registration
current_path = pathlib.Path(__file__).parent
for path in current_path.glob("*.py"):
    if path.name.startswith("__"):
        continue

    module = importlib.import_module(f".{path.stem}", package=__package__)
    if hasattr(module, "cli"):
        publishers.add_command(module.cli, name=path.stem)
