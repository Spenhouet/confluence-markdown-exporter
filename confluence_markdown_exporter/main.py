import os
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from confluence_markdown_exporter import __version__
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import set_setting
from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop
from confluence_markdown_exporter.utils.lockfile import LockfileManager
from confluence_markdown_exporter.utils.measure_time import measure
from confluence_markdown_exporter.utils.rich_console import console
from confluence_markdown_exporter.utils.rich_console import get_stats
from confluence_markdown_exporter.utils.rich_console import setup_logging
from confluence_markdown_exporter.utils.type_converter import str_to_bool

DEBUG: bool = str_to_bool(os.getenv("DEBUG", "False"))

app = typer.Typer()


def _init_logging() -> None:
    """Initialize logging from config (or DEBUG env override)."""
    log_level = "DEBUG" if DEBUG else get_settings().export.log_level
    setup_logging(log_level)


def override_output_path_config(value: Path | None) -> None:
    """Override the default output path if provided."""
    if value is not None:
        set_setting("export.output_path", value)


def _print_summary() -> None:
    """Print a rich summary panel with export statistics."""
    stats = get_stats()
    if stats.total == 0:
        return

    output_path = get_settings().export.output_path

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", justify="right")
    grid.add_column()

    grid.add_row("Total pages", str(stats.total))
    grid.add_row("[success]Exported[/success]", f"[success]{stats.exported}[/success]")
    grid.add_row("[dim]Skipped (unchanged)[/dim]", str(stats.skipped))
    if stats.failed:
        grid.add_row("[error]Failed[/error]", f"[error]{stats.failed}[/error]")
    grid.add_row("Output", str(output_path))

    if stats.failed:
        title = "[warning]Export finished with errors[/warning]"
    else:
        title = "[success]Export complete[/success]"
    console.print(Panel(grid, title=title, expand=False))


@app.command(help="Export one or more Confluence pages by URL to Markdown.")
def pages(
    page_urls: Annotated[list[str], typer.Argument(help="Confluence Page URL(s)")],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Page
    from confluence_markdown_exporter.confluence import sync_removed_pages

    _init_logging()
    with measure(f"Export pages {', '.join(page_urls)}"):
        override_output_path_config(output_path)
        LockfileManager.init()

        exported_urls: set[str] = set()
        for page_url in page_urls:
            page = Page.from_url(page_url)
            page.export()
            LockfileManager.record_page(page)
            exported_urls.add(page.base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)

    _print_summary()


@app.command(help="Export Confluence pages and their descendant pages by URL to Markdown.")
def pages_with_descendants(
    page_urls: Annotated[list[str], typer.Argument(help="Confluence Page URL(s)")],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Page
    from confluence_markdown_exporter.confluence import sync_removed_pages

    _init_logging()
    with measure(f"Export pages {', '.join(page_urls)} with descendants"):
        override_output_path_config(output_path)
        LockfileManager.init()

        exported_urls: set[str] = set()
        for page_url in page_urls:
            page = Page.from_url(page_url)
            page.export_with_descendants()
            exported_urls.add(page.base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)

    _print_summary()


@app.command(help="Export all Confluence pages of one or more spaces to Markdown.")
def spaces(
    space_urls: Annotated[
        list[str],
        typer.Argument(help="Confluence Space URL(s)"),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Space
    from confluence_markdown_exporter.confluence import sync_removed_pages

    _init_logging()
    with measure(f"Export spaces {', '.join(space_urls)}"):
        override_output_path_config(output_path)
        LockfileManager.init()

        exported_urls: set[str] = set()
        for space_url in space_urls:
            space = Space.from_url(space_url)
            space.export()
            exported_urls.add(space.base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)

    _print_summary()


@app.command(
    help="Export all Confluence pages across all spaces of one or more organizations to Markdown."
)
def orgs(
    base_urls: Annotated[list[str], typer.Argument(help="Confluence Base URL(s)")],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Organization
    from confluence_markdown_exporter.confluence import sync_removed_pages

    _init_logging()
    with measure("Export all spaces"):
        override_output_path_config(output_path)
        LockfileManager.init()

        for base_url in base_urls:
            org = Organization.from_url(base_url)
            org.export()
            sync_removed_pages(base_url)

    _print_summary()


@app.command(help="Open the interactive configuration menu or display current configuration.")
def config(
    jump_to: Annotated[
        str | None,
        typer.Option(help="Jump directly to a config submenu, e.g. 'auth.confluence'"),
    ] = None,
    *,
    show: Annotated[
        bool,
        typer.Option(
            "--show",
            help="Display current configuration as YAML instead of opening the interactive menu",
        ),
    ] = False,
) -> None:
    """Interactive configuration menu or display current configuration."""
    if show:
        current_settings = get_settings()
        json_output = current_settings.model_dump_json(indent=2)
        typer.echo(f"```json\n{json_output}\n```")
    else:
        main_config_menu_loop(jump_to)


@app.command(help="Show the current version of confluence-markdown-exporter.")
def version() -> None:
    """Display the current version."""
    typer.echo(f"confluence-markdown-exporter {__version__}")


if __name__ == "__main__":
    app()
