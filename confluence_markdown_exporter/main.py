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


@app.command(help="Export one or more Confluence pages by ID or URL to Markdown.")
def pages(
    pages: Annotated[list[str], typer.Argument(help="Page ID(s) or URL(s)")],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    *,
    incremental: Annotated[
        bool,
        typer.Option(
            "--incremental",
            help="Only export pages that have changed since last export.",
        ),
    ] = False,
) -> None:
    from confluence_markdown_exporter.confluence import Page

    with measure(f"Export pages {', '.join(pages)}"):
        override_output_path_config(output_path)
        if incremental:
            LockfileManager.init()
        for page in pages:
            if incremental:
                _page_with_version = (
                    Page.from_id(int(page), expand="version")
                    if page.isdigit()
                    else Page.from_url(page, expand="version")
                )
                _page = Page.from_id(_page_with_version.id)
                _page.export()
            else:
                _page = Page.from_id(int(page)) if page.isdigit() else Page.from_url(page)
                _page.export()


@app.command(help="Export Confluence pages and their descendant pages by ID or URL to Markdown.")
def pages_with_descendants(
    pages: Annotated[list[str], typer.Argument(help="Page ID(s) or URL(s)")],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    *,
    incremental: Annotated[
        bool,
        typer.Option(
            "--incremental",
            help="Only export pages that have changed since last export.",
        ),
    ] = False,
) -> None:
    from confluence_markdown_exporter.confluence import Page

    with measure(f"Export pages {', '.join(pages)} with descendants"):
        override_output_path_config(output_path)
        if incremental:
            LockfileManager.init()
        for page in pages:
            _page = (
                Page.from_id(int(page), expand="version")
                if page.isdigit()
                else Page.from_url(page, expand="version")
            )
            _page.export_with_descendants()


@app.command(help="Export all Confluence pages of one or more spaces to Markdown.")
def spaces(
    space_keys: Annotated[list[str], typer.Argument()],
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    *,
    incremental: Annotated[
        bool,
        typer.Option(
            "--incremental",
            help="Only export pages that have changed since last export.",
        ),
    ] = False,
) -> None:
    from confluence_markdown_exporter.confluence import Space

    # Personal Confluence spaces start with ~. Exporting them on Windows leads to
    # Powershell expanding tilde to the Users directory, which is handled here
    normalized_space_keys = [handle_powershell_tilde_expansion(key) for key in space_keys]

    with measure(f"Export spaces {', '.join(normalized_space_keys)}"):
        override_output_path_config(output_path)
        if incremental:
            LockfileManager.init()
        for space_key in normalized_space_keys:
            space = Space.from_key(space_key)
            space.export()


@app.command(help="Export all Confluence pages across all spaces to Markdown.")
def all_spaces(
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    *,
    incremental: Annotated[
        bool,
        typer.Option(
            "--incremental",
            help="Only export pages that have changed since last export.",
        ),
    ] = False,
) -> None:
    from confluence_markdown_exporter.confluence import Organization

    with measure("Export all spaces"):
        override_output_path_config(output_path)
        if incremental:
            LockfileManager.init()
        org = Organization.from_api()
        org.export()


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


@app.command(help="Delete exported files that are not tracked in the lockfile.")
def prune(
    output_path: Annotated[
        Path | None,
        typer.Option(help="Directory containing exported Markdown files. Overrides config if set."),
    ] = None,
    *,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show files that would be deleted without actually deleting them.",
        ),
    ] = False,
) -> None:
    """Delete exported files not tracked in the lockfile."""
    override_output_path_config(output_path)
    LockfileManager.init()
    deleted = LockfileManager.cleanup_untracked(dry_run=dry_run)
    if dry_run:
        typer.echo(f"Would delete {len(deleted)} file(s):")
        for path in deleted:
            typer.echo(f"  {path}")
    else:
        typer.echo(f"Deleted {len(deleted)} file(s).")


@app.command(help="Show the current version of confluence-markdown-exporter.")
def version() -> None:
    """Display the current version."""
    typer.echo(f"confluence-markdown-exporter {__version__}")


if __name__ == "__main__":
    app()
