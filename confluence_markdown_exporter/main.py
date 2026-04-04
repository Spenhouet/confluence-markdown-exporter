import os
from pathlib import Path
from typing import Annotated

import typer

from confluence_markdown_exporter import __version__
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import set_setting
from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop
from confluence_markdown_exporter.utils.lockfile import LockfileManager
from confluence_markdown_exporter.utils.measure_time import measure
from confluence_markdown_exporter.utils.platform_compat import handle_powershell_tilde_expansion
from confluence_markdown_exporter.utils.type_converter import str_to_bool

DEBUG: bool = str_to_bool(os.getenv("DEBUG", "False"))

app = typer.Typer()


def override_output_path_config(value: Path | None) -> None:
    """Override the default output path if provided."""
    if value is not None:
        set_setting("export.output_path", value)


def _resolve_base_url(url: str | None) -> str:
    """Return the Confluence base URL to use, auto-selecting the single configured instance."""
    from confluence_markdown_exporter.api_clients import _resolve_confluence_url

    return _resolve_confluence_url(url)


@app.command(help="Export one or more Confluence pages by ID or URL to Markdown.")
def pages(
    pages: Annotated[list[str], typer.Argument(help="Page ID(s) or URL(s)")],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option(
            help=(
                "Confluence base URL (e.g. https://company.atlassian.net). "
                "Required when exporting by page ID with multiple instances configured."
            ),
        ),
    ] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Page
    from confluence_markdown_exporter.confluence import sync_removed_pages

    with measure(f"Export pages {', '.join(pages)}"):
        override_output_path_config(output_path)
        LockfileManager.init()

        exported_urls: set[str] = set()
        for page in pages:
            if page.isdigit():
                base_url = _resolve_base_url(url)
                _page = Page.from_id(int(page), base_url)
            else:
                _page = Page.from_url(page)
                base_url = _page.base_url
            _page.export()
            LockfileManager.record_page(_page)
            exported_urls.add(base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)


@app.command(help="Export Confluence pages and their descendant pages by ID or URL to Markdown.")
def pages_with_descendants(
    pages: Annotated[list[str], typer.Argument(help="Page ID(s) or URL(s)")],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option(
            help=(
                "Confluence base URL (e.g. https://company.atlassian.net). "
                "Required when exporting by page ID with multiple instances configured."
            ),
        ),
    ] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Page
    from confluence_markdown_exporter.confluence import sync_removed_pages

    with measure(f"Export pages {', '.join(pages)} with descendants"):
        override_output_path_config(output_path)
        LockfileManager.init()

        exported_urls: set[str] = set()
        for page in pages:
            if page.isdigit():
                base_url = _resolve_base_url(url)
                _page = Page.from_id(int(page), base_url)
            else:
                _page = Page.from_url(page)
                base_url = _page.base_url
            _page.export_with_descendants()
            exported_urls.add(base_url)

        for base_url in exported_urls:
            sync_removed_pages(base_url)


@app.command(help="Export all Confluence pages of one or more spaces to Markdown.")
def spaces(
    space_keys: Annotated[list[str], typer.Argument()],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option(
            help=(
                "Confluence base URL (e.g. https://company.atlassian.net). "
                "Required when multiple instances are configured."
            ),
        ),
    ] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Space
    from confluence_markdown_exporter.confluence import sync_removed_pages

    # Personal Confluence spaces start with ~. Exporting them on Windows leads to
    # Powershell expanding tilde to the Users directory, which is handled here
    normalized_space_keys = [handle_powershell_tilde_expansion(key) for key in space_keys]

    with measure(f"Export spaces {', '.join(normalized_space_keys)}"):
        override_output_path_config(output_path)
        base_url = _resolve_base_url(url)
        LockfileManager.init()
        for space_key in normalized_space_keys:
            space = Space.from_key(space_key, base_url)
            space.export()
        sync_removed_pages(base_url)


@app.command(help="Export all Confluence pages across all spaces to Markdown.")
def all_spaces(
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option(
            help=(
                "Confluence base URL (e.g. https://company.atlassian.net). "
                "Required when multiple instances are configured; "
                "omit to export from all configured instances."
            ),
        ),
    ] = None,
) -> None:
    from confluence_markdown_exporter.confluence import Organization
    from confluence_markdown_exporter.confluence import sync_removed_pages

    with measure("Export all spaces"):
        override_output_path_config(output_path)
        LockfileManager.init()

        settings = get_settings()
        if url:
            urls_to_export = [url]
        else:
            urls_to_export = list(settings.auth.confluence.keys()) or [_resolve_base_url(None)]

        for base_url in urls_to_export:
            org = Organization.from_api(base_url)
            org.export()
            sync_removed_pages(base_url)


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
