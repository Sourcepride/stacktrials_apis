import subprocess
from pathlib import Path

import click

BASE_DIR = Path(__file__).resolve().parent
I18N_DIR = BASE_DIR / "app" / "i18n"


@click.group()
def i18n():
    """i18n utilities"""


@i18n.command()
def sync():
    """Sync translation keys across all locales"""
    subprocess.run(["python", str(I18N_DIR / "sync.py")])


@i18n.command()
def extract():
    """Scan Python source code and extract used translation keys"""
    subprocess.run(["python", str(I18N_DIR / "extract.py")])


cli = click.CommandCollection(sources=[i18n])

if __name__ == "__main__":
    cli()
