"""Sync orchestration: scope replay, execution, and reporting.

Replays export scopes against the Confluence API to discover current page
versions, then applies the computed delta by exporting new/modified/stale
pages and deleting orphans. Produces a git-status-style report of changes.
"""

import logging
from pathlib import Path

from atlassian.errors import ApiError
from requests import HTTPError
from tqdm import tqdm

from confluence_markdown_exporter.api_clients import get_confluence_instance
from confluence_markdown_exporter.confluence import Organization
from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.confluence import Space
from confluence_markdown_exporter.state import ExportState
from confluence_markdown_exporter.state import SyncDelta
from confluence_markdown_exporter.state import save_state
from confluence_markdown_exporter.state import update_page_state

logger = logging.getLogger(__name__)

confluence = get_confluence_instance()


def _fetch_page_versions(page_ids: list[int]) -> dict[str, int]:
    """Fetch lightweight page versions from Confluence API.

    Uses get_page_by_id with expand=version to avoid downloading full
    page content, making scope replay fast.

    Args:
        page_ids: List of Confluence page IDs to fetch versions for.

    Returns:
        Mapping of page_id (str) to version number.
    """
    result: dict[str, int] = {}
    for page_id in tqdm(page_ids, unit="pages", desc="Checking versions"):
        try:
            data = confluence.get_page_by_id(page_id, expand="version")
            version = data.get("version", {}).get("number", 0)
            result[str(page_id)] = version
        except (ApiError, HTTPError) as exc:
            status_code = getattr(exc, "status_code", None)
            response = getattr(exc, "response", None)
            if response is not None:
                status_code = getattr(response, "status_code", status_code)

            if status_code in (403, 404):
                logger.info(
                    "Page %s not accessible (status %s), treating as removed.",
                    page_id,
                    status_code,
                )
                continue

            logger.warning(
                "Could not fetch version for page %s (status %s), "
                "marking for re-export.",
                page_id,
                status_code,
            )
            result[str(page_id)] = 0
    return result


def _replay_spaces_scope(args: list[str]) -> dict[str, int]:
    """Replay a 'spaces' scope entry.

    Fetches all pages from each named space and returns their versions.

    Args:
        args: List of space keys.

    Returns:
        Mapping of page_id to version for all pages in the listed spaces.
    """
    all_page_ids: list[int] = []
    for space_key in tqdm(args, unit="spaces", desc="Discovering pages"):
        space = Space.from_key(space_key)
        all_page_ids.extend(space.pages)
    return _fetch_page_versions(all_page_ids)


def _replay_all_spaces_scope() -> dict[str, int]:
    """Replay an 'all-spaces' scope entry.

    Fetches all pages across all spaces in the organization.

    Returns:
        Mapping of page_id to version for all pages in the organization.
    """
    org = Organization.from_api()
    all_page_ids: list[int] = []
    for space in tqdm(org.spaces, unit="spaces", desc="Discovering pages"):
        all_page_ids.extend(space.pages)
    return _fetch_page_versions(all_page_ids)


def _replay_pages_scope(args: list[str]) -> dict[str, int]:
    """Replay a 'pages' scope entry.

    Fetches individual pages by ID and returns their versions. Uses
    Page.from_id which fetches full page data (including version),
    since these are specific pages the user requested.

    Args:
        args: List of page ID strings.

    Returns:
        Mapping of page_id to version.
    """
    result: dict[str, int] = {}
    for page_id_str in args:
        page = Page.from_id(int(page_id_str))
        result[str(page.id)] = page.page_version
    return result


def _replay_pages_with_descendants_scope(args: list[str]) -> dict[str, int]:
    """Replay a 'pages_with_descendants' scope entry.

    For each page ID, fetches the page and all its descendants,
    then returns their versions.

    Args:
        args: List of root page ID strings.

    Returns:
        Mapping of page_id to version for all pages and their descendants.
    """
    result: dict[str, int] = {}
    for page_id_str in tqdm(args, unit="pages", desc="Discovering descendants"):
        page = Page.from_id(int(page_id_str))
        result[str(page.id)] = page.page_version
        # Fetch descendant versions via lightweight API
        descendant_versions = _fetch_page_versions(page.descendants)
        result.update(descendant_versions)
    return result


