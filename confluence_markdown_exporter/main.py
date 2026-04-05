import logging
from typing import Annotated

import typer
import typer.rich_utils
from rich.panel import Panel
from rich.table import Table

from confluence_markdown_exporter import __version__
from confluence_markdown_exporter import config as config_module
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.lockfile import LockfileManager
from confluence_markdown_exporter.utils.measure_time import measure
from confluence_markdown_exporter.utils.rich_console import console
from confluence_markdown_exporter.utils.rich_console import get_rich_console
from confluence_markdown_exporter.utils.rich_console import get_stats
from confluence_markdown_exporter.utils.rich_console import reset_stats
from confluence_markdown_exporter.utils.rich_console import setup_logging

typer.rich_utils._get_rich_console = get_rich_console

logger = logging.getLogger(__name__)


# Each list item must be its own \n\n-separated block so typer's epilog renderer
# keeps single \n between items, forming a valid markdown bullet list.
_QUICKSTART_EPILOG = (
    "**Quick start:**\n\n"
    "- Configure credentials: `cme config edit auth.confluence`\n\n"
    "- Set output path: `cme config set export.output_path=./output`\n\n"
    "- Export a page: `cme pages https://company.atlassian.net/wiki/spaces/KEY/pages/123/Title`\n\n"
    "- Export a space: `cme spaces https://company.atlassian.net/wiki/spaces/MYSPACE`\n\n"
    "- Export everything: `cme orgs https://company.atlassian.net`\n\n"
    "- Each command also has a singular alias"
    " (`page`, `space`, `org`) that behaves identically.\n\n"
)

_PAGE_URL_FORMATS = (
    "**Supported URL formats:**\n\n"
    "- **Cloud**: `https://company.atlassian.net/wiki/spaces/KEY/pages/123/Title`\n\n"
    "- **Server (long)**: `https://confluence.company.com/display/KEY/Title`\n\n"
    "- **Server (short)**: `https://confluence.company.com/KEY/Title`\n\n"
)

_SPACE_URL_FORMATS = (
    "**Supported URL formats:**\n\n"
    "- **Cloud**: `https://company.atlassian.net/wiki/spaces/SPACEKEY`\n\n"
    "- **Server (long)**: `https://confluence.company.com/display/SPACEKEY`\n\n"
    "- **Server (short)**: `https://confluence.company.com/SPACEKEY`\n\n"
)

app = typer.Typer(
    rich_markup_mode="markdown",
    no_args_is_help=True,
    help=(
        "Export Confluence pages, spaces, or entire organizations to Markdown files.\n\n"
        "Authentication and settings are managed via `cme config`. "
        "Run `cme config` to open the interactive menu, or use "
        "`cme config set <key=value>` to set values directly.\n\n"
        "Most settings can also be overridden with environment variables using the prefix "
        "`CME_` and `__` as the nested delimiter "
        "(e.g. `CME_EXPORT__OUTPUT_PATH=/tmp/export`)."
    ),
    epilog=_QUICKSTART_EPILOG,
)
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

    grid.add_row("Pages", "")
    grid.add_row("  Total", str(stats.total))
    grid.add_row("  [success]Exported[/success]", f"[success]{stats.exported}[/success]")
    grid.add_row("  [dim]Skipped (unchanged)[/dim]", str(stats.skipped))
    if stats.removed:
        grid.add_row("  [dim]Removed[/dim]", str(stats.removed))
    if stats.failed:
        grid.add_row("  [error]Failed[/error]", f"[error]{stats.failed}[/error]")

    attachments_total = (
        stats.attachments_exported + stats.attachments_skipped + stats.attachments_failed
    )
    if attachments_total or stats.attachments_removed:
        grid.add_row("Attachments", "")
        if attachments_total:
            grid.add_row("  Total", str(attachments_total))
        att_exp = stats.attachments_exported
        grid.add_row("  [success]Exported[/success]", f"[success]{att_exp}[/success]")
        grid.add_row("  [dim]Skipped (unchanged)[/dim]", str(stats.attachments_skipped))
        if stats.attachments_removed:
            grid.add_row("  [dim]Removed[/dim]", str(stats.attachments_removed))
        if stats.attachments_failed:
            grid.add_row("  [error]Failed[/error]", f"[error]{stats.attachments_failed}[/error]")

    grid.add_row("Output", str(output_path))

    if stats.failed:
        title = "[warning]Export finished with errors[/warning]"
    else:
        title = "[success]Export complete[/success]"
    console.print(Panel(grid, title=title, expand=False))


