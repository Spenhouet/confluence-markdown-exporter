"""Confluence API documentation.

https://developer.atlassian.com/cloud/confluence/rest/v1/intro
"""

import functools
import json
import logging
import mimetypes
import os
import re
import urllib.parse
from collections.abc import Set
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from os import PathLike
from pathlib import Path
from string import Template
from typing import Literal
from typing import TypeAlias
from typing import cast
from urllib.parse import unquote
from urllib.parse import urlparse

import yaml
from atlassian.errors import ApiError
from atlassian.errors import ApiNotFoundError
from bs4 import BeautifulSoup
from bs4 import Tag
from markdownify import ATX
from markdownify import MarkdownConverter
from pydantic import BaseModel
from requests import HTTPError
from requests import RequestException
from rich.progress import BarColumn
from rich.progress import MofNCompleteColumn
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TaskProgressColumn
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from rich.progress import TimeRemainingColumn

from confluence_markdown_exporter.api_clients import JiraAuthenticationError
from confluence_markdown_exporter.api_clients import build_gateway_url
from confluence_markdown_exporter.api_clients import get_confluence_instance
from confluence_markdown_exporter.api_clients import get_jira_instance
from confluence_markdown_exporter.api_clients import get_thread_confluence
from confluence_markdown_exporter.api_clients import handle_jira_auth_failure
from confluence_markdown_exporter.api_clients import parse_confluence_path
from confluence_markdown_exporter.api_clients import parse_gateway_url
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import normalize_instance_url
from confluence_markdown_exporter.utils.drawio_converter import load_and_parse_drawio
from confluence_markdown_exporter.utils.export import sanitize_filename
from confluence_markdown_exporter.utils.export import sanitize_key
from confluence_markdown_exporter.utils.export import save_file
from confluence_markdown_exporter.utils.lockfile import AttachmentEntry
from confluence_markdown_exporter.utils.lockfile import LockfileManager
from confluence_markdown_exporter.utils.rich_console import ExportStats
from confluence_markdown_exporter.utils.rich_console import console
from confluence_markdown_exporter.utils.rich_console import get_stats
from confluence_markdown_exporter.utils.rich_console import reset_stats
from confluence_markdown_exporter.utils.table_converter import TableConverter

JsonResponse: TypeAlias = dict
StrPath: TypeAlias = str | PathLike[str]

logger = logging.getLogger(__name__)


def _extract_base_url(url: str) -> str:
    """Extract the base URL from a Confluence or Jira URL.

    For Atlassian Cloud URLs (``*.atlassian.net``) returns ``{scheme}://{hostname}``.
    For Atlassian API gateway URLs of the form
    ``https://api.atlassian.com/ex/{service}/{cloudId}/...``
    returns ``https://api.atlassian.com/ex/{service}/{cloudId}`` so that
    the Cloud ID is preserved as part of the base URL used for auth lookup
    and SDK initialisation.
    For Server/Data Center instances with a context path (e.g.
    ``https://host/confluence/spaces/KEY``), the context path is preserved
    so the SDK client hits the correct REST endpoints.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme is None or parsed.hostname is None:
        msg = (
            "Invalid URL: a scheme (http:// or https://) and hostname are required. "
            "Expected format: 'https://<hostname>[:port]/...'."
        )
        raise ValueError(msg)

    if gateway := parse_gateway_url(url):
        return normalize_instance_url(build_gateway_url(*gateway))

    # For Server/DC instances the Confluence webapp may be deployed under a
    # context path (e.g. ``/confluence``).  Preserve everything before the
    # first path segment that belongs to Confluence's own routing.
    _confluence_route_segments = {
        "wiki",
        "display",
        "spaces",
        "rest",
        "pages",
        "plugins",
        "dosearchsite.action",
    }
    segments = [s for s in parsed.path.split("/") if s]
    context_parts: list[str] = []
    for segment in segments:
        if segment.lower() in _confluence_route_segments:
            break
        context_parts.append(segment)

    base = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port and parsed.port not in (80, 443):
        base = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    if context_parts:
        base = f"{base}/{'/'.join(context_parts)}"
    return normalize_instance_url(base)


_JIRA_ROUTE_SEGMENTS = {
    "agile",
    "backlog",
    "board",
    "browse",
    "issues",
    "plugins",
    "projects",
    "rest",
    "secure",
    "servicedesk",
    "software",
}


def _extract_jira_base_url(url: str) -> str | None:
    """Extract the Jira instance base URL from a Jira issue URL.

    Strips Jira-specific routing segments (e.g. ``browse``) so that the context
    path is preserved for Server/DC deployments (e.g. ``https://host/jira``),
    matching the key format used in ``auth.jira`` configuration.
    Returns ``None`` when *url* is not an absolute URL.
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return None

    if gateway := parse_gateway_url(url):
        return normalize_instance_url(build_gateway_url(*gateway))

    segments = [s for s in parsed.path.split("/") if s]
    context_parts: list[str] = []
    for segment in segments:
        if segment.lower() in _JIRA_ROUTE_SEGMENTS:
            break
        context_parts.append(segment)

    base = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port and parsed.port not in (80, 443):
        base = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    if context_parts:
        base = f"{base}/{'/'.join(context_parts)}"
    return normalize_instance_url(base)


settings = get_settings()


class JiraIssue(BaseModel):
    key: str
    summary: str
    description: str | None
    status: str

    @classmethod
    def from_json(cls, data: JsonResponse) -> "JiraIssue":
        fields = data.get("fields", {})
        return cls(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            description=fields.get("description", ""),
            status=fields.get("status", {}).get("name", ""),
        )

    @classmethod
    def from_key(cls, issue_key: str, jira_url: str) -> "JiraIssue | None":
        """Fetch a Jira issue by key."""
        settings = get_settings()
        if not settings.export.enable_jira_enrichment:
            return None

        try:
            return cls._fetch_cached(issue_key, jira_url)
        except JiraAuthenticationError:
            handle_jira_auth_failure(jira_url)
            return None

    @classmethod
    @functools.lru_cache(maxsize=100)
    def _fetch_cached(cls, issue_key: str, jira_url: str) -> "JiraIssue":
        jira_instance = get_jira_instance(jira_url)
        issue_data = cast("JsonResponse", jira_instance.get_issue(issue_key))
        return cls.from_json(issue_data)


class User(BaseModel):
    account_id: str
    username: str
    display_name: str
    public_name: str
    email: str

    @classmethod
    def from_json(cls, data: JsonResponse) -> "User":
        return cls(
            account_id=data.get("accountId", ""),
            username=data.get("username", ""),
            display_name=data.get("displayName", ""),
            public_name=data.get("publicName", ""),
            email=data.get("email", ""),
        )

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_username(cls, username: str, base_url: str = "") -> "User":
        return cls.from_json(
            cast(
                "JsonResponse",
                get_thread_confluence(base_url).get_user_details_by_username(username),
            )
        )

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_userkey(cls, userkey: str, base_url: str = "") -> "User":
        return cls.from_json(
            cast(
                "JsonResponse",
                get_thread_confluence(base_url).get_user_details_by_userkey(userkey),
            )
        )

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_accountid(cls, accountid: str, base_url: str = "") -> "User":
        return cls.from_json(
            cast(
                "JsonResponse",
                get_thread_confluence(base_url).get_user_details_by_accountid(accountid),
            )
        )


class Version(BaseModel):
    number: int
    by: User
    when: str
    friendly_when: str

    @classmethod
    def from_json(cls, data: JsonResponse) -> "Version":
        return cls(
            number=data.get("number", 0),
            by=User.from_json(data.get("by", {})),
            when=data.get("when", ""),
            friendly_when=data.get("friendlyWhen", ""),
        )


class Organization(BaseModel):
    base_url: str
    spaces: list["Space"]

    @property
    def pages(self) -> list["Page | Descendant"]:
        return [page for space in self.spaces for page in space.pages]

    def export(self) -> None:
        """Export all pages across all spaces, showing per-space discovery progress."""
        all_pages: list[Page | Descendant] = []
        n = len(self.spaces)
        logger.info("Exporting %d space(s) from %s", n, self.base_url)
        with console.status("", spinner="dots") as status:
            for i, space in enumerate(self.spaces, 1):
                status.update(
                    f"[dim]Fetching pages for space [highlight]{space.name}[/highlight]"
                    f" ({i}/{n})…[/dim]"
                )
                all_pages.extend(space.pages)
        logger.info("Discovered %d page(s) across %d space(s)", len(all_pages), n)
        export_pages(all_pages)

    @classmethod
    def from_json(cls, data: JsonResponse, base_url: str) -> "Organization":
        return cls(
            base_url=base_url,
            spaces=[Space.from_json(space, base_url) for space in data.get("results", [])],
        )

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_url(cls, base_url: str) -> "Organization":
        logger.debug("Fetching space list from %s", base_url)
        with console.status(
            f"[dim]Fetching space list from [highlight]{base_url}[/highlight]…[/dim]"
        ):
            org = cls.from_json(
                cast(
                    "JsonResponse",
                    get_thread_confluence(base_url).get_all_spaces(
                        space_type="global", space_status="current", expand="homepage"
                    ),
                ),
                base_url,
            )
        logger.info("Found %d space(s) in %s", len(org.spaces), base_url)
        return org


class Space(BaseModel):
    base_url: str
    key: str
    name: str
    description: str
    homepage: int | None

    @property
    def pages(self) -> list["Page | Descendant"]:
        if self.homepage is None:
            logger.warning(
                f"Space '{self.name}' (key: {self.key}) has no homepage. No pages will be exported."
            )
            return []

        homepage = Page.from_id(self.homepage, self.base_url)
        return [homepage, *homepage.descendants]

    def export(self) -> None:
        """Export all pages in this space to Markdown."""
        logger.debug("Fetching pages for space '%s' (%s)", self.name, self.key)
        with console.status(
            f"[dim]Fetching pages for space [highlight]{self.name}[/highlight]…[/dim]"
        ):
            pages = self.pages
        logger.info("Found %d page(s) in space '%s'", len(pages), self.name)
        export_pages(pages)

    @classmethod
    def from_json(cls, data: JsonResponse, base_url: str) -> "Space":
        return cls(
            base_url=base_url,
            key=data.get("key", ""),
            name=data.get("name", ""),
            description=data.get("description", {}).get("plain", {}).get("value", ""),
            homepage=data.get("homepage", {}).get("id"),
        )

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_key(cls, space_key: str, base_url: str) -> "Space":
        return cls.from_json(
            cast(
                "JsonResponse",
                get_thread_confluence(base_url).get_space(space_key, expand="homepage"),
            ),
            base_url,
        )

    @classmethod
    def from_url(cls, space_url: str) -> "Space":
        """Retrieve a Space object given a Confluence space URL.

        The Confluence instance is selected automatically by matching the URL's
        hostname against configured instances.  If no match is found, a new
        entry is registered in the auth config so the user can fill in
        credentials via the interactive config menu.

        Supports standard instance URLs (``https://company.atlassian.net/wiki/spaces/KEY``)
        and Atlassian API gateway URLs
        (``https://api.atlassian.com/ex/confluence/{cloudId}/wiki/spaces/KEY``).
        """
        base_url = _extract_base_url(space_url)

        # Ensure a client exists (creates/prompts if first time for this host)
        get_confluence_instance(base_url)

        parsed = urllib.parse.urlparse(space_url)
        base_path = urllib.parse.urlparse(base_url).path.rstrip("/")
        relative_path = parsed.path[len(base_path) :]
        if match := parse_confluence_path(relative_path):
            if match.space_key:
                logger.debug("Resolved space key '%s' from URL %s", match.space_key, space_url)
                return cls.from_key(match.space_key, base_url)

        msg = f"Could not parse space URL {space_url}."
        raise ValueError(msg)


class Label(BaseModel):
    id: str
    name: str
    prefix: str

    @classmethod
    def from_json(cls, data: JsonResponse) -> "Label":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            prefix=data.get("prefix", ""),
        )


