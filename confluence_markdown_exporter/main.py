import logging
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from confluence_markdown_exporter import __version__
from confluence_markdown_exporter import config as config_module
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.lockfile import LockfileManager
from confluence_markdown_exporter.utils.measure_time import measure
from confluence_markdown_exporter.utils.rich_console import console
from confluence_markdown_exporter.utils.rich_console import get_stats
from confluence_markdown_exporter.utils.rich_console import reset_stats
from confluence_markdown_exporter.utils.rich_console import setup_logging

logger = logging.getLogger(__name__)

app = typer.Typer()
app.add_typer(config_module.app, name="config")


def _init_logging() -> None:
    """Initialize logging from config (CME_EXPORT__LOG_LEVEL env var takes precedence)."""
    setup_logging(get_settings().export.log_level)


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
) -> None:
    from confluence_markdown_exporter.confluence import Page
    from confluence_markdown_exporter.confluence import sync_removed_pages

    _init_logging()
    stats = reset_stats(total=len(page_urls))
    with measure(f"Export pages {', '.join(page_urls)}"):
        LockfileManager.init()

        exported_urls: set[str] = set()
        for page_url in page_urls:
            with console.status(f"[dim]Fetching [highlight]{page_url}[/highlight]…[/dim]"):
                page = Page.from_url(page_url)
            with console.status(f"[dim]Exporting [highlight]{page.title}[/highlight]…[/dim]"):
                try:
                    page.export()
                    LockfileManager.record_page(page)
                    stats.inc_exported()
                except Exception:
                    logger.exception("Failed to export page %s", page.title)
                    stats.inc_failed()
            exported_urls.add(page.base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)

    _print_summary()


app.command(name="page", help="Export one or more Confluence pages by URL to Markdown.")(pages)


@app.command(help="Export Confluence pages and their descendant pages by URL to Markdown.")
def pages_with_descendants(
    page_urls: Annotated[list[str], typer.Argument(help="Confluence Page URL(s)")],
) -> None:
    from confluence_markdown_exporter.confluence import Page
    from confluence_markdown_exporter.confluence import sync_removed_pages

    _init_logging()
    with measure(f"Export pages {', '.join(page_urls)} with descendants"):
        LockfileManager.init()

        exported_urls: set[str] = set()
        for page_url in page_urls:
            page = Page.from_url(page_url)
            page.export_with_descendants()
            exported_urls.add(page.base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)

    _print_summary()


app.command(
    name="page-with-descendants",
    help="Export Confluence pages and their descendant pages by URL to Markdown.",
)(pages_with_descendants)


@app.command(help="Export all Confluence pages of one or more spaces to Markdown.")
def spaces(
    space_urls: Annotated[
        list[str],
        typer.Argument(help="Confluence Space URL(s)"),
    ],
) -> None:
    from confluence_markdown_exporter.confluence import Space
    from confluence_markdown_exporter.confluence import sync_removed_pages

    _init_logging()
    with measure(f"Export spaces {', '.join(space_urls)}"):
        LockfileManager.init()

        exported_urls: set[str] = set()
        for space_url in space_urls:
            space = Space.from_url(space_url)
            space.export()
            exported_urls.add(space.base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)

    _print_summary()


app.command(name="space", help="Export all Confluence pages of one or more spaces to Markdown.")(
    spaces
)


@app.command(
    help="Export all Confluence pages across all spaces of one or more organizations to Markdown."
)
def orgs(
    base_urls: Annotated[list[str], typer.Argument(help="Confluence Base URL(s)")],
) -> None:
    from confluence_markdown_exporter.confluence import Organization
    from confluence_markdown_exporter.confluence import sync_removed_pages

    _init_logging()
    with measure("Export all spaces"):
        LockfileManager.init()

        for base_url in base_urls:
            org = Organization.from_url(base_url)
            org.export()
            sync_removed_pages(base_url)

    _print_summary()


app.command(
    name="org",
    help="Export all Confluence pages across all spaces of one or more organizations to Markdown.",
)(orgs)


@app.command(help="Show the current version of confluence-markdown-exporter.")
def version() -> None:
    """Display the current version."""
    typer.echo(f"confluence-markdown-exporter {__version__}")


if __name__ == "__main__":
    app()
