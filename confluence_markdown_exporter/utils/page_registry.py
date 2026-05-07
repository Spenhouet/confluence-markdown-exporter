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
from typing import ClassVar


class PageTitleRegistry:
    """Track page-id -> title mappings to detect cross-page title collisions.

    Populated from the lockfile snapshot at run start and from each
    page list before export workers begin so collisions are known
    before any link rendering.
    """

    _entries: ClassVar[dict[int, str]] = {}
    _title_counts: ClassVar[dict[str, int]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._entries.clear()
            cls._title_counts.clear()

    @classmethod
    def register(cls, page_id: int, title: str) -> None:
        if not page_id or not title:
            return
        with cls._lock:
            old = cls._entries.get(page_id)
            if old == title:
                return
            if old is not None:
                cls._title_counts[old] -= 1
                if cls._title_counts[old] <= 0:
                    cls._title_counts.pop(old, None)
            cls._entries[page_id] = title
            cls._title_counts[title] = cls._title_counts.get(title, 0) + 1

    @classmethod
    def is_ambiguous(cls, title: str) -> bool:
        return cls._title_counts.get(title, 0) > 1

    @classmethod
    def title_count(cls, title: str) -> int:
        return cls._title_counts.get(title, 0)
