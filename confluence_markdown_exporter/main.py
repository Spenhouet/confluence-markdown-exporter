import logging
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.logging import RichHandler

from confluence_markdown_exporter.utils.config_interactive import interactive_config_menu
from confluence_markdown_exporter.utils.measure_time import measure

DEBUG: bool = bool(os.getenv("DEBUG"))

rich_handler = RichHandler(show_path=False, markup=True)

logging.basicConfig(
    level="NOTSET" if DEBUG else "INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[rich_handler],
)

app = typer.Typer()


@app.command()
def page(
    page: Annotated[str, typer.Argument(help="Page ID or URL")],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    from confluence_markdown_exporter.confluence import Page

    with measure(f"Export page {page}"):
        _page = Page.from_id(int(page)) if page.isdigit() else Page.from_url(page)
        _page.export(output_path)


@app.command()
def page_with_descendants(
    page: Annotated[str, typer.Argument(help="Page ID or URL")],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    from confluence_markdown_exporter.confluence import Page

    with measure(f"Export page {page} with descendants"):
        _page = Page.from_id(int(page)) if page.isdigit() else Page.from_url(page)
        _page.export_with_descendants(output_path)


@app.command()
def space(
    space_key: Annotated[str, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    from confluence_markdown_exporter.confluence import Space

    with measure(f"Export space {space_key}"):
        space = Space.from_key(space_key)
        space.export(output_path)


@app.command()
def all_spaces(
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    from confluence_markdown_exporter.confluence import Organization

    with measure("Export all spaces"):
        org = Organization.from_api()
        org.export(output_path)


@app.command()
def logout_command() -> None:
    """Remove stored login credentials (log out)."""
    from confluence_markdown_exporter.api_clients import logout

    logout()


@app.command()
def config() -> None:
    """Interactive configuration menu."""
    interactive_config_menu()


if __name__ == "__main__":
    app()