def replay_scopes(state: ExportState) -> dict[str, int]:
    """Replay all scope entries from state against the Confluence API.

    Dispatches each scope entry to the appropriate handler based on the
    command field, then merges results. When the same page appears in
    multiple scopes, the merged mapping keeps the maximum positive version
    number observed for that page. Non-positive (sentinel) versions do not
    overwrite an existing positive version.

    Args:
        state: The ExportState containing scope entries to replay.

    Returns:
        Mapping of page_id (str) to current Confluence version number
        for all pages across all scopes, deduplicated by page_id.
    """
    merged: dict[str, int] = {}

    for scope in state.scopes:
        if scope.command == "spaces":
            pages = _replay_spaces_scope(scope.args)
        elif scope.command == "all-spaces":
            pages = _replay_all_spaces_scope()
        elif scope.command == "pages":
            pages = _replay_pages_scope(scope.args)
        elif scope.command == "pages-with-descendants":
            pages = _replay_pages_with_descendants_scope(scope.args)
        else:
            logger.warning(f"Unknown scope command: {scope.command}")
            continue

        for page_id, version in pages.items():
            existing = merged.get(page_id)
            if existing is not None and version <= 0:
                continue
            if existing is None or version > existing:
                merged[page_id] = version

    return merged


def export_and_track(
    page_ids: list[int],
    state: ExportState,
    output_path: Path,
) -> None:
    """Export pages and progressively track state.

    Orchestration-layer wrapper that keeps domain models (Page.export)
    free of state/persistence concerns. For each page: exports it,
    then updates and saves state.

    Inaccessible pages (title='Page not accessible') are exported
    (Page.export handles the skip internally) but not tracked in state.

    Args:
        page_ids: List of Confluence page IDs to export.
        state: The ExportState to update after each page.
        output_path: Base output directory for state file writes.
    """
    if not page_ids:
        return

    for page_id in tqdm(page_ids, unit="pages", smoothing=0.05):
        page = Page.from_id(page_id)
        page.export()

        if page.title == "Page not accessible":
            continue

        update_page_state(
            state,
            page_id=str(page.id),
            version=page.page_version,
            output_path=str(page.export_path),
        )
        save_state(output_path, state)


def execute_sync(
    state: ExportState,
    delta: SyncDelta,
    output_path: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Execute sync operations based on the computed delta.

    For new, modified, and stale pages: calls export_and_track for
    progressive exports with state tracking. For deleted pages:
    removes the local file and marks the page as deleted in state.

    Does nothing when dry_run is True.

    Args:
        state: The ExportState to update during sync.
        delta: The computed SyncDelta describing what changed.
        output_path: Base output directory for exports and state file.
        dry_run: If True, no files are written and no state is changed.
    """
    if dry_run:
        return

    # Export new, modified, and stale pages with state tracking
    pages_to_export = [
        int(pid) for pid in [*delta.new, *delta.modified, *delta.stale]
    ]
    export_and_track(pages_to_export, state, output_path)

    # Delete orphan files for removed Confluence pages
    output_root = output_path.resolve()
    for page_id in delta.deleted:
        page_state = state.pages.get(page_id)
        if page_state is not None:
            # Remove the local file, ensuring path stays within output directory
            candidate = (output_path / page_state.output_path).resolve()
            if candidate.is_relative_to(output_root):
                if candidate.exists() and candidate.is_file():
                    candidate.unlink()
                    logger.info(f"Deleted orphan file: {candidate}")
            else:
                logger.warning(
                    "Refusing to delete file outside export directory: %s",
                    candidate,
                )

            # Mark page as deleted in state
            page_state.status = "deleted"

        # Save state progressively after each deletion
        save_state(output_path, state)


def format_sync_report(delta: SyncDelta, state: ExportState) -> str:
    """Format a git-status-style report of sync changes.

    Produces output like:
        new:  path/to/new-page.md
        mod:  path/to/modified-page.md
        del:  path/to/deleted-page.md
      3 new, 1 modified, 1 deleted, 496 unchanged

    The prefix style mirrors git status for familiarity.

    Args:
        delta: The SyncDelta describing what changed.
        state: The ExportState containing output paths for pages.

    Returns:
        Formatted report string.
    """
    lines: list[str] = []

    for page_id in delta.new:
        path = state.pages.get(page_id)
        output = path.output_path if path else f"page {page_id}"
        lines.append(f"  new:  {output}")

    for page_id in delta.modified:
        path = state.pages.get(page_id)
        output = path.output_path if path else f"page {page_id}"
        lines.append(f"  mod:  {output}")

    for page_id in delta.stale:
        path = state.pages.get(page_id)
        output = path.output_path if path else f"page {page_id}"
        lines.append(f"  stale:  {output}")

    for page_id in delta.deleted:
        path = state.pages.get(page_id)
        output = path.output_path if path else f"page {page_id}"
        lines.append(f"  del:  {output}")

    # Summary line
    n_new = len(delta.new)
    n_modified = len(delta.modified)
    n_stale = len(delta.stale)
    n_deleted = len(delta.deleted)
    n_unchanged = len(delta.unchanged)
    parts = [f"{n_new} new", f"{n_modified} modified"]
    if n_stale:
        parts.append(f"{n_stale} stale")
    parts.extend([f"{n_deleted} deleted", f"{n_unchanged} unchanged"])
    lines.append(", ".join(parts))

    return "\n".join(lines)
