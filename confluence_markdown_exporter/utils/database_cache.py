"""In-memory cache for Confluence database objects and page metadata during export."""

from __future__ import annotations

import logging
import threading
import urllib.parse
from typing import Any
from typing import ClassVar
from typing import cast

from bs4 import BeautifulSoup

from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry

logger = logging.getLogger(__name__)


def clean_v2_path(path: str, client_url: str) -> str:
    """Strip redundant prefix from a v2 REST API path when joining with client_url."""
    parsed_client = urllib.parse.urlparse(client_url)
    base_prefix = parsed_client.path.rstrip("/")
    if base_prefix and path.startswith(base_prefix + "/"):
        path = path[len(base_prefix) + 1 :]
    elif path.startswith("/wiki/"):
        path = path[len("/wiki/") :]
    return path.lstrip("/")


def fetch_v2_paginated(client: Any, initial_path: str) -> list[dict[str, Any]]:  # noqa: ANN401
    """Fetch all pages of results from a cursor-paginated Confluence v2 endpoint."""
    results: list[dict[str, Any]] = []
    path: str | None = initial_path
    while path:
        cleaned = clean_v2_path(path, client.url)
        resp = cast("dict[str, Any]", client.get(cleaned))
        if not resp or not isinstance(resp, dict):
            break
        results.extend(resp.get("results", []))
        path = resp.get("_links", {}).get("next")
    return results