@app.command(
    help=(
        "Export one or more Confluence pages by URL to Markdown.\n\n"
        "Fetches each page via the Confluence API and writes a Markdown file to the "
        "configured output directory (`export.output_path`). "
        "Pages that have not changed since the last export are skipped by default "
        "(`export.skip_unchanged=true`)."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme pages https://company.atlassian.net/wiki/spaces/KEY/pages/123/My+Page`\n\n"
        "- `cme pages https://...page1 https://...page2` — export multiple pages at once\n\n"
        "- `cme page URL` — singular alias, identical behaviour\n\n"
        "---\n\n" + _PAGE_URL_FORMATS
    ),
)
def pages(
    page_urls: Annotated[
        list[str],
        typer.Argument(
            help=(
                "One or more Confluence page URLs. "
                "Supports Cloud and Server URL formats. "
                "Example: https://company.atlassian.net/wiki/spaces/KEY/pages/123/Title"
            ),
            metavar="PAGE_URL",
        ),
    ],
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
            LockfileManager.mark_seen([page.id])
            if not LockfileManager.should_export(page):
                stats.inc_skipped()
                exported_urls.add(page.base_url)
                continue
            with console.status(f"[dim]Exporting [highlight]{page.title}[/highlight]…[/dim]"):
                try:
                    attachment_entries = page.export()
                    LockfileManager.record_page(page, attachment_entries)
                    stats.inc_exported()
                except Exception:
                    logger.exception("Failed to export page %s", page.title)
                    stats.inc_failed()
            exported_urls.add(page.base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)

    _print_summary()


app.command(
    name="page",
    help=(
        "Alias for `pages`. Export one or more Confluence pages by URL to Markdown.\n\n"
        "See `cme pages --help` for full documentation and all supported URL formats."
    ),
    epilog=(
        "**Example:**\n\n"
        "- `cme page https://company.atlassian.net/wiki/spaces/KEY/pages/123/My+Page`\n\n"
    ),
)(pages)


@app.command(
    help=(
        "Export one or more Confluence pages **and all their descendants** by URL to Markdown.\n\n"
        "Recursively fetches the given page(s) and every child page beneath them, "
        "then writes Markdown files to the configured output directory. "
        "Useful for exporting entire page trees without exporting a whole space."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme pages-with-descendants https://company.atlassian.net/wiki/spaces/KEY/pages/123/Root`\n\n"
        "- `cme pages-with-descendants https://...root1 https://...root2` — multiple trees\n\n"
        "- `cme page-with-descendants URL` — singular alias, identical behaviour\n\n"
        "---\n\n" + _PAGE_URL_FORMATS
    ),
)
def pages_with_descendants(
    page_urls: Annotated[
        list[str],
        typer.Argument(
            help=(
                "One or more Confluence page URLs. "
                "Each page and all its descendants will be exported. "
                "Example: https://company.atlassian.net/wiki/spaces/KEY/pages/123/Title"
            ),
            metavar="PAGE_URL",
        ),
    ],
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
    help=(
        "Alias for `pages-with-descendants`. "
        "Export a Confluence page and all its descendants by URL to Markdown.\n\n"
        "See `cme pages-with-descendants --help` for full documentation."
    ),
    epilog=(
        "**Example:**\n\n"
        "- `cme page-with-descendants https://company.atlassian.net/wiki/spaces/KEY/pages/123/Root`\n\n"
    ),
)(pages_with_descendants)


@app.command(
    help=(
        "Export **all pages** in one or more Confluence spaces by URL to Markdown.\n\n"
        "Fetches every page in each space via the Confluence API and writes Markdown files "
        "to the configured output directory. "
        "Pages that have not changed since the last export are skipped by default."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme spaces https://company.atlassian.net/wiki/spaces/MYSPACE`\n\n"
        "- `cme spaces https://...SPACE1 https://...SPACE2` — export multiple spaces\n\n"
        "- `cme space URL` — singular alias, identical behaviour\n\n"
        "---\n\n" + _SPACE_URL_FORMATS
    ),
)
def spaces(
    space_urls: Annotated[
        list[str],
        typer.Argument(
            help=(
                "One or more Confluence space URLs. "
                "All pages within each space will be exported. "
                "Example: https://company.atlassian.net/wiki/spaces/MYSPACE"
            ),
            metavar="SPACE_URL",
        ),
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


app.command(
    name="space",
    help=(
        "Alias for `spaces`. Export all pages in a Confluence space by URL to Markdown.\n\n"
        "See `cme spaces --help` for full documentation and all supported URL formats."
    ),
    epilog=("**Example:**\n\n- `cme space https://company.atlassian.net/wiki/spaces/MYSPACE`\n\n"),
)(spaces)


@app.command(
    help=(
        "Export **all spaces** of one or more Confluence organizations to Markdown.\n\n"
        "Iterates over every space in the organization and exports all pages in each. "
        "This is the broadest export scope — use `spaces` to target specific spaces, "
        "or `pages` / `pages-with-descendants` for finer-grained control.\n\n"
        "The base URL is the root of the Confluence instance, "
        "e.g. `https://company.atlassian.net`."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme orgs https://company.atlassian.net` — export everything\n\n"
        "- `cme orgs https://company1.atlassian.net https://company2.atlassian.net`"
        " — multiple orgs\n\n"
        "- `cme org URL` — singular alias, identical behaviour\n\n"
    ),
)
def orgs(
    base_urls: Annotated[
        list[str],
        typer.Argument(
            help=(
                "One or more Confluence base URLs (root of the instance). "
                "All spaces and pages within each organization will be exported. "
                "Example: https://company.atlassian.net"
            ),
            metavar="BASE_URL",
        ),
    ],
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
    help=(
        "Alias for `orgs`. "
        "Export all spaces of a Confluence organization to Markdown.\n\n"
        "See `cme orgs --help` for full documentation."
    ),
    epilog=("**Example:**\n\n- `cme org https://company.atlassian.net`\n\n"),
)(orgs)


@app.command(
    help="Show the installed version of confluence-markdown-exporter.",
)
def version() -> None:
    """Display the current version."""
    typer.echo(f"confluence-markdown-exporter {__version__}")


if __name__ == "__main__":
    app()