class Document(BaseModel):
    base_url: str
    title: str
    space: Space
    ancestors: list["Ancestor"]
    version: Version

    @property
    def _template_vars(self) -> dict[str, str]:
        homepage_id = ""
        homepage_title = ""
        if self.space.homepage:
            homepage_id = str(self.space.homepage)
            homepage_title = sanitize_filename(
                Page.from_id(self.space.homepage, self.base_url).title
            )

        return {
            "space_key": sanitize_filename(self.space.key),
            "space_name": sanitize_filename(self.space.name),
            "homepage_id": homepage_id,
            "homepage_title": homepage_title,
            "ancestor_ids": "/".join(str(a.id) for a in self.ancestors),
            "ancestor_titles": "/".join(sanitize_filename(a.title) for a in self.ancestors),
        }


class Attachment(Document):
    id: str
    file_size: int
    media_type: str
    media_type_description: str
    file_id: str
    collection_name: str
    download_link: str
    comment: str

    @property
    def extension(self) -> str:
        if self.comment == "draw.io diagram" and self.media_type == "application/vnd.jgraph.mxfile":
            return ".drawio"
        if self.comment == "draw.io preview" and self.media_type == "image/png":
            return ".drawio.png"

        return mimetypes.guess_extension(self.media_type) or ""

    @property
    def filename(self) -> str:
        return f"{self.file_id}{self.extension}"

    @property
    def _template_vars(self) -> dict[str, str]:
        return {
            **super()._template_vars,
            "attachment_id": str(self.id),
            "attachment_title": sanitize_filename(self.title),
            # file_id is a GUID and does not need sanitized.
            "attachment_file_id": self.file_id,
            "attachment_extension": self.extension,
        }

    @property
    def export_path(self) -> Path:
        filepath_template = Template(settings.export.attachment_path.replace("{", "${"))
        return Path(filepath_template.safe_substitute(self._template_vars))

    @classmethod
    def from_json(cls, data: JsonResponse, base_url: str) -> "Attachment":
        extensions = data.get("extensions", {})
        container = data.get("container", {})
        return cls(
            base_url=base_url,
            id=data.get("id", ""),
            title=data.get("title", ""),
            space=Space.from_key(
                data.get("_expandable", {}).get("space", "").split("/")[-1], base_url
            ),
            file_size=extensions.get("fileSize", 0),
            media_type=extensions.get("mediaType", ""),
            media_type_description=extensions.get("mediaTypeDescription", ""),
            file_id=extensions.get("fileId", ""),
            collection_name=extensions.get("collectionName", ""),
            download_link=data.get("_links", {}).get("download", ""),
            comment=extensions.get("comment", ""),
            ancestors=[
                *[
                    Ancestor.from_json(ancestor, base_url)
                    for ancestor in container.get("ancestors", [])
                ],
                Ancestor.from_json(container, base_url),
            ][1:],
            version=Version.from_json(data.get("version", {})),
        )

    @classmethod
    def from_page_id(cls, page_id: int, base_url: str) -> list["Attachment"]:
        attachments = []
        start = 0
        paging_limit = 50
        size = paging_limit  # Initialize to limit to enter the loop

        while size >= paging_limit:
            response = cast(
                "JsonResponse",
                get_thread_confluence(base_url).get_attachments_from_content(
                    page_id,
                    start=start,
                    limit=paging_limit,
                    expand="container.ancestors,version",
                ),
            )

            attachments.extend(
                [cls.from_json(att, base_url) for att in response.get("results", [])]
            )

            size = response.get("size", 0)
            start += size

        logger.debug("Found %d attachment(s) for page id=%s", len(attachments), page_id)
        return attachments

    def export(self) -> None:
        stats = get_stats()
        filepath = settings.export.output_path / self.export_path
        if filepath.exists():
            logger.debug("Skipping attachment '%s' — already exists at %s", self.title, filepath)
            return

        logger.debug("Downloading attachment '%s' to %s", self.title, filepath)
        client = get_thread_confluence(self.base_url)
        try:
            response = client.request(
                method="GET",
                path=client.url + self.download_link,
                absolute=True,
                advanced_mode=True,
            )
            response.raise_for_status()  # Raise error if request fails
        except HTTPError:
            logger.warning("There is no attachment with title '%s'. Skipping export.", self.title)
            stats.inc_attachments_failed()
            return
        except RequestException as e:
            logger.warning("Failed to download attachment '%s': %s. Skipping.", self.title, e)
            stats.inc_attachments_failed()
            return

        save_file(filepath, response.content)
        logger.debug("Saved attachment '%s' (%d bytes)", self.title, len(response.content))
        stats.inc_attachments_exported()


