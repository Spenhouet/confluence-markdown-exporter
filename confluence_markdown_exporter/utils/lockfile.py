"""Lock file handling for tracking exported Confluence pages."""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING
from typing import ClassVar

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError

if TYPE_CHECKING:
    from confluence_markdown_exporter.confluence import Descendant
    from confluence_markdown_exporter.confluence import Page

logger = logging.getLogger(__name__)

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

    def save(self, lockfile_path: Path, *, delete_ids: set[str] | None = None) -> None:
        """Save lock file to disk.

        To handle concurrent writes, this method reads the existing lock file
        and merges it with the current state before saving.
        """
        lockfile_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing lock file and merge to handle concurrent writes
        existing = ConfluenceLock.load(lockfile_path)
        existing.pages = dict(sorted({**existing.pages, **self.pages}.items()))
        if delete_ids:
            for page_id in delete_ids:
                existing.pages.pop(page_id, None)
        existing.last_export = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(existing.model_dump(), indent=2, ensure_ascii=False)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=lockfile_path.parent,
                suffix=".tmp",
                delete=False,
                encoding="utf-8",
            ) as fd:
                tmp_path = Path(fd.name)
                fd.write(json_str)
            tmp_path.replace(lockfile_path)
        except BaseException:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            raise

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

    _lockfile_path: ClassVar[Path | None] = None
    _lock: ClassVar[ConfluenceLock | None] = None
    _output_path: ClassVar[Path | None] = None
    _all_entries_snapshot: ClassVar[dict[str, PageEntry]] = {}
    _seen_page_ids: ClassVar[set[str]] = set()

    @classmethod
    def init(cls) -> None:
        """Initialize the lockfile manager if skip_unchanged is enabled."""
        from confluence_markdown_exporter.utils.app_data_store import get_settings

        settings = get_settings()
        if not settings.export.skip_unchanged:
            return

        cls._output_path = settings.export.output_path
        cls._lockfile_path = cls._output_path / settings.export.lockfile_name
        cls._lock = ConfluenceLock.load(cls._lockfile_path)
        cls._all_entries_snapshot = dict(cls._lock.pages)
        cls._seen_page_ids = set()

    @classmethod
    def record_page(cls, page: Page) -> None:
        """Record a page export to the lock file."""
        if cls._lock is None or cls._lockfile_path is None:
            return

        cls._lock.add_page(page)
        cls._lock.save(cls._lockfile_path)
        cls._seen_page_ids.add(str(page.id))

    @classmethod
    def mark_seen(cls, page_ids: list[int]) -> None:
        """Mark page IDs as seen in the current export run.

        This avoids unnecessary API existence checks during cleanup for pages
        that were encountered but skipped (e.g. unchanged pages).
        """
        cls._seen_page_ids.update(str(pid) for pid in page_ids)

    @classmethod
    def should_export(cls, page: Page | Descendant) -> bool:
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
    def unseen_ids(cls) -> set[str]:
        """Return lockfile page IDs not encountered during the current export run."""
        if cls._lock is None:
            return set()
        return set(cls._lock.pages.keys()) - cls._seen_page_ids

    @classmethod
    def remove_pages(cls, deleted_ids: set[str]) -> None:
        """Remove files and lockfile entries for moved or deleted pages.

        Args:
            deleted_ids: Page IDs confirmed as deleted from Confluence.
        """
        if cls._lock is None or cls._lockfile_path is None or cls._output_path is None:
            return

        result_delete_ids: set[str] = set()

        # Handle moved pages: delete old file when export_path changed
        for page_id in cls._seen_page_ids:
            if page_id in cls._all_entries_snapshot and page_id in cls._lock.pages:
                old_entry = cls._all_entries_snapshot[page_id]
                new_entry = cls._lock.pages[page_id]
                if old_entry.export_path != new_entry.export_path:
                    (cls._output_path / old_entry.export_path).unlink(missing_ok=True)
                    logger.info(f"Deleted old path for moved page: {old_entry.export_path}")

        # Remove files and lockfile entries for pages deleted from Confluence
        for page_id in deleted_ids:
            if page_id in cls._lock.pages:
                entry = cls._lock.pages[page_id]
                (cls._output_path / entry.export_path).unlink(missing_ok=True)
                logger.info(f"Deleted removed page: {entry.export_path}")
                result_delete_ids.add(page_id)

        if result_delete_ids:
            cls._lock.save(cls._lockfile_path, delete_ids=result_delete_ids)
