import os
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Annotated

import typer

from confluence_markdown_exporter import __version__
from confluence_markdown_exporter.state import ExportState
from confluence_markdown_exporter.state import ScopeEntry
from confluence_markdown_exporter.state import compute_delta
from confluence_markdown_exporter.state import load_state
from confluence_markdown_exporter.state import save_state
from confluence_markdown_exporter.state import validate_state_url
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import set_setting
from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop
from confluence_markdown_exporter.utils.measure_time import measure
from confluence_markdown_exporter.utils.platform_compat import handle_powershell_tilde_expansion
from confluence_markdown_exporter.utils.type_converter import str_to_bool

DEBUG: bool = str_to_bool(os.getenv("DEBUG", "False"))

app = typer.Typer()


def override_output_path_config(value: Path | None) -> None:
    """Override the default output path if provided."""
    if value is not None:
        set_setting("export.output_path", value)


def check_state_file_guard(
    output_path: Path,
    *,
    append: bool,
    command: str,
    args: list[str],
    confluence_url: str,
) -> ExportState:
    """Check for existing state file and create or update state accordingly.

    If a state file exists and --append is not set, prints an error message
    recommending `sync` and raises SystemExit(1).

    If a state file exists and --append is set, loads the existing state,
    validates the Confluence URL, and adds the new scope if not already present.

    If no state file exists, creates a new ExportState with the given scope.

    Args:
        output_path: Directory containing or to contain the state file.
        append: Whether --append was passed to allow adding to existing state.
        command: The export command name (e.g., "pages", "spaces").
        args: The arguments passed to the command.
        confluence_url: The currently configured Confluence instance URL.

    Returns:
        The ExportState to use for this export run.

    Raises:
        SystemExit: If state file exists and --append is not set.
        ValueError: If state file exists and Confluence URL does not match.
    """
    new_scope = ScopeEntry(command=command, args=args)
    existing_state = load_state(output_path)

    if existing_state is not None:
        if not append:
            typer.echo(
                "Error: A state file (.cme-state.json) already exists in the output "
                "directory. Use 'sync' to incrementally update, or pass '--append' to "
                "add a new scope to the existing state.",
                err=True,
            )
            raise SystemExit(1)

        # Validate URL matches
        validate_state_url(existing_state, confluence_url)

        # Add scope if not already present
        if new_scope not in existing_state.scopes:
            existing_state.scopes.append(new_scope)

        return existing_state

    # No state file, create fresh state
    return ExportState(
        confluence_url=confluence_url,
        scopes=[new_scope],
    )


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
    append: Annotated[
        bool,
        typer.Option(
            "--append",
            help="Allow adding a new scope to an existing state file.",
        ),
    ] = False,
) -> None:
    from confluence_markdown_exporter.confluence import Page
    from confluence_markdown_exporter.sync import export_and_track

    override_output_path_config(output_path)
    settings = get_settings()
    state = check_state_file_guard(
        output_path=settings.export.output_path,
        append=append,
        command="pages",
        args=list(pages),
        confluence_url=str(settings.auth.confluence.url),
    )

    with measure(f"Export pages {', '.join(pages)}"):
        page_ids = [
            Page.from_id(int(p)).id if p.isdigit() else Page.from_url(p).id
            for p in pages
        ]
        export_and_track(page_ids, state, settings.export.output_path)

    save_state(settings.export.output_path, state)


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
    append: Annotated[
        bool,
        typer.Option(
            "--append",
            help="Allow adding a new scope to an existing state file.",
        ),
    ] = False,
) -> None:
    from confluence_markdown_exporter.confluence import Page
    from confluence_markdown_exporter.sync import export_and_track

    override_output_path_config(output_path)
    settings = get_settings()
    state = check_state_file_guard(
        output_path=settings.export.output_path,
        append=append,
        command="pages_with_descendants",
        args=list(pages),
        confluence_url=str(settings.auth.confluence.url),
    )

    with measure(f"Export pages {', '.join(pages)} with descendants"):
        all_page_ids: list[int] = []
        for page in pages:
            _page = Page.from_id(int(page)) if page.isdigit() else Page.from_url(page)
            all_page_ids.extend([_page.id, *_page.descendants])
        export_and_track(all_page_ids, state, settings.export.output_path)

    save_state(settings.export.output_path, state)


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
    append: Annotated[
        bool,
        typer.Option(
            "--append",
            help="Allow adding a new scope to an existing state file.",
        ),
    ] = False,
) -> None:
    from confluence_markdown_exporter.confluence import Space
    from confluence_markdown_exporter.sync import export_and_track

    # Personal Confluence spaces start with ~. Exporting them on Windows leads to
    # Powershell expanding tilde to the Users directory, which is handled here
    normalized_space_keys = [handle_powershell_tilde_expansion(key) for key in space_keys]

    override_output_path_config(output_path)
    settings = get_settings()
    state = check_state_file_guard(
        output_path=settings.export.output_path,
        append=append,
        command="spaces",
        args=normalized_space_keys,
        confluence_url=str(settings.auth.confluence.url),
    )

    with measure(f"Export spaces {', '.join(normalized_space_keys)}"):
        all_page_ids: list[int] = []
        for space_key in normalized_space_keys:
            space = Space.from_key(space_key)
            all_page_ids.extend(space.pages)
        export_and_track(all_page_ids, state, settings.export.output_path)

    save_state(settings.export.output_path, state)