class Ancestor(Document):
    id: int

    @classmethod
    def from_json(cls, data: JsonResponse, base_url: str) -> "Ancestor":
        return cls(
            base_url=base_url,
            id=data.get("id", 0),
            title=data.get("title", ""),
            space=Space.from_key(
                data.get("_expandable", {}).get("space", "").split("/")[-1], base_url
            ),
            ancestors=[],  # Ancestors of ancestor is not needed for now.
            version=Version.from_json({}),  # Version of ancestor is not needed for now.
        )


class Descendant(Document):
    id: int

    @property
    def _template_vars(self) -> dict[str, str]:
        return {
            **super()._template_vars,
            "page_id": str(self.id),
            "page_title": sanitize_filename(self.title),
        }

    @property
    def export_path(self) -> Path:
        filepath_template = Template(settings.export.page_path.replace("{", "${"))
        return Path(filepath_template.safe_substitute(self._template_vars))

    @classmethod
    def from_json(cls, data: JsonResponse, base_url: str) -> "Descendant":
        return cls(
            base_url=base_url,
            id=data.get("id", 0),
            title=data.get("title", ""),
            space=Space.from_key(
                data.get("_expandable", {}).get("space", "").split("/")[-1], base_url
            ),
            ancestors=[
                Ancestor.from_json(ancestor, base_url) for ancestor in data.get("ancestors", [])
            ][1:],
            version=Version.from_json(data.get("version", {})),
        )


