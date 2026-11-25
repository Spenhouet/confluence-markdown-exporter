"""Cross-space page title registry for link disambiguation.

Confluence enforces page-title uniqueness per space, not across spaces.
When pages from multiple spaces are exported into the same vault, two
pages can share a title — Obsidian's wiki link ``[[Title]]`` then
resolves ambiguously. This registry tracks known page titles so the
Markdown converter can emit a path-qualified wiki link
(``[[path/to/file|Title]]``) when a collision is detected.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING
from typing import ClassVar

if TYPE_CHECKING:
    from pathlib import Path


class PageTitleRegistry:
    """Track page-id -> title and export path mappings.

    Used to detect cross-page title collisions and determine export scope
    for link rendering. Populated from the lockfile snapshot at run start
    and from each page list before export workers begin.
    """

    _entries: ClassVar[dict[int, str]] = {}
    _export_paths: ClassVar[dict[int, Path]] = {}
    _title_counts: ClassVar[dict[str, int]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._entries.clear()
            cls._export_paths.clear()
            cls._title_counts.clear()
        try:
            from confluence_markdown_exporter.utils.database_cache import DatabaseDataCache
            from confluence_markdown_exporter.utils.database_cache import PageMetadataCache

            DatabaseDataCache.reset()
            PageMetadataCache.reset()
        except ImportError:
            pass

    @classmethod
    def register(cls, page_id: int, title: str, export_path: Path | None = None) -> None:
        if not page_id or not title:
            return
        with cls._lock:
            old = cls._entries.get(page_id)
            if old != title:
                if old is not None:
                    cls._title_counts[old] -= 1
                    if cls._title_counts[old] <= 0:
                        cls._title_counts.pop(old, None)
                cls._entries[page_id] = title
                cls._title_counts[title] = cls._title_counts.get(title, 0) + 1
            if export_path is not None:
                cls._export_paths[page_id] = export_path

    @classmethod
    def get(cls, page_id: int) -> str | None:
        with cls._lock:
            return cls._entries.get(page_id)

    @classmethod
    def get_export_path(cls, page_id: int) -> Path | None:
        with cls._lock:
            return cls._export_paths.get(page_id)

    @classmethod
    def is_in_export_scope(cls, page_id: int) -> bool:
        with cls._lock:
            return page_id in cls._export_paths

    @classmethod
    def is_ambiguous(cls, title: str) -> bool:
        return cls._title_counts.get(title, 0) > 1

    @classmethod
    def title_count(cls, title: str) -> int:
        return cls._title_counts.get(title, 0)