@app.command(help="Export all Confluence pages across all spaces to Markdown.")
def all_spaces(
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Directory to write exported Markdown files to. Overrides config if set."
        ),
    ] = None,
    *,
    append: Annotated[
        bool,
        typer.Option(
            "--append",
            help="Allow adding a new scope to an existing state file.",
        ),
    ] = False,
) -> None:
    from confluence_markdown_exporter.confluence import Organization
    from confluence_markdown_exporter.sync import export_and_track

    override_output_path_config(output_path)
    settings = get_settings()
    state = check_state_file_guard(
        output_path=settings.export.output_path,
        append=append,
        command="all_spaces",
        args=[],
        confluence_url=str(settings.auth.confluence.url),
    )

    with measure("Export all spaces"):
        org = Organization.from_api()
        export_and_track(org.pages, state, settings.export.output_path)

    save_state(settings.export.output_path, state)


@app.command(help="Incrementally sync previously exported pages, only re-exporting changes.")
def sync(
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Output directory containing the state file from a previous export."
            " Overrides config if set."
        ),
    ] = None,
    *,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Force re-export of all pages regardless of version.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would change without modifying any files.",
        ),
    ] = False,
) -> None:
    """Incrementally sync previously exported pages.

    Loads state from a previous export, replays scopes against the
    Confluence API, computes a delta of changes, and applies them.
    """
    from confluence_markdown_exporter.sync import execute_sync
    from confluence_markdown_exporter.sync import format_sync_report
    from confluence_markdown_exporter.sync import replay_scopes

    override_output_path_config(output_path)
    settings = get_settings()
    resolved_path = settings.export.output_path

    # Load state; fail if no state file exists
    state = load_state(resolved_path)
    if state is None:
        typer.echo(
            "Error: No state file (.cme-state.json) found in the output directory. "
            "Run an export command first to create the initial state.",
            err=True,
        )
        raise SystemExit(1)

    # Validate confluence_url matches current settings (--force updates it)
    current_url = str(settings.auth.confluence.url)
    validate_state_url(state, current_url, update=force)

    # If --force: set min_export_timestamp to force re-export of all pages
    if force:
        state.min_export_timestamp = datetime.now(tz=timezone.utc)

    # Replay scopes to get current page list from Confluence
    current_pages = replay_scopes(state)

    # Compute delta between stored state and current pages
    delta = compute_delta(state, current_pages)

    # Print the sync report
    report = format_sync_report(delta, state)
    typer.echo(report)

    # Execute sync unless --dry-run
    if not dry_run:
        execute_sync(state, delta, resolved_path)
        save_state(resolved_path, state)


@app.command(help="Show the status of a previous export without contacting the Confluence API.")
def status(
    output_path: Annotated[
        Path | None,
        typer.Option(
            help="Output directory containing the state file from a previous export."
            " Overrides config if set."
        ),
    ] = None,
) -> None:
    """Show the local state of a previous export.

    Reads the state file and displays scopes, page counts, and
    active/deleted status. Makes no API calls.
    """
    override_output_path_config(output_path)
    settings = get_settings()
    state = load_state(settings.export.output_path)
    if state is None:
        typer.echo("No previous export found. Run an export command first.")
        return

    typer.echo(f"Confluence URL: {state.confluence_url}")
    typer.echo(f"Schema version: {state.schema_version}")
    typer.echo("")

    # Display scopes
    typer.echo("Scopes:")
    for scope in state.scopes:
        args_str = " ".join(scope.args) if scope.args else "(none)"
        typer.echo(f"  {scope.command} {args_str}")

    typer.echo("")

    # Count active and deleted pages
    active_count = sum(1 for p in state.pages.values() if p.status == "active")
    deleted_count = sum(1 for p in state.pages.values() if p.status == "deleted")
    total_count = len(state.pages)

    typer.echo(f"Pages tracked: {total_count}")
    typer.echo(f"  Active: {active_count}")
    typer.echo(f"  Deleted: {deleted_count}")

    if state.min_export_timestamp is not None:
        typer.echo(f"\nForce re-export before: {state.min_export_timestamp.isoformat()}")


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
