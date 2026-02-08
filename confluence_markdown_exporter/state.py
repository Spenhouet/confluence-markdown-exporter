"""State file model and persistence for incremental sync.

Tracks exported page versions, scopes, and timestamps to enable
incremental sync, so only pages that have changed since the last
run are re-exported.
"""

import json
import tempfile
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

STATE_FILENAME = ".cme-state.json"


class PageState(BaseModel):
    """Tracks the export state of a single Confluence page.

    Attributes:
        version: Confluence page version number at time of export.
        last_exported: UTC timestamp of when this page was last exported.
        output_path: Relative path to the exported markdown file.
        status: Whether the page is active or has been deleted.
    """

    version: int
    last_exported: datetime
    output_path: str
    status: Literal["active", "deleted"]


class ScopeEntry(BaseModel):
    """Records which CLI command and arguments were used for an export.

    Attributes:
        command: The export command name (e.g., "pages", "spaces").
        args: The arguments passed to the command.
    """

    command: str
    args: list[str]


class ExportState(BaseModel):
    """Top-level state model persisted to .cme-state.json.

    Attributes:
        schema_version: Version of the state file schema for future migrations.
        confluence_url: The Confluence instance URL this state belongs to.
        scopes: List of export scopes (command + args) that produced this state.
        min_export_timestamp: When set, pages exported before this time are
            considered stale and will be re-exported (used by --force).
        pages: Map of page_id to PageState for all tracked pages.
    """

    schema_version: int = 1
    confluence_url: str
    scopes: list[ScopeEntry]
    min_export_timestamp: datetime | None = None
    pages: dict[str, PageState] = {}


def load_state(output_path: Path) -> ExportState | None:
    """Load export state from the output directory.

    Args:
        output_path: Directory containing the state file.

    Returns:
        The deserialized ExportState, or None if no state file exists.
    """
    state_file = output_path / STATE_FILENAME
    if not state_file.exists():
        return None
    data = json.loads(state_file.read_text(encoding="utf-8"))
    return ExportState.model_validate(data)


def save_state(output_path: Path, state: ExportState) -> None:
    """Save export state to the output directory atomically.

    Writes the state as indented JSON to a temporary file, then atomically
    replaces the target file using os.replace(). This prevents partial writes
    from corrupting the state file if the process is interrupted.

    Args:
        output_path: Directory where the state file will be written.
        state: The ExportState to persist.
    """
    output_path.mkdir(parents=True, exist_ok=True)
    state_file = output_path / STATE_FILENAME
    json_str = state.model_dump_json(indent=2)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=output_path,
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as fd:
            tmp_path = Path(fd.name)
            fd.write(json_str)
        tmp_path.replace(state_file)
    except BaseException:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def update_page_state(
    state: ExportState, page_id: str, version: int, output_path: str
) -> None:
    """Update or add a page entry in the export state.

    Sets the page status to "active" and records the current UTC time
    as last_exported. This is designed for progressive state writes
    during export. Call after each page is successfully exported.

    Args:
        state: The ExportState to mutate in place.
        page_id: Confluence page ID.
        version: Confluence page version number.
        output_path: Relative path to the exported markdown file.
    """
    state.pages[page_id] = PageState(
        version=version,
        last_exported=datetime.now(tz=timezone.utc),
        output_path=output_path,
        status="active",
    )


def validate_state_url(
    state: ExportState, current_url: str, *, update: bool = False
) -> None:
    """Validate that the state file belongs to the same Confluence instance.

    Args:
        state: The loaded ExportState.
        current_url: The currently configured Confluence URL.
        update: If True, update the state URL to match instead of raising.

    Raises:
        ValueError: If the URLs do not match and update is False.
    """
    if state.confluence_url.rstrip("/") != current_url.rstrip("/"):
        if update:
            state.confluence_url = current_url
            return
        msg = (
            f"Confluence URL mismatch: state file has '{state.confluence_url}' "
            f"but current configuration has '{current_url}'.\n"
            f"If this is the same Confluence instance (e.g. after a domain rename "
            f"or config correction), re-run with --force to update the stored URL."
        )
        raise ValueError(msg)


@dataclass
class SyncDelta:
    """Result of comparing current Confluence pages against stored state.

    Each field contains a list of page IDs that fall into that category.

    Attributes:
        new: Pages present in Confluence but not in state (first export).
        modified: Pages whose Confluence version is higher than the stored version.
        stale: Pages whose version matches but were exported before
            min_export_timestamp (triggered by --force).
        deleted: Pages active in state but no longer present in Confluence.
        unchanged: Pages whose version matches and export is recent enough.
    """

    new: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


def compute_delta(
    state: ExportState, current_pages: dict[str, int]
) -> SyncDelta:
    """Compute the delta between stored state and current Confluence pages.

    Categorizes every page into one of five buckets:
    - new: in current_pages but not in state
    - modified: in both, but current version > stored version
    - stale: in both, versions match, but last_exported < min_export_timestamp
    - deleted: active in state but absent from current_pages
    - unchanged: in both, versions match, export is recent enough

    Pages already marked as deleted in state are ignored entirely.

    Args:
        state: The current ExportState loaded from disk.
        current_pages: Mapping of page_id to current Confluence version number.

    Returns:
        A SyncDelta with page IDs grouped into the five categories.
    """
    delta = SyncDelta()

    for page_id, current_version in current_pages.items():
        page_state = state.pages.get(page_id)

        if page_state is None or page_state.status == "deleted":
            # Page not tracked or was previously deleted, treat as new
            delta.new.append(page_id)
            continue

        if current_version <= 0:
            # Sentinel version (e.g. from transient API errors), force re-export
            delta.modified.append(page_id)
            continue

        if current_version > page_state.version:
            delta.modified.append(page_id)
            continue

        # Version matches, check staleness
        if (
            state.min_export_timestamp is not None
            and page_state.last_exported < state.min_export_timestamp
        ):
            delta.stale.append(page_id)
            continue

        delta.unchanged.append(page_id)

    # Check for deleted pages: active in state but not in current_pages
    for page_id, page_state in state.pages.items():
        if page_state.status == "deleted":
            continue
        if page_id not in current_pages:
            delta.deleted.append(page_id)

    return delta