class Page(Document):
    id: int
    body: str
    body_export: str
    editor2: str
    labels: list["Label"]
    attachments: list["Attachment"]

    @property
    def descendants(self) -> list["Descendant"]:
        url = "rest/api/content/search"
        params = {
            "cql": f"type=page AND ancestor={self.id}",
            "expand": "metadata.properties,ancestors,version",
            "limit": 250,
        }
        results = []
        client = get_thread_confluence(self.base_url)

        try:
            response = cast("dict", client.get(url, params=params))
            results.extend(response.get("results", []))
            next_path = response.get("_links", {}).get("next")

            while next_path:
                response = cast("dict", client.get(next_path))
                results.extend(response.get("results", []))
                next_path = response.get("_links", {}).get("next")

        except HTTPError as e:
            if e.response.status_code == 404:  # noqa: PLR2004
                logger.warning(
                    f"Content with ID {self.id} not found (404) when fetching descendants."
                )
                return []
            return []
        except Exception:
            logger.exception(
                f"Unexpected error when fetching descendants for content ID {self.id}."
            )
            return []
        return [Descendant.from_json(result, self.base_url) for result in results]

    @property
    def _template_vars(self) -> dict[str, str]:
        return {
            **super()._template_vars,
            "page_id": str(self.id),
            "page_title": sanitize_filename(self.title),
        }

    @property
    def export_path(self) -> Path:
        filepath_template = Template(settings.export.page_path.replace("{", "${"))
        return Path(filepath_template.safe_substitute(self._template_vars))

    @property
    def html(self) -> str:
        if settings.export.include_document_title:
            return f"<h1>{self.title}</h1>{self.body}"
        return self.body

    @property
    def markdown(self) -> str:
        return self.Converter(self).markdown

    def export(self) -> dict[str, AttachmentEntry]:
        if self.title == "Page not accessible":
            logger.warning("Skipping export for inaccessible page id=%s", self.id)
            return {}

        logger.debug("Exporting page id=%s '%s'", self.id, self.title)
        if settings.export.log_level == "DEBUG":
            self.export_body()
        # Export attachments first so the files can be utilized during markdown conversion
        logger.debug("Exporting attachments for page id=%s", self.id)
        attachment_entries = self.export_attachments()
        logger.debug("Converting to Markdown for page id=%s", self.id)
        self.export_markdown()
        logger.info(
            "Exported '%s' -> %s", self.title, settings.export.output_path / self.export_path
        )
        return attachment_entries

    def export_with_descendants(self) -> None:
        with console.status(
            f"[dim]Fetching descendants of [highlight]{self.title}[/highlight]…[/dim]"
        ):
            pages = [self, *self.descendants]
        export_pages(pages)

    def export_body(self) -> None:
        soup = BeautifulSoup(self.html, "html.parser")
        save_file(
            settings.export.output_path
            / self.export_path.parent
            / f"{self.export_path.stem}_body_view.html",
            str(soup.prettify()),
        )
        soup = BeautifulSoup(self.body_export, "html.parser")
        save_file(
            settings.export.output_path
            / self.export_path.parent
            / f"{self.export_path.stem}_body_export_view.html",
            str(soup.prettify()),
        )
        save_file(
            settings.export.output_path
            / self.export_path.parent
            / f"{self.export_path.stem}_body_editor2.xml",
            str(self.editor2),
        )

    def export_markdown(self) -> None:
        save_file(
            settings.export.output_path / self.export_path,
            self.markdown,
        )

    def _attachments_for_export(self) -> list["Attachment"]:
        """Return the subset of attachments that should be exported for this page."""
        if settings.export.attachment_export_all:
            return list(self.attachments)
        return [
            a
            for a in self.attachments
            if (a.filename.endswith(".drawio") and f"diagramName={a.title}" in self.body)
            or (
                a.filename.endswith((".drawio.png", ".drawio"))
                and a.title.replace(" ", "%20") in self.body_export
            )
            or a.file_id in self.body
        ]

    def export_attachments(self) -> dict[str, AttachmentEntry]:
        old_entries = LockfileManager.get_page_attachment_entries(str(self.id))
        new_entries: dict[str, AttachmentEntry] = {}
        output_path = settings.export.output_path
        stats = get_stats()

        for attachment in self._attachments_for_export():
            att_id = attachment.id
            att_version = attachment.version.number if attachment.version else 0

            # Skip download if the same attachment version is tracked and the file still exists
            if att_id in old_entries:
                old = old_entries[att_id]
                if old.version == att_version and (output_path / old.path).exists():
                    new_entries[att_id] = old
                    logger.debug(
                        "Skipping unchanged attachment '%s' (v%d)", attachment.title, att_version
                    )
                    stats.inc_attachments_skipped()
                    continue

            attachment.export()
            if att_version:
                new_entries[att_id] = AttachmentEntry(
                    version=att_version, path=str(attachment.export_path)
                )

        # Clean up orphaned attachment files when an attachment was re-versioned
        for att_id, old_entry in old_entries.items():
            if att_id in new_entries and old_entry.path != new_entries[att_id].path:
                old_file = output_path / old_entry.path
                old_file.unlink(missing_ok=True)
                logger.info("Deleted old attachment file: %s", old_entry.path)
                stats.inc_attachments_removed()

        return new_entries

    def get_attachment_by_id(self, attachment_id: str) -> Attachment | None:
        """Get the Attachment object by its ID.

        Confluence Server sometimes stores attachments without a file_id.
        Fall back to the plain attachment.id and return None if nothing matches.
        """
        for a in self.attachments:
            if attachment_id in a.id:
                return a
            if a.file_id and attachment_id in a.file_id:
                return a
        return None

    def get_attachment_by_file_id(self, file_id: str) -> Attachment | None:
        for a in self.attachments:
            if a.file_id and file_id in a.file_id:
                return a
        return None

    def get_attachments_by_title(self, title: str) -> list[Attachment]:
        return [attachment for attachment in self.attachments if attachment.title == title]

    @classmethod
    def from_json(cls, data: JsonResponse, base_url: str) -> "Page":
        return cls(
            base_url=base_url,
            id=data.get("id", 0),
            title=data.get("title", ""),
            space=Space.from_key(
                data.get("_expandable", {}).get("space", "").split("/")[-1], base_url
            ),
            body=data.get("body", {}).get("view", {}).get("value", ""),
            body_export=data.get("body", {}).get("export_view", {}).get("value", ""),
            editor2=data.get("body", {}).get("editor2", {}).get("value", ""),
            labels=[
                Label.from_json(label)
                for label in data.get("metadata", {}).get("labels", {}).get("results", [])
            ],
            attachments=Attachment.from_page_id(data.get("id", 0), base_url),
            ancestors=[
                Ancestor.from_json(ancestor, base_url) for ancestor in data.get("ancestors", [])
            ][1:],
            version=Version.from_json(data.get("version", {})),
        )

    @classmethod
    @functools.lru_cache(maxsize=1000)
    def from_id(cls, page_id: int, base_url: str) -> "Page":
        _empty_space = Space(base_url=base_url, key="", name="", description="", homepage=0)
        if page_id is None:
            logger.warning("Page ID is None, returning empty page")
            return cls(
                base_url=base_url,
                id=0,
                title="Page not accessible",
                space=_empty_space,
                body="",
                body_export="",
                editor2="",
                labels=[],
                attachments=[],
                ancestors=[],
            )
        logger.debug("Fetching page id=%s from %s", page_id, base_url)
        try:
            return cls.from_json(
                cast(
                    "JsonResponse",
                    get_thread_confluence(base_url).get_page_by_id(
                        page_id,
                        expand="body.view,body.export_view,body.editor2,metadata.labels,"
                        "metadata.properties,ancestors,version",
                    ),
                ),
                base_url,
            )
        except (ApiError, HTTPError):
            logger.warning("Could not access page id=%s — treating as inaccessible", page_id)
            return cls(
                base_url=base_url,
                id=page_id,
                title="Page not accessible",
                space=_empty_space,
                body="",
                body_export="",
                editor2="",
                labels=[],
                attachments=[],
                ancestors=[],
                version=Version.from_json({}),
            )

    @classmethod
    def from_url(cls, page_url: str) -> "Page":
        """Retrieve a Page object given a Confluence page URL.

        The Confluence instance is selected automatically by matching the URL's
        hostname against configured instances.  If no match is found, a new
        entry is registered in the auth config so the user can fill in
        credentials via the interactive config menu.

        Supports standard instance URLs and Atlassian API gateway URLs of the form
        ``https://api.atlassian.com/ex/confluence/{cloudId}/wiki/spaces/KEY/pages/123``.
        """
        base_url = _extract_base_url(page_url)

        # Ensure a client exists (creates/prompts if first time for this host)
        get_confluence_instance(base_url)

        parsed = urllib.parse.urlparse(page_url)
        base_path = urllib.parse.urlparse(base_url).path.rstrip("/")
        relative_path = parsed.path[len(base_path) :]
        if match := parse_confluence_path(relative_path):
            if match.page_id:
                logger.debug("Resolved page id=%s from Confluence URL %s", match.page_id, page_url)
                return Page.from_id(match.page_id, base_url)

            if match.space_key and match.page_title:
                logger.debug(
                    "Resolving page '%s' in space '%s' from Confluence URL %s",
                    match.page_title,
                    match.space_key,
                    page_url,
                )
                page_data = cast(
                    "JsonResponse",
                    get_thread_confluence(base_url).get_page_by_title(
                        space=match.space_key, title=match.page_title, expand="version"
                    ),
                )
                return Page.from_id(page_data["id"], base_url)

        msg = f"Could not parse page URL {page_url}."
        raise ValueError(msg)

    class Converter(TableConverter, MarkdownConverter):
        """Create a custom MarkdownConverter for Confluence HTML to Markdown conversion."""

        class Options(MarkdownConverter.DefaultOptions):  # type: ignore[assignment]
            bullets = "-"
            heading_style = ATX
            macros_to_ignore: Set[str] = frozenset(["qc-read-and-understood-signature-box"])
            front_matter_indent = 2

        def __init__(self, page: "Page", **options) -> None:  # noqa: ANN003
            super().__init__(**options)
            self.page = page
            self.page_properties = {}

        @property
        def markdown(self) -> str:
            md_body = self.convert(self.page.html)
            markdown = f"{self.front_matter}\n"
            if settings.export.page_breadcrumbs:
                markdown += f"{self.breadcrumbs}\n"
            markdown += f"{md_body}\n"
            return markdown

        @property
        def front_matter(self) -> str:
            indent = self.options["front_matter_indent"]
            self.set_page_properties(tags=self.labels)

            if not self.page_properties:
                return ""

            yml = yaml.dump(self.page_properties, indent=indent).strip()
            # Indent the root level list items
            yml = re.sub(r"^( *)(- )", r"\1" + " " * indent + r"\2", yml, flags=re.MULTILINE)
            return f"---\n{yml}\n---\n"

        @property
        def breadcrumbs(self) -> str:
            return (
                " > ".join(
                    [self.convert_page_link(ancestor.id) for ancestor in self.page.ancestors]
                )
                + "\n"
            )

        @property
        def labels(self) -> list[str]:
            return [f"#{label.name}" for label in self.page.labels]

        def set_page_properties(self, **props: list[str] | str | None) -> None:
            for key, value in props.items():
                if value:
                    self.page_properties[sanitize_key(key)] = value

        def convert_page_properties(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str | None:
            if not settings.export.page_properties_as_front_matter:
                return text

            rows = [
                cast("list[Tag]", tr.find_all(["th", "td"]))
                for tr in cast("list[Tag]", el.find_all("tr"))
                if tr
            ]
            if not rows:
                return None

            props = {
                row[0].get_text(strip=True): self.convert(str(row[1])).strip()
                for row in rows
                if len(row) == 2  # noqa: PLR2004
            }

            self.set_page_properties(**props)
            return None

        def convert_alert(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert Confluence info macros to Markdown GitHub style alerts.

            GitHub specific alert types: https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts
            """
            alert_type_map = {
                "info": "IMPORTANT",
                "panel": "NOTE",
                "tip": "TIP",
                "note": "WARNING",
                "warning": "CAUTION",
            }

            alert_type = alert_type_map.get(str(el["data-macro-name"]), "NOTE")

            blockquote = super().convert_blockquote(el, text, parent_tags)
            return f"\n> [!{alert_type}]{blockquote}"

        def convert_div(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            # Handle Confluence macros
            if el.has_attr("data-macro-name"):
                macro_name = str(el["data-macro-name"])
                if macro_name in self.options["macros_to_ignore"]:
                    return ""

                macro_handlers = {
                    "panel": self.convert_alert,
                    "info": self.convert_alert,
                    "note": self.convert_alert,
                    "tip": self.convert_alert,
                    "warning": self.convert_alert,
                    "details": self.convert_page_properties,
                    "drawio": self.convert_drawio,
                    "plantuml": self.convert_plantuml,
                    "scroll-ignore": self.convert_hidden_content,
                    "toc": self.convert_toc,
                    "jira": self.convert_jira_table,
                    "attachments": self.convert_attachments,
                    "markdown": self.convert_markdown,
                    "mohamicorp-markdown": self.convert_markdown,
                }
                if macro_name in macro_handlers:
                    return macro_handlers[macro_name](el, text, parent_tags)

            class_handlers = {
                "expand-container": self.convert_expand_container,
                "columnLayout": self.convert_column_layout,
            }
            for class_name, handler in class_handlers.items():
                if class_name in str(el.get("class", "")):
                    return handler(el, text, parent_tags)

            return super().convert_div(el, text, parent_tags)

        def convert_expand_container(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:
            """Convert expand-container div to HTML details element."""
            # Extract summary text from expand-control-text
            summary_element = el.find("span", class_="expand-control-text")
            summary_text = (
                summary_element.get_text().strip() if summary_element else "Click here to expand..."
            )

            # Extract content from expand-content
            content_element = el.find("div", class_="expand-content")
            # Recursively convert the content
            content = (
                self.process_tag(content_element, parent_tags).strip() if content_element else ""
            )

            # Return as details element
            return f"\n<details>\n<summary>{summary_text}</summary>\n\n{content}\n\n</details>\n\n"

        def convert_span(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if el.has_attr("data-macro-name"):
                if el["data-macro-name"] == "jira":
                    return self.convert_jira_issue(el, text, parent_tags)

            return text

        def convert_attachments(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            file_header = el.find("th", {"class": "filename-column"})
            file_header_text = file_header.text.strip() if file_header else "File"

            modified_header = el.find("th", {"class": "modified-column"})
            modified_header_text = modified_header.text.strip() if modified_header else "Modified"

            def _get_path(p: Path) -> str:
                attachment_path = self._get_path_for_href(p, settings.export.attachment_href)
                return attachment_path.replace(" ", "%20")

            rows = [
                {
                    "file": f"[{att.title}]({_get_path(att.export_path)})",
                    "modified": f"{att.version.friendly_when} by {self.convert_user(att.version.by)}",  # noqa: E501
                }
                for att in self.page.attachments
            ]

            html = f"""<table>
            <tr><th>{file_header_text}</th><th>{modified_header_text}</th></tr>
            {"".join(f"<tr><td>{row['file']}</td><td>{row['modified']}</td></tr>" for row in rows)}
            </table>"""

            return (
                f"\n\n{self.convert_table(BeautifulSoup(html, 'html.parser'), text, parent_tags)}\n"
            )

        def convert_column_layout(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:
            cells = el.find_all("div", {"class": "cell"})

            if len(cells) < 2:  # noqa: PLR2004
                return super().convert_div(el, text, parent_tags)

            html = f"<table><tr>{''.join([f'<td>{cell!s}</td>' for cell in cells])}</tr></table>"

            return self.convert_table(BeautifulSoup(html, "html.parser"), text, parent_tags)

        def convert_jira_table(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            jira_tables = BeautifulSoup(self.page.body_export, "html.parser").find_all(
                "div", {"class": "jira-table"}
            )

            if len(jira_tables) == 0:
                logger.warning("No Jira table found. Ignoring.")
                return text

            if len(jira_tables) > 1:
                logger.exception("Multiple Jira tables are not supported. Ignoring.")
                return text

            return self.process_tag(jira_tables[0], parent_tags)

        def convert_toc(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            tocs = BeautifulSoup(self.page.body_export, "html.parser").find_all(
                "div", {"class": "toc-macro"}
            )

            if len(tocs) == 0:
                logger.warning("Could not find TOC macro. Ignoring.")
                return text

            if len(tocs) > 1:
                logger.exception("Multiple TOC macros are not supported. Ignoring.")
                return text

            return self.process_tag(tocs[0], parent_tags)

        def convert_hidden_content(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:
            content = super().convert_p(el, text, parent_tags)
            return f"\n<!--{content}-->\n"

        def convert_jira_issue(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            issue_key = el.get("data-jira-key")
            link = cast("BeautifulSoup", el.find("a", {"class": "jira-issue-key"}))
            if not link:
                return text
            if not issue_key:
                return self.process_tag(link, parent_tags)

            try:
                jira_url = _extract_jira_base_url(str(link.get("href", ""))) or self.page.base_url
                issue = JiraIssue.from_key(str(issue_key), jira_url)
            except HTTPError:
                return f"[[{issue_key}]]({link.get('href')})"

            if not issue:
                return f"[[{issue_key}]]({link.get('href')})"

            return f"[[{issue.key}] {issue.summary}]({link.get('href')})"

        def convert_pre(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:  # type: ignore[override]
            if not text:
                return ""

            code_language = ""
            if el.has_attr("data-syntaxhighlighter-params"):
                match = re.search(r"brush:\s*([^;]+)", str(el["data-syntaxhighlighter-params"]))
                if match:
                    code_language = match.group(1)

            return f"\n\n```{code_language}\n{text}\n```\n\n"

        def convert_sub(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            return f"<sub>{text}</sub>"

        def convert_sup(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert superscript to Markdown footnotes."""
            if el.previous_sibling is None:
                return f"[^{text}]:"  # Footnote definition
            return f"[^{text}]"  # f"<sup>{text}</sup>"

        def convert_a(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:  # noqa: PLR0911, C901
            if "user-mention" in str(el.get("class")):
                return self.convert_user_mention(el, text, parent_tags)
            if "createpage.action" in str(el.get("href")) or "createlink" in str(el.get("class")):
                logger.warning(
                    f"Broken link detected: '{text}' on page '{self.page.title}' "
                    f"(ID: {self.page.id}). This is likely a Confluence bug. "
                    f"Please report this issue to Atlassian Support."
                )
                # Find fallback link without using string= parameter to avoid
                # BeautifulSoup recursion bug. The string= parameter triggers
                # recursive .string property access which fails on Fabric
                # Editor v2 HTML with fab:media tags
                try:
                    soup = BeautifulSoup(self.page.editor2, "html.parser")
                    for link in soup.find_all("a"):
                        # Use get_text() instead of .string to avoid recursion issues
                        link_text = link.get_text(strip=True)
                        if link_text == text:
                            # Prevent infinite recursion if fallback is the same element
                            if isinstance(link, Tag) and link.get("href") != el.get("href"):
                                return self.convert_a(link, text, parent_tags)  # type: ignore[arg-type]
                except RecursionError:
                    # editor2 HTML contains problematic tags (e.g., fab:media)
                    # that cause BS4 recursion. Skip fallback and return
                    # wiki-style link
                    pass
                # If no matching link found, return wiki-style link
                return f"[[{text}]]"
            if "page" in str(el.get("data-linked-resource-type")):
                page_id = str(el.get("data-linked-resource-id", ""))
                if page_id and page_id != "null":
                    return self.convert_page_link(int(page_id))
            if "attachment" in str(el.get("data-linked-resource-type")):
                link = self.convert_attachment_link(el, text, parent_tags)
                # convert_attachment_link may return None if the attachment meta is incomplete
                return link or f"[{text}]({el.get('href')})"
            if match := parse_confluence_path(str(el.get("href", ""))):
                if match.page_id:
                    return self.convert_page_link(match.page_id)
            if str(el.get("href", "")).startswith("#"):
                # Handle heading links
                return f"[{text}](#{sanitize_key(text, '-')})"

            return super().convert_a(el, text, parent_tags)

        def convert_page_link(self, page_id: int) -> str:
            if not page_id:
                msg = "Page link does not have valid page_id."
                raise ValueError(msg)

            page = Page.from_id(page_id, self.page.base_url)

            if page.title == "Page not accessible":
                logger.warning(
                    f"Confluence page link (ID: {page_id}) is not accessible, "
                    f"referenced from page '{self.page.title}' (ID: {self.page.id})"
                )
                return f"[Page not accessible (ID: {page_id})]"

            page_path = self._get_path_for_href(page.export_path, settings.export.page_href)

            return f"[{page.title}]({page_path.replace(' ', '%20')})"

        def convert_attachment_link(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:
            """Build a Markdown link for an attachment.

            If the attachment metadata is missing,
            return the original Confluence URL instead of crashing.
            """
            attachment = None
            if fid := el.get("data-linked-resource-file-id"):
                attachment = self.page.get_attachment_by_file_id(str(fid))
            if not attachment and (fid := el.get("data-media-id")):
                attachment = self.page.get_attachment_by_file_id(str(fid))
            if not attachment and (aid := el.get("data-linked-resource-id")):
                attachment = self.page.get_attachment_by_id(str(aid))

            if attachment is None:
                href = el.get("href") or text
                return f"[{text}]({href})"

            path = self._get_path_for_href(attachment.export_path, settings.export.attachment_href)
            return f"[{attachment.title}]({path.replace(' ', '%20')})"

        def convert_time(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if el.has_attr("datetime"):
                return f"{el['datetime']}"

            return f"{text}"

        def convert_user_mention(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if aid := el.get("data-account-id"):
                try:
                    return self.convert_user(User.from_accountid(str(aid), self.page.base_url))
                except ApiNotFoundError:
                    logger.warning(f"User {aid} not found. Using text instead.")

            return self.convert_user_name(text)

        def convert_user(self, user: User) -> str:
            return self.convert_user_name(user.display_name)

        def convert_user_name(self, name: str) -> str:
            return name.removesuffix("(Unlicensed)").removesuffix("(Deactivated)").strip()

        def convert_li(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            md = super().convert_li(el, text, parent_tags)
            bullet = self.options["bullets"][0]

            # Convert Confluence task lists to GitHub task lists
            if el.has_attr("data-inline-task-id"):
                is_checked = el.has_attr("class") and "checked" in el["class"]
                return md.replace(f"{bullet} ", f"{bullet} {'[x]' if is_checked else '[ ]'} ", 1)

            return md

        def convert_img(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:  # noqa: C901
            attachment = None
            if fid := el.get("data-media-id"):
                attachment = self.page.get_attachment_by_file_id(str(fid))
            if not attachment and (fid := el.get("data-media-id")):
                attachment = self.page.get_attachment_by_file_id(str(fid))
            if not attachment and (aid := el.get("data-linked-resource-id")):
                attachment = self.page.get_attachment_by_id(str(aid))

            url_src = str(el.get("src", ""))

            if ".drawio.png" in url_src:
                filename = unquote(urlparse(url_src).path.split("/")[-1])
                drawio_result = self._convert_drawio_embedded_mermaid(filename)
                if drawio_result:
                    return drawio_result
                # If no mermaid diagram extracted, use PNG as attachment fallback
                if attachment is None:
                    drawio_images = self.page.get_attachments_by_title(filename)
                    if len(drawio_images) > 0:
                        attachment = drawio_images[0]

            if attachment is None:
                href = el.get("href") or text
                if href:
                    return f"![{text}]({href})"
                if url_src:
                    return f"![{text}]({url_src})"
                return text

            path = self._get_path_for_href(attachment.export_path, settings.export.attachment_href)
            el["src"] = path.replace(" ", "%20")
            if "_inline" in parent_tags:
                parent_tags.remove("_inline")  # Always show images.
            return super().convert_img(el, text, parent_tags)

        def _normalize_unicode_whitespace(self, text: str) -> str:
            r"""Normalize Unicode whitespace to regular spaces.

            This fixes an issue where markdownify's chomp() function strips Unicode
            whitespace characters (like \xa0 from &nbsp;) entirely, causing missing
            spaces in markdown output.

            Confluence often uses &nbsp; (non-breaking space, \xa0) inside inline
            formatting tags like <em>&nbsp;text</em>. BeautifulSoup correctly converts
            this to \xa0, but markdownify's chomp() doesn't preserve it, resulting in
            output like "word*text*" instead of "word *text*".

            This method normalizes all Unicode whitespace characters to regular ASCII
            spaces so they are preserved by markdownify's chomp() function.

            Args:
                text: Text string to normalize

            Returns:
                Text with Unicode whitespace replaced by regular spaces
            """
            # Normalize all Unicode whitespace to regular space
            # This includes: \xa0 (nbsp), \u2000-\u200a (various spaces),
            # \u2028 (line separator), \u2029 (paragraph separator), etc.
            # Keep \n, \r, \t as-is since they have semantic meaning
            normalized = text
            for char in text:
                if char.isspace() and char not in " \n\r\t":
                    # Replace Unicode whitespace with regular space
                    normalized = normalized.replace(char, " ")
            return normalized

        def convert_em(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert <em> tags, preserving spaces from Unicode whitespace entities."""
            text = self._normalize_unicode_whitespace(text)
            return super().convert_em(el, text, parent_tags)

        def convert_strong(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert <strong> tags, preserving spaces from Unicode whitespace entities."""
            text = self._normalize_unicode_whitespace(text)
            return super().convert_strong(el, text, parent_tags)

        def convert_code(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert <code> tags, preserving spaces from Unicode whitespace entities."""
            text = self._normalize_unicode_whitespace(text)
            return super().convert_code(el, text, parent_tags)

        def convert_i(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert <i> tags, preserving spaces from Unicode whitespace entities."""
            text = self._normalize_unicode_whitespace(text)
            return super().convert_i(el, text, parent_tags)

        def convert_b(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert <b> tags, preserving spaces from Unicode whitespace entities."""
            text = self._normalize_unicode_whitespace(text)
            return super().convert_b(el, text, parent_tags)

        def _convert_drawio_embedded_mermaid(self, filename: str) -> str | None:
            """Extract mermaid diagram from DrawIO PNG preview image.

            Args:
                filename: The filename of the drawio diagram image.

            Returns:
                Markdown formatted mermaid diagram or None if not found.
            """
            drawio_title = filename.removesuffix(".png")
            drawio_attachments = self.page.get_attachments_by_title(drawio_title)

            if len(drawio_attachments) == 0:
                return None

            drawio_filepath = settings.export.output_path / drawio_attachments[0].export_path
            if not drawio_filepath.exists():
                return None

            # Extract mermaid diagram from DrawIO file
            return load_and_parse_drawio(str(drawio_filepath))

        def convert_drawio(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if match := re.search(r"\|diagramName=(.+?)\|", str(el)):
                drawio_name = match.group(1)
                preview_name = f"{drawio_name}.png"
                drawio_attachments = self.page.get_attachments_by_title(drawio_name)
                preview_attachments = self.page.get_attachments_by_title(preview_name)

                if not drawio_attachments or not preview_attachments:
                    return f"\n<!-- Drawio diagram `{drawio_name}` not found -->\n\n"

                drawio_path = self._get_path_for_href(
                    drawio_attachments[0].export_path, settings.export.attachment_href
                )
                preview_path = self._get_path_for_href(
                    preview_attachments[0].export_path, settings.export.attachment_href
                )

                drawio_image_embedding = f"![{drawio_name}]({preview_path.replace(' ', '%20')})"
                drawio_link = f"[{drawio_image_embedding}]({drawio_path.replace(' ', '%20')})"
                return f"\n{drawio_link}\n\n"

            return ""

        def convert_plantuml(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:  # noqa: PLR0911, C901
            """Convert PlantUML diagrams from editor2 XML to Markdown code blocks.

            PlantUML diagrams are stored in the editor2 XML as structured macros with
            the UML definition in a JSON structure inside CDATA sections.
            """
            # Parse the editor2 XML to find the PlantUML macro
            # The editor2 content is an XML fragment without a root element, so wrap it
            wrapped_editor2 = f"<root>{self.page.editor2}</root>"
            soup_editor2 = BeautifulSoup(wrapped_editor2, "xml")

            # Get the macro-id from the current element to match it in editor2
            macro_id = el.get("data-macro-id")
            if not macro_id:
                logger.warning("PlantUML macro found but no macro-id attribute")
                return "\n<!-- PlantUML diagram (no macro-id found) -->\n\n"

            # Find the corresponding macro in editor2 XML
            # BeautifulSoup with lxml strips namespace prefixes from both
            # element and attribute names
            # So ac:structured-macro becomes structured-macro, ac:name becomes name, etc.
            plantuml_macros = soup_editor2.find_all("structured-macro")
            plantuml_macro: Tag | None = None
            for macro in plantuml_macros:
                if not isinstance(macro, Tag):
                    continue
                if macro.get("name") == "plantuml" and macro.get("macro-id") == macro_id:
                    plantuml_macro = macro
                    break

            if not plantuml_macro:
                logger.warning(f"PlantUML macro with id {macro_id} not found in editor2 XML")
                return "\n<!-- PlantUML diagram (not found in editor2) -->\n\n"

            # Extract the plain-text-body containing the JSON
            plain_text_body = plantuml_macro.find("plain-text-body")
            if not isinstance(plain_text_body, Tag):
                logger.warning(f"PlantUML macro {macro_id} has no plain-text-body")
                return "\n<!-- PlantUML diagram (no content found) -->\n\n"

            # Extract the JSON from CDATA
            cdata_content = plain_text_body.get_text(strip=True)
            if not cdata_content:
                logger.warning(f"PlantUML macro {macro_id} has empty content")
                return "\n<!-- PlantUML diagram (empty content) -->\n\n"

            # Parse the JSON to get the umlDefinition
            try:
                plantuml_data = json.loads(cdata_content)
                uml_definition = plantuml_data.get("umlDefinition", "")

                if not uml_definition:
                    logger.warning(f"PlantUML macro {macro_id} has no umlDefinition")
                    return "\n<!-- PlantUML diagram (no UML definition) -->\n\n"

            except json.JSONDecodeError:
                logger.exception(f"Failed to parse PlantUML JSON for macro {macro_id}")
                return "\n<!-- PlantUML diagram (invalid JSON) -->\n\n"
            else:
                # Return as a Markdown code block with plantuml syntax
                return f"\n```plantuml\n{uml_definition}\n```\n\n"

        def _find_element_with_namespace(self, parent: BeautifulSoup, tag_name: str) -> Tag | None:
            """Find an element with or without namespace prefix."""
            result = parent.find(f"ac:{tag_name}") or parent.find(tag_name)
            return result if isinstance(result, Tag) else None

        def _find_structured_macro(self, el: BeautifulSoup) -> Tag | None:
            """Find structured-macro element with or without namespace."""
            return self._find_element_with_namespace(el, "structured-macro")

        def _extract_plain_text_body(self, el: BeautifulSoup | Tag) -> str | None:
            """Extract markdown content from plain-text-body element."""
            plain_text_body = self._find_element_with_namespace(el, "plain-text-body")  # type: ignore[arg-type]
            if plain_text_body:
                return plain_text_body.get_text()
            return None

        def _extract_markdown_parameter(self, el: BeautifulSoup | Tag) -> str | None:
            """Extract markdown content from parameter element."""
            param = el.find("ac:parameter", {"ac:name": "markdown"})
            if param is None:
                param = el.find("parameter", {"name": "markdown"})
            if isinstance(param, Tag):
                return param.get_text()
            return None

        def _extract_markdown_from_body(self, el: BeautifulSoup) -> str | None:
            """Extract markdown content from body HTML."""
            # Try plain-text-body first (standard markdown macro)
            markdown_content = self._extract_plain_text_body(el)
            if markdown_content:
                return markdown_content

            # Check in structured-macro child element
            structured_macro = self._find_structured_macro(el)
            if structured_macro:
                markdown_content = self._extract_plain_text_body(structured_macro)
                if markdown_content:
                    return markdown_content

            # Try parameter for mohamicorp-markdown
            markdown_content = self._extract_markdown_parameter(el)
            if markdown_content:
                return markdown_content

            # Check parameter in structured-macro child
            if structured_macro:
                markdown_content = self._extract_markdown_parameter(structured_macro)
                if markdown_content:
                    return markdown_content

            return None

        def _extract_markdown_from_editor2(self, macro_id: str) -> str | None:
            """Extract markdown content from editor2 XML."""
            wrapped_editor2 = f"<root>{self.page.editor2}</root>"
            soup_editor2 = BeautifulSoup(wrapped_editor2, "xml")

            # BeautifulSoup strips namespace prefixes, so ac:structured-macro
            # becomes structured-macro
            markdown_macros = soup_editor2.find_all("structured-macro")
            for macro in markdown_macros:
                if not isinstance(macro, Tag):
                    continue
                if (
                    macro.get("name") in ("markdown", "mohamicorp-markdown")
                    and macro.get("macro-id") == macro_id
                ):
                    # Try plain-text-body first
                    plain_text_body = macro.find("plain-text-body")
                    if isinstance(plain_text_body, Tag):
                        return plain_text_body.get_text(strip=True)

                    # Try parameter for mohamicorp-markdown
                    param = macro.find("parameter", {"name": "markdown"})
                    if isinstance(param, Tag):
                        return param.get_text(strip=True)

            return None

        def convert_markdown(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert Markdown macro fragments to Markdown.

            Supports both standard 'markdown' macro and 'mohamicorp-markdown'
            macro. The content is already in Markdown format, so we just extract
            and return it.
            """
            macro_name = el.get("data-macro-name", "")

            # First, try to extract from body HTML
            markdown_content = self._extract_markdown_from_body(el)

            # If not found, try editor2 XML (similar to plantuml)
            if not markdown_content:
                macro_id = el.get("data-macro-id")
                if macro_id and isinstance(macro_id, str):
                    markdown_content = self._extract_markdown_from_editor2(macro_id)

            if not markdown_content:
                logger.warning(
                    f"Markdown macro ({macro_name}) found but no content could be extracted"
                )
                return f"\n<!-- Markdown macro ({macro_name}) content not found -->\n\n"

            # Return the markdown content directly (it's already in markdown format)
            # Add newlines for proper spacing
            return f"\n{markdown_content}\n\n"

        def convert_table(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if el.has_attr("class") and "metadata-summary-macro" in el["class"]:
                return self.convert_page_properties_report(el, text, parent_tags)

            return super().convert_table(el, text, parent_tags)

        def convert_page_properties_report(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:
            data_cql = el.get("data-cql")
            if not data_cql:
                return ""
            soup = BeautifulSoup(self.page.body_export, "html.parser")
            table = soup.find("table", {"data-cql": data_cql})
            if not table:
                return ""
            return super().convert_table(table, "", parent_tags)  # type: ignore -

        def _get_path_for_href(self, path: Path, style: Literal["absolute", "relative"]) -> str:
            """Get the path to use in href attributes based on settings."""
            if style == "absolute":
                # Note that usually absolute would be
                # something like this: (settings.export.output_path / path).absolute()
                # In this case the URL will be "absolute" to the export path.
                # This is useful for local file links.
                result = "/" + str(path).lstrip("/")
            else:
                result = os.path.relpath(path, self.page.export_path.parent)
            return result


_CQL_MAX_BATCH_SIZE: int = 25


def _fetch_page_ids_v2_batch(batch: list[str], base_url: str) -> set[str]:
    """Single v2 API request for a batch of page IDs.

    Uses GET /api/v2/pages?id=X&id=Y&...  (Atlassian Cloud).
    The v2 API accepts multiple ``id`` params, so they are encoded directly
    into the URL path since the SDK only accepts a dict for ``params``.
    """
    query = urllib.parse.urlencode([("id", pid) for pid in batch] + [("limit", len(batch))])
    response = cast("dict", get_thread_confluence(base_url).get(f"api/v2/pages?{query}"))
    if not response:
        return set()
    return {str(item["id"]) for item in response.get("results", [])}


def _fetch_page_ids_cql_batch(batch: list[str], base_url: str) -> set[str]:
    """Single CQL v1 request for a batch of page IDs.

    Uses GET /rest/api/content/search with id in (...) (self-hosted / fallback).
    """
    cql = "id in ({})".format(",".join(batch))
    response = cast(
        "dict",
        get_thread_confluence(base_url).get(
            "rest/api/content/search",
            params={"cql": cql, "limit": len(batch), "fields": "id"},
        ),
    )
    if not response:
        return set()
    return {str(item["id"]) for item in response.get("results", [])}


def fetch_deleted_page_ids(page_ids: list[str], base_url: str) -> set[str]:
    """Return the subset of *page_ids* that no longer exist in Confluence.

    Uses the v2 REST API when ``connection_config.use_v2_api`` is enabled
    (multiple ``id`` query params, up to ``export.existence_check_batch_size``
    IDs per request), or the v1 CQL content search otherwise (capped at
    :data:`_CQL_MAX_BATCH_SIZE` IDs per request).

    Per-batch API failures are handled safely: affected IDs are assumed to
    still exist so they are never accidentally deleted.
    """
    if not page_ids:
        return set()

    use_v2 = settings.connection_config.use_v2_api
    batch_size = settings.export.existence_check_batch_size
    effective_batch_size = batch_size if use_v2 else min(batch_size, _CQL_MAX_BATCH_SIZE)
    n_batches = -(-len(page_ids) // effective_batch_size)  # ceil division
    logger.debug(
        "Checking existence of %d page(s) in %d batch(es) via %s API",
        len(page_ids),
        n_batches,
        "v2" if use_v2 else "v1 CQL",
    )
    existing: set[str] = set()

    for i in range(0, len(page_ids), effective_batch_size):
        batch = page_ids[i : i + effective_batch_size]
        try:
            if use_v2:
                existing.update(_fetch_page_ids_v2_batch(batch, base_url))
            else:
                existing.update(_fetch_page_ids_cql_batch(batch, base_url))
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to check page existence for batch (%d IDs). "
                "Skipping deletion for these pages.",
                len(batch),
            )
            existing.update(batch)

    return set(page_ids) - existing


def sync_removed_pages(base_url: str) -> None:
    """Orchestrate stale-file cleanup: check API for deleted pages, then clean up."""
    if not settings.export.cleanup_stale:
        logger.debug("Stale page cleanup disabled — skipping.")
        return

    unseen = LockfileManager.unseen_ids()
    if not unseen:
        logger.debug("No unseen pages in lockfile — nothing to clean up.")
        return

    with console.status(f"[dim]Checking {len(unseen)} unseen page(s) for removal…[/dim]"):
        deleted = fetch_deleted_page_ids(sorted(unseen), base_url)

    if deleted:
        logger.info("Removing %d stale page(s) from local export.", len(deleted))
    LockfileManager.remove_pages(deleted)


def _make_progress() -> Progress:
    """Build a rich Progress instance for page export."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


def _export_page_worker(page: "Page | Descendant", stats: ExportStats | None = None) -> None:
    """Export a single Confluence page to Markdown (worker function).

    Each page carries its own ``base_url`` so the correct thread-local client
    is used automatically — no global state manipulation needed.

    Args:
        page: The page to export.
        stats: Optional stats tracker to update on completion.
    """
    _page = Page.from_id(page.id, page.base_url)
    attachment_entries = _page.export()
    LockfileManager.record_page(_page, attachment_entries)
    if stats is not None:
        stats.inc_exported()


def export_pages(pages: list["Page | Descendant"]) -> None:
    """Export a list of Confluence pages to Markdown.

    Pages are exported in parallel using ThreadPoolExecutor for significant
    performance improvement. Worker count is read from
    settings.connection_config.max_workers (default: 20).

    Args:
        pages: List of pages to export.
    """
    # Mark all pages as seen so cleanup skips API checks for unchanged pages
    LockfileManager.mark_seen([p.id for p in pages])
    pages_to_export = [page for page in pages if LockfileManager.should_export(page)]

    skipped_count = len(pages) - len(pages_to_export)
    stats = reset_stats(total=len(pages))
    for _ in range(skipped_count):
        stats.inc_skipped()

    if skipped_count:
        logger.info("Skipping %d unchanged page(s).", skipped_count)

    if not pages_to_export:
        logger.info("All %d page(s) unchanged — nothing to export.", len(pages))
        return

    # Get worker count from config
    max_workers = settings.connection_config.max_workers
    serial = settings.export.log_level == "DEBUG" or max_workers <= 1

    mode_label = "serial" if serial else f"parallel ({max_workers} workers)"
    logger.debug("Export mode: %s, pages to export: %d", mode_label, len(pages_to_export))

    with _make_progress() as progress:
        task = progress.add_task(
            f"[cyan]Exporting {len(pages_to_export)} page(s)[/cyan]",
            total=len(pages_to_export),
        )

        if serial:
            for page in pages_to_export:
                progress.update(task, description=f"[cyan]Page {page.id}[/cyan]")
                try:
                    _export_page_worker(page, stats)
                except Exception:
                    logger.exception("Failed to export page %s", page.id)
                    stats.inc_failed()
                finally:
                    progress.advance(task)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(_export_page_worker, page, stats): page
                    for page in pages_to_export
                }
                for future in as_completed(futures):
                    page = futures[future]
                    try:
                        future.result()
                    except Exception:
                        logger.exception("Failed to export page %s", page.id)
                        stats.inc_failed()
                    finally:
                        progress.advance(task)
