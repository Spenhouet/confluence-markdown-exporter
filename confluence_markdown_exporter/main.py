import os
from pathlib import Path
from typing import Annotated

import typer

from confluence_markdown_exporter.utils.app_data_store import set_setting
from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop
from confluence_markdown_exporter.utils.measure_time import measure

DEBUG: bool = bool(os.getenv("DEBUG"))

app = typer.Typer()


def override_output_path_config(value: Path | None) -> None:
    """Override the default output path if provided."""
    if value is not None:
        set_setting("export.output_path", value)


@app.command(help="Export a single Confluence page by ID or URL to Markdown.")
def page(
    page: Annotated[str, typer.Argument(help="Page ID or URL")],
    output_path: Annotated[Path | None, typer.Argument()] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Page

    with measure(f"Export page {page}"):
        override_output_path_config(output_path)
        _page = Page.from_id(int(page)) if page.isdigit() else Page.from_url(page)
        _page.export()


@app.command(help="Export a Confluence page and all its descendant pages by ID or URL to Markdown.")
def page_with_descendants(
    page: Annotated[str, typer.Argument(help="Page ID or URL")],
    output_path: Annotated[Path | None, typer.Argument()] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Page

    with measure(f"Export page {page} with descendants"):
        override_output_path_config(output_path)
        _page = Page.from_id(int(page)) if page.isdigit() else Page.from_url(page)
        _page.export_with_descendants()


@app.command(help="Export all Confluence pages of a single space to Markdown.")
def space(
    space_key: Annotated[str, typer.Argument()],
    output_path: Annotated[Path | None, typer.Argument()] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Space

    with measure(f"Export space {space_key}"):
        override_output_path_config(output_path)
        space = Space.from_key(space_key)
        space.export()


@app.command(help="Export all Confluence pages across all spaces to Markdown.")
def all_spaces(
    output_path: Annotated[Path | None, typer.Argument()] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Organization

    with measure("Export all spaces"):
        override_output_path_config(output_path)
        org = Organization.from_api()
        org.export()


@app.command(help="Open the interactive configuration menu.")
def config(
    jump_to: str = typer.Option(
        None, help="Jump directly to a config submenu, e.g. 'auth.confluence'"
    ),
) -> None:
    """Interactive configuration menu."""
    main_config_menu_loop(jump_to)


if __name__ == "__main__":
    app()
