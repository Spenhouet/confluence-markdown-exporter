"""Handles secure storage and retrieval of API credentials for the exporter."""

import json
from pathlib import Path

import typer
from rich.console import Console

APP_NAME = "confluence-markdown-exporter"
APP_CONFIG_DIR = Path(typer.get_app_dir(APP_NAME))
APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = APP_CONFIG_DIR / "auth.json"

console = Console()


def save_credentials(data: dict) -> None:
    with open(STORE_PATH, "w") as f:
        json.dump(data, f)


def load_credentials() -> dict | None:
    if STORE_PATH.exists():
        with open(STORE_PATH, "r") as f:
            return json.load(f)
    return None


def delete_credentials() -> None:
    if STORE_PATH.exists():
        STORE_PATH.unlink()