class DatabaseDataCache:
    """Thread-safe cache of database fields, entries, and titles."""

    _cache: ClassVar[dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]], str]]] = {}
    _entry_to_db: ClassVar[dict[str, str]] = {}
    _field_to_db: ClassVar[dict[str, str]] = {}
    _known_db_ids: ClassVar[set[str]] = set()
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def reset(cls) -> None:
        """Clear all cached database schemas, entries, and reverse-lookup indexes."""
        with cls._lock:
            cls._cache.clear()
            cls._entry_to_db.clear()
            cls._field_to_db.clear()
            cls._known_db_ids.clear()

    @classmethod
    def register_database_id(cls, database_id: str | int) -> None:
        """Register a discovered database ID so lazy lookups can inspect it later."""
        if not database_id:
            return
        with cls._lock:
            cls._known_db_ids.add(str(database_id))

    @classmethod
    def _store_locked(
        cls,
        db_id: str,
        fields: list[dict[str, Any]],
        entries: list[dict[str, Any]],
        title: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        result = (fields, entries, title)
        cls._cache[db_id] = result
        cls._known_db_ids.add(db_id)
        for field in fields:
            fid = str(field.get("id", ""))
            if fid:
                cls._field_to_db[fid] = db_id
        for entry in entries:
            eid = str(entry.get("id", ""))
            if eid:
                cls._entry_to_db[eid] = db_id
        return result

    @classmethod
    def set(
        cls,
        database_id: str,
        fields: list[dict[str, Any]],
        entries: list[dict[str, Any]],
        title: str,
    ) -> None:
        """Store database fields, entries, and title in the cache."""
        with cls._lock:
            cls._store_locked(str(database_id), fields, entries, title)

    @classmethod
    def get(cls, database_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str] | None:
        """Return cached ``(fields, entries, title)`` for *database_id*, if present."""
        with cls._lock:
            return cls._cache.get(str(database_id))

    @classmethod
    def get_database_id_for_entry(cls, entry_id: str) -> str | None:
        """Return the cached database ID owning *entry_id*, if known."""
        with cls._lock:
            return cls._entry_to_db.get(str(entry_id))

    @classmethod
    def get_database_id_for_field(cls, field_id: str) -> str | None:
        """Return the cached database ID owning *field_id*, if known."""
        with cls._lock:
            return cls._field_to_db.get(str(field_id))

    @classmethod
    def _fetch_database_title(cls, client: Any, db_id: str) -> str:  # noqa: ANN401
        title = ""
        try:
            if db_id.isdigit():
                title = PageTitleRegistry.get(int(db_id)) or ""
            if not title:
                resp = client.get(f"api/v2/databases/{db_id}")
                if isinstance(resp, dict):
                    title = resp.get("title", "")
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch database %s title: %s", db_id, e)
        return title or f"Database {db_id}"

    @classmethod
    def get_or_fetch(
        cls, database_id: str, base_url: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str] | None:
        """Return cached database data or fetch title, fields, and entries from Confluence."""
        db_id = str(database_id)
        with cls._lock:
            if db_id in cls._cache:
                return cls._cache[db_id]

        from confluence_markdown_exporter.confluence import get_thread_confluence

        client = get_thread_confluence(base_url)
        title = cls._fetch_database_title(client, db_id)

        fields: list[dict[str, Any]] = []
        try:
            fields = fetch_v2_paginated(client, f"api/v2/databases/{db_id}/fields")
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch fields for database %s: %s", db_id, e)

        entries: list[dict[str, Any]] = []
        try:
            entries = fetch_v2_paginated(client, f"api/v2/databases/{db_id}/entries")
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch entries for database %s: %s", db_id, e)

        with cls._lock:
            return cls._store_locked(db_id, fields, entries, title)

    @classmethod
    def _find_database_by_index(
        cls,
        item_id: str,
        index: dict[str, str],
        base_url: str,
        space_key: str | None,
        kind: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str] | None:
        key = str(item_id)
        with cls._lock:
            target_db_id = index.get(key)
            if target_db_id and target_db_id in cls._cache:
                return cls._cache[target_db_id]
            unfetched_known = [did for did in cls._known_db_ids if did not in cls._cache]

        for did in unfetched_known:
            cls.get_or_fetch(did, base_url)
            with cls._lock:
                target_db_id = index.get(key)
                if target_db_id and target_db_id in cls._cache:
                    return cls._cache[target_db_id]

        if not space_key:
            return None

        from confluence_markdown_exporter.confluence import get_thread_confluence

        try:
            client = get_thread_confluence(base_url)
            resp = client.get(f'rest/api/content/search?cql=type=database AND space="{space_key}"')
            if isinstance(resp, dict):
                for db_item in resp.get("results", []):
                    did = str(db_item.get("id", ""))
                    if not did:
                        continue
                    cls.register_database_id(did)
                    cls.get_or_fetch(did, base_url)
                    with cls._lock:
                        target_db_id = index.get(key)
                        if target_db_id and target_db_id in cls._cache:
                            return cls._cache[target_db_id]
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed discovering space databases for %s %s: %s", kind, key, e)

        return None

    @classmethod
    def find_database_for_entry(
        cls, entry_id: str, base_url: str, space_key: str | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str] | None:
        """Locate the database containing *entry_id* using cache, known IDs, or space search."""
        return cls._find_database_by_index(entry_id, cls._entry_to_db, base_url, space_key, "entry")

    @classmethod
    def find_database_for_field(
        cls, field_id: str, base_url: str, space_key: str | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str] | None:
        """Locate the database containing *field_id* using cache, known IDs, or space search."""
        return cls._find_database_by_index(field_id, cls._field_to_db, base_url, space_key, "field")


class PageMetadataCache:
    """Thread-safe cache of Confluence page metadata for lookup and link resolution."""

    _cache: ClassVar[dict[str, dict[str, Any]]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def reset(cls) -> None:
        """Clear all cached page metadata."""
        with cls._lock:
            cls._cache.clear()

    @classmethod
    def set(cls, page_id: str, meta: dict[str, Any]) -> None:
        """Store metadata dictionary for *page_id*."""
        with cls._lock:
            cls._cache[str(page_id)] = meta

    @classmethod
    def get(cls, page_id: str) -> dict[str, Any] | None:
        """Return cached metadata for *page_id*, if present."""
        with cls._lock:
            return cls._cache.get(str(page_id))

    @staticmethod
    def _extract_excerpt(body_html: str) -> str:
        if not body_html or "excerpt" not in body_html:
            return ""
        soup = BeautifulSoup(body_html, "html.parser")
        macro = soup.find("ac:structured-macro", {"ac:name": "excerpt"}) or soup.find(
            attrs={"data-macro-name": "excerpt"}
        )
        if not macro:
            return ""
        for ext in macro.find_all(["ac:adf-extension", "ac:parameter", "ac:adf-node"]):
            ext.decompose()
        rich_body = macro.find("ac:rich-text-body")
        target = rich_body or macro
        return target.get_text().strip()

    @classmethod
    def _populate_from_page(cls, meta: dict[str, Any], int_id: int, base_url: str) -> None:
        from confluence_markdown_exporter.confluence import Page

        try:
            page = Page.from_id(int_id, base_url)
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch full page %s via Page.from_id: %s", int_id, e)
            return

        if not page or page.title == "Page not accessible":
            return

        meta["title"] = page.title
        meta["web_url"] = page.web_url
        if getattr(page, "space", None):
            meta["space_key"] = page.space.key
        meta["labels"] = [lbl.name for lbl in getattr(page, "labels", [])]
        if getattr(page, "version", None):
            meta["version"] = str(page.version.number)
            meta["version_comment"] = getattr(page.version, "message", "") or ""
            meta["last_modified"] = page.version.when or ""
            if getattr(page.version, "by", None) and page.version.by.display_name:
                meta["last_modified_by"] = page.version.by.display_name
        if getattr(page, "history", None):
            meta["created"] = page.history.created or ""
            if page.history.created_by and page.history.created_by.display_name:
                meta["created_by"] = page.history.created_by.display_name
            if not meta["last_modified"]:
                meta["last_modified"] = meta["created"]
            if not meta["last_modified_by"]:
                meta["last_modified_by"] = meta["created_by"]
        body_html = getattr(page, "body_storage", None) or getattr(page, "body", "")
        meta["excerpt"] = cls._extract_excerpt(body_html)

    @classmethod
    def _populate_from_v2_api(cls, meta: dict[str, Any], pid: str, base_url: str) -> None:
        from confluence_markdown_exporter.confluence import get_thread_confluence

        try:
            client = get_thread_confluence(base_url)
            resp = client.get(f"api/v2/pages/{pid}")
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch page %s via v2 API: %s", pid, e)
            return

        if not isinstance(resp, dict):
            return
        if not meta["title"]:
            meta["title"] = resp.get("title", "")
        if not meta["status"]:
            meta["status"] = resp.get("status", "")
        if not meta["web_url"]:
            webui = resp.get("_links", {}).get("webui", "")
            if webui:
                meta["web_url"] = f"{base_url.rstrip('/')}{webui}"

    @classmethod
    def get_or_fetch(cls, page_id: str, base_url: str) -> dict[str, Any]:
        """Return cached page metadata or fetch it from Confluence REST v1/v2 APIs."""
        pid = str(page_id)
        with cls._lock:
            if pid in cls._cache:
                return cls._cache[pid]

        meta: dict[str, Any] = {
            "title": "",
            "web_url": "",
            "space_key": "",
            "status": "",
            "labels": [],
            "created": "",
            "created_by": "",
            "last_modified": "",
            "last_modified_by": "",
            "version": "",
            "version_comment": "",
            "excerpt": "",
        }

        int_id = int(pid) if pid.isdigit() else None
        if int_id is not None:
            title = PageTitleRegistry.get(int_id)
            if title:
                meta["title"] = title
            cls._populate_from_page(meta, int_id, base_url)

        if not meta["title"] or not meta["status"]:
            cls._populate_from_v2_api(meta, pid, base_url)

        with cls._lock:
            cls._cache[pid] = meta
        return meta
