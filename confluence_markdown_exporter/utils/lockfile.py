"""Lock file handling for tracking exported Confluence pages."""

from __future__ import annotations

import logging
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError

if TYPE_CHECKING:
    from pathlib import Path

    from confluence_markdown_exporter.confluence import Page

logger = logging.getLogger(__name__)

LOCKFILE_FILENAME = ".confluence-lock.json"
LOCKFILE_VERSION = 1


class PageEntry(BaseModel):
    """Entry for a single page in the lock file."""

    title: str
    version: int
    export_path: str


class ConfluenceLock(BaseModel):
    """Lock file tracking exported Confluence data."""

    lockfile_version: int = Field(default=LOCKFILE_VERSION)
    last_export: str = Field(default="")
    pages: dict[str, PageEntry] = Field(default_factory=dict)

    @classmethod
    def load(cls, lockfile_path: Path) -> ConfluenceLock:
        """Load lock file from disk, or return empty if not exists."""
        if lockfile_path.exists():
            try:
                content = lockfile_path.read_text(encoding="utf-8")
                return cls.model_validate_json(content)
            except ValidationError:
                logger.warning(f"Failed to parse lock file: {lockfile_path}. Starting fresh.")
        return cls()

    def save(self, lockfile_path: Path) -> None:
        """Save lock file to disk.

        To handle concurrent writes, this method reads the existing lock file
        and merges it with the current state before saving.
        """
        lockfile_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing lock file and merge to handle concurrent writes
        existing = ConfluenceLock.load(lockfile_path)
        existing.pages.update(self.pages)
        existing.last_export = datetime.now(timezone.utc).isoformat()

        lockfile_path.write_text(
            existing.model_dump_json(indent=2),
            encoding="utf-8",
        )

        # Update self to reflect merged state
        self.pages = existing.pages
        self.last_export = existing.last_export

    def add_page(self, page: Page) -> None:
        """Add or update a page entry in the lock file."""
        if page.version is None:
            logger.warning(f"Page {page.id} has no version info. Skipping lock entry.")
            return

        self.pages[str(page.id)] = PageEntry(
            title=page.title,
            version=page.version.number,
            export_path=str(page.export_path),
        )


class LockfileManager:
    """Manager for lock file operations during export."""

    _lockfile_path: Path | None = None
    _lock: ConfluenceLock | None = None

    @classmethod
    def init(cls) -> None:
        """Initialize the lockfile manager using settings."""
        from confluence_markdown_exporter.utils.app_data_store import get_settings

        settings = get_settings()
        cls._lockfile_path = settings.export.output_path / LOCKFILE_FILENAME
        cls._lock = ConfluenceLock.load(cls._lockfile_path)

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if lockfile tracking is enabled."""
        return cls._lockfile_path is not None and cls._lock is not None

    @classmethod
    def record_page(cls, page: Page) -> None:
        """Record a page export to the lock file."""
        if cls._lock is None or cls._lockfile_path is None:
            return

        cls._lock.add_page(page)
        cls._lock.save(cls._lockfile_path)

    @classmethod
    def should_export(cls, page: Page) -> bool:
        """Check if a page should be exported based on lockfile state.

        Returns True if the page should be exported (not in lockfile or changed).
        """
        if cls._lock is None:
            return True

        page_id = str(page.id)
        if page_id not in cls._lock.pages:
            return True

        entry = cls._lock.pages[page_id]
        if page.version is None:
            return True

        # Export if version or export_path has changed
        return entry.version != page.version.number or entry.export_path != str(page.export_path)

    @classmethod
    def cleanup_untracked(cls, *, dry_run: bool = False) -> list[Path]:
        """Delete exported files that are not in the lockfile.

        Args:
            dry_run: If True, only return files that would be deleted without deleting.

        Returns list of deleted (or would-be-deleted) file paths.
        """
        from pathlib import Path

        from confluence_markdown_exporter.utils.app_data_store import get_settings

        if cls._lock is None:
            return []

        settings = get_settings()
        output_path = settings.export.output_path

        # Collect all export_paths from lockfile
        tracked_paths = {Path(entry.export_path) for entry in cls._lock.pages.values()}

        # Find all markdown files in output directory
        untracked: list[Path] = []
        for md_file in output_path.rglob("*.md"):
            relative_path = md_file.relative_to(output_path)
            if relative_path not in tracked_paths:
                untracked.append(relative_path)
                if not dry_run:
                    md_file.unlink()
                    logger.info(f"Deleted untracked file: {relative_path}")

        return untracked
