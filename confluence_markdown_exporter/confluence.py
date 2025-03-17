"""Confluence API documentation.

https://developer.atlassian.com/cloud/confluence/rest/v1/intro
"""

import functools
import mimetypes
import os
import re
import sys
from collections.abc import Set
from os import PathLike
from pathlib import Path
from typing import TypeAlias
from typing import cast

import yaml
from atlassian import Confluence as ConfluenceApi
from atlassian import Jira
from atlassian.errors import ApiError
from bs4 import BeautifulSoup
from bs4 import Tag
from markdownify import ATX
from markdownify import MarkdownConverter
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from requests import HTTPError
from tqdm import tqdm

from confluence_markdown_exporter.utils.export import sanitize_filename
from confluence_markdown_exporter.utils.export import sanitize_key
from confluence_markdown_exporter.utils.export import save_file
from confluence_markdown_exporter.utils.table_converter import TableConverter

JsonResponse: TypeAlias = dict
StrPath: TypeAlias = str | PathLike[str]

DEBUG: bool = bool(os.getenv("DEBUG"))


class ApiSettings(BaseSettings):
    atlassian_username: str = Field()
    atlassian_api_token: str = Field()
    atlassian_url: str = Field()

    model_config = SettingsConfigDict(env_file=".env")


try:
    settings = ApiSettings()  # type: ignore reportCallIssue as the parameters are read via env file
except ValidationError:
    print(
        "Please set the required environment variables: "
        "ATLASSIAN_USERNAME, ATLASSIAN_API_TOKEN, ATLASSIAN_URL\n\n"
        "Read the README.md for more information."
    )
    sys.exit(1)

confluence = ConfluenceApi(
    url=settings.atlassian_url,
    username=settings.atlassian_username,
    password=settings.atlassian_api_token,
)

jira = Jira(
    url=settings.atlassian_url,
    username=settings.atlassian_username,
    password=settings.atlassian_api_token,
)


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
    @functools.lru_cache(maxsize=100)
    def from_key(cls, issue_key: str) -> "JiraIssue":
        issue_data = cast(JsonResponse, jira.get_issue(issue_key))
        return cls.from_json(issue_data)


class User(BaseModel):
    username: str
    display_name: str
    email: str

    @classmethod
    def from_json(cls, data: JsonResponse) -> "User":
        return cls(
            username=data.get("username", ""),
            display_name=data.get("displayName", ""),
            email=data.get("email", ""),
        )

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_username(cls, username: str) -> "User":
        return cls.from_json(cast(JsonResponse, confluence.get_user_details_by_username(username)))

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_userkey(cls, userkey: str) -> "User":
        return cls.from_json(cast(JsonResponse, confluence.get_user_details_by_userkey(userkey)))

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_accountid(cls, accountid: int) -> "User":
        return cls.from_json(
            cast(JsonResponse, confluence.get_user_details_by_accountid(accountid))
        )


class Organization(BaseModel):
    spaces: list["Space"]

    @property
    def pages(self) -> list[int]:
        return [page for space in self.spaces for page in space.pages]

    def export(self, export_path: StrPath) -> None:
        export_pages(self.pages, export_path)

    @classmethod
    def from_json(cls, data: JsonResponse) -> "Organization":
        return cls(
            spaces=[Space.from_json(space) for space in data.get("results", [])],
        )

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_api(cls) -> "Organization":
        return cls.from_json(
            cast(
                JsonResponse,
                confluence.get_all_spaces(
                    space_type="global", space_status="current", expand="homepage"
                ),
            )
        )


class Space(BaseModel):
    key: str
    name: str
    description: str
    homepage: int

    @property
    def pages(self) -> list[int]:
        homepage = Page.from_id(self.homepage)
        return [self.homepage, *homepage.descendants]

    def export(self, export_path: StrPath) -> None:
        export_pages(self.pages, export_path)

    @classmethod
    def from_json(cls, data: JsonResponse) -> "Space":
        return cls(
            key=data.get("key", ""),
            name=data.get("name", ""),
            description=data.get("description", {}).get("plain", {}).get("value", ""),
            homepage=data.get("homepage", {}).get("id"),
        )

    @classmethod
    @functools.lru_cache(maxsize=100)
    def from_key(cls, space_key: str) -> "Space":
        return cls.from_json(cast(JsonResponse, confluence.get_space(space_key, expand="homepage")))


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


class ExportPath(BaseModel):
    dirpath: Path
    filename: str

    @property
    def filepath(self) -> Path:
        return self.dirpath / self.filename

    @classmethod
    def from_page(cls, page: "Page") -> "ExportPath":
        home_path = Path(
            *[sanitize_filename(Page.from_id(ancestor).title) for ancestor in page.ancestors]
        )
        space_path = Path(sanitize_filename(page.space.name))
        return cls(
            dirpath=space_path / home_path,
            filename=f"{sanitize_filename(page.title)}.md",
        )

    @classmethod
    def from_attachment(cls, attachment: "Attachment") -> "ExportPath":
        space_path = Path(sanitize_filename(attachment.space.name))
        return cls(
            dirpath=space_path / "attachments",
            filename=f"{attachment.filename}",
        )


class Attachment(BaseModel):
    id: str
    title: str
    file_size: int
    space: Space
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
    def export_path(self) -> ExportPath:
        return ExportPath.from_attachment(self)

    @classmethod
    def from_json(cls, data: JsonResponse) -> "Attachment":
        extensions = data.get("extensions", {})
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            space=Space.from_key(data.get("_expandable", {}).get("space", "").split("/")[-1]),
            file_size=extensions.get("fileSize", 0),
            media_type=extensions.get("mediaType", ""),
            media_type_description=extensions.get("mediaTypeDescription", ""),
            file_id=extensions.get("fileId", ""),
            collection_name=extensions.get("collectionName", ""),
            download_link=data.get("_links", {}).get("download", ""),
            comment=extensions.get("comment", ""),
        )

    def export(self, export_path: StrPath) -> None:
        filepath = Path(export_path) / self.export_path.filepath
        if filepath.exists():
            return

        response = confluence._session.get(str(confluence.url + self.download_link))
        response.raise_for_status()  # Raise error if request fails

        save_file(
            filepath,
            response.content,
        )


class Page(BaseModel):
    id: int
    title: str
    space: Space
    body: str
    body_export: str
    editor2: str
    labels: list["Label"]
    attachments: list["Attachment"]
    ancestors: list[int]

    @property
    def descendants(self) -> list[int]:
        url = f"rest/api/content/{self.id}/descendant/page"
        try:
            response = cast(JsonResponse, confluence.get(url, params={"limit": 10000}))
        except HTTPError as e:
            if e.response.status_code == 404:  # noqa: PLR2004
                # Raise ApiError as the documented reason is ambiguous
                msg = (
                    "There is no content with the given id, "
                    "or the calling user does not have permission to view the content"
                )
                raise ApiError(msg, reason=e) from e

            raise

        return [page.get("id") for page in response.get("results", [])]

    @property
    def export_path(self) -> ExportPath:
        return ExportPath.from_page(self)

    @property
    def html(self) -> str:
        return f"<h1>{self.title}</h1>{self.body}"

    @property
    def markdown(self) -> str:
        return self.Converter(self).markdown

    def export(self, export_path: StrPath) -> None:
        if DEBUG:
            self.export_body(export_path)
        self.export_markdown(export_path)
        self.export_attachments(export_path)

    def export_with_descendants(self, export_path: StrPath) -> None:
        export_pages([self.id, *self.descendants], export_path)

    def export_body(self, export_path: StrPath) -> None:
        soup = BeautifulSoup(self.html, "html.parser")
        save_file(
            Path(export_path)
            / self.export_path.dirpath
            / f"{self.export_path.filepath.stem}_body_view.html",
            str(soup.prettify()),
        )
        soup = BeautifulSoup(self.body_export, "html.parser")
        save_file(
            Path(export_path)
            / self.export_path.dirpath
            / f"{self.export_path.filepath.stem}_body_export_view.html",
            str(soup.prettify()),
        )
        save_file(
            Path(export_path)
            / self.export_path.dirpath
            / f"{self.export_path.filepath.stem}_body_editor2.xml",
            str(self.editor2),
        )

    def export_markdown(self, export_path: StrPath) -> None:
        save_file(
            Path(export_path) / self.export_path.filepath,
            self.markdown,
        )

    def export_attachments(self, export_path: StrPath) -> None:
        for attachment in self.attachments:
            if (
                attachment.filename.endswith(".drawio")
                and f"diagramName={attachment.title}" in self.body
            ):
                attachment.export(export_path)
                continue
            if (
                attachment.filename.endswith(".drawio.png")
                and attachment.title.replace(" ", "%20") in self.body_export
            ):
                attachment.export(export_path)
                continue
            if attachment.file_id in self.body:
                attachment.export(export_path)
                continue

    def get_attachment_by_file_id(self, file_id: str) -> Attachment:
        return next(attachment for attachment in self.attachments if attachment.file_id == file_id)

    def get_attachments_by_title(self, title: str) -> list[Attachment]:
        return [attachment for attachment in self.attachments if attachment.title == title]

    @classmethod
    def from_json(cls, data: JsonResponse) -> "Page":
        attachments = cast(
            JsonResponse, confluence.get_attachments_from_content(data.get("id", 0), limit=1000)
        )
        return cls(
            id=data.get("id", 0),
            title=data.get("title", ""),
            space=Space.from_key(data.get("_expandable", {}).get("space", "").split("/")[-1]),
            body=data.get("body", {}).get("view", {}).get("value", ""),
            body_export=data.get("body", {}).get("export_view", {}).get("value", ""),
            editor2=data.get("body", {}).get("editor2", {}).get("value", ""),
            labels=[
                Label.from_json(label)
                for label in data.get("metadata", {}).get("labels", {}).get("results", [])
            ],
            attachments=[
                Attachment.from_json(attachment) for attachment in attachments.get("results", [])
            ],
            ancestors=[ancestor.get("id") for ancestor in data.get("ancestors", [])],
        )

    @classmethod
    @functools.lru_cache(maxsize=1000)
    def from_id(cls, page_id: int) -> "Page":
        return cls.from_json(
            cast(
                JsonResponse,
                confluence.get_page_by_id(
                    page_id,
                    expand="body.view,body.export_view,body.editor2,metadata.labels,"
                    "metadata.properties,ancestors",
                ),
            )
        )

    class Converter(TableConverter, MarkdownConverter):
        """Create a custom MarkdownConverter for Confluence HTML to Markdown conversion."""

        # TODO Support table captions
        # TODO Support figure captions (934379624)

        # FIXME Potentially the REST API timesout - retry?

        # Advanced/Future features:
        # TODO Support badges via https://shields.io/badges/static-badge
        # TODO Read version by version and commit in git using change comment and user info
        # TODO what to do with page comments?

        class Options(MarkdownConverter.DefaultOptions):
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
            return f"{self.front_matter}\n{self.breadcrumbs}\n{md_body}\n"

        @property
        def front_matter(self) -> str:
            indent = self.options["front_matter_indent"]
            space = self.page.space
            self.set_page_properties(space_name=space.name, space_key=space.key)
            self.set_page_properties(tags=self.labels)

            yml = yaml.dump(self.page_properties, indent=indent).strip()
            # Indent the root level list items
            yml = re.sub(r"^( *)(- )", r"\1" + " " * indent + r"\2", yml, flags=re.MULTILINE)
            return f"---\n{yml}\n---\n"

        @property
        def breadcrumbs(self) -> str:
            return (
                " > ".join([self.convert_page_link(ancestor) for ancestor in self.page.ancestors])
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
        ) -> None:
            # TODO can this be queries via REST API instead?

            rows = [
                cast(list[Tag], tr.find_all(["th", "td"]))
                for tr in cast(list[Tag], el.find_all("tr"))
            ]
            if not rows:
                return

            props = {
                row[0].get_text(strip=True): self.convert(str(row[1])).strip()
                for row in rows
                if len(row) == 2  # noqa: PLR2004
            }

            self.set_page_properties(**props)

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

            return f"\n> [!{alert_type}]\n> {text.strip()}\n\n"

        def convert_div(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:  # noqa: PLR0911
            # Handle Confluence macros
            if el.has_attr("data-macro-name"):
                if el["data-macro-name"] in self.options["macros_to_ignore"]:
                    return ""
                if el["data-macro-name"] in ["panel", "info", "note", "tip", "warning"]:
                    return self.convert_alert(el, text, parent_tags)
                if el["data-macro-name"] == "details":
                    self.convert_page_properties(el, text, parent_tags)
                if el["data-macro-name"] == "drawio":
                    return self.convert_drawio(el, text, parent_tags)
                if el["data-macro-name"] == "scroll-ignore":
                    return self.convert_comment(el, text, parent_tags)
                if el["data-macro-name"] == "toc":
                    return self.convert_toc(el, text, parent_tags)
                if el["data-macro-name"] == "jira":
                    return self.convert_jira_table(el, text, parent_tags)
            if "columnLayout" in str(el.get("class", "")):
                return self.convert_column_layout(el, text, parent_tags)

            return super().convert_div(el, text, parent_tags)

        def convert_span(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if el.has_attr("data-macro-name"):
                if el["data-macro-name"] == "jira":
                    return self.convert_jira_issue(el, text, parent_tags)

            return text

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

            if len(jira_tables) > 1:
                print("Multiple Jira tables are not supported. Ignoring.")
                return text

            return self.process_tag(jira_tables[0], parent_tags)

        def convert_toc(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            tocs = BeautifulSoup(self.page.body_export, "html.parser").find_all(
                "div", {"class": "toc-macro"}
            )

            if len(tocs) > 1:
                print("Multiple TOC macros are not supported. Ignoring.")
                return text

            return self.process_tag(tocs[0], parent_tags)

        def convert_comment(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if _ := el.find("div", {"data-macro-name": "toc"}):
                return super().convert_div(el, text, parent_tags)

            content = super().convert_p(el, text, parent_tags)
            return f"\n<!--{content}-->\n"

        def convert_jira_issue(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            issue_key = el.get("data-jira-key")
            link = cast(BeautifulSoup, el.find("a", {"class": "jira-issue-key"}))
            if not issue_key:
                return self.process_tag(link, parent_tags)
            if not link:
                return text
            issue = JiraIssue.from_key(str(issue_key))
            return f"[[{issue.key}] {issue.summary}]({link.get('href')})"

        def convert_pre(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
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

        def convert_a(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:  # noqa: PLR0911
            if "user-mention" in str(el.get("class")):
                return self.convert_user(el, text, parent_tags)
            if "createpage.action" in str(el.get("href")) or "createlink" in str(el.get("class")):
                if fallback := BeautifulSoup(self.page.editor2, "html.parser").find(
                    "a", string=text
                ):
                    return self.convert_a(fallback, text, parent_tags)  # type: ignore -
                return f"[[{text}]]"
            if "page" in str(el.get("data-linked-resource-type")):
                page_id = el.get("data-linked-resource-id")
                return self.convert_page_link(int(str(page_id)))
            if "attachment" in str(el.get("data-linked-resource-type")):
                return self.convert_attachment_link(el, text, parent_tags)
            if match := re.search(r"/wiki/.+?/pages/(\d+)", str(el.get("href", ""))):
                page_id = match.group(1)
                return self.convert_page_link(int(page_id))
            if str(el.get("href", "")).startswith("#"):
                # Handle heading links
                return f"[{text}](#{sanitize_key(text, '-')})"

            return super().convert_a(el, text, parent_tags)

        def convert_page_link(self, page_id: int) -> str:
            if not page_id:
                msg = "Page link does not have valid page_id."
                raise ValueError(msg)

            page = Page.from_id(page_id)
            relpath = os.path.relpath(page.export_path.filepath, self.page.export_path.dirpath)

            return f"[{page.title}]({relpath.replace(' ', '%20')})"

        def convert_attachment_link(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:
            attachment_id = el.get("data-media-id")
            attachment = self.page.get_attachment_by_file_id(str(attachment_id))
            relpath = os.path.relpath(
                attachment.export_path.filepath, self.page.export_path.dirpath
            )
            return f"[{attachment.title}]({relpath.replace(' ', '%20')})"

        def convert_time(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if el.has_attr("datetime"):
                return f"{el['datetime']}"  # TODO convert to date format?

            return f"{text}"

        def convert_user(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            return f"{text.removesuffix('(Unlicensed)').removesuffix('(Deactivated)').strip()}"

        def convert_li(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            md = super().convert_li(el, text, parent_tags)
            bullet = self.options["bullets"][0]

            # Convert Confluence task lists to GitHub task lists
            if el.has_attr("data-inline-task-id"):
                is_checked = el.has_attr("class") and "checked" in el["class"]
                return md.replace(f"{bullet} ", f"{bullet} {'[x]' if is_checked else '[ ]'} ", 1)

            return md

        def convert_img(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            file_id = el.get("data-media-id")
            if not file_id:
                return ""

            attachment = self.page.get_attachment_by_file_id(str(file_id))
            relpath = os.path.relpath(
                attachment.export_path.filepath, self.page.export_path.dirpath
            )
            el["src"] = relpath.replace(" ", "%20")
            if "_inline" in parent_tags:
                parent_tags.remove("_inline")  # Always show images.
            return super().convert_img(el, text, parent_tags)
            # REPORT Wiki style image link has alignment issues
            # return f"![[{attachment.export_path.filepath}]]"

        def convert_drawio(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if match := re.search(r"\|diagramName=(.+?)\|", str(el)):
                drawio_name = match.group(1)
                preview_name = f"{drawio_name}.png"
                drawio_attachments = self.page.get_attachments_by_title(drawio_name)
                preview_attachments = self.page.get_attachments_by_title(preview_name)

                if not drawio_attachments or not preview_attachments:
                    return f"\n<!-- Drawio diagram `{drawio_name}` not found -->\n\n"

                drawio_relpath = os.path.relpath(
                    drawio_attachments[0].export_path.filepath, self.page.export_path.dirpath
                )
                preview_relpath = os.path.relpath(
                    preview_attachments[0].export_path.filepath, self.page.export_path.dirpath
                )

                drawio_image_embedding = f"![{drawio_name}]({preview_relpath.replace(' ', '%20')})"
                drawio_link = f"[{drawio_image_embedding}]({drawio_relpath.replace(' ', '%20')})"
                return f"\n{drawio_link}\n\n"

            return ""

        def convert_table(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if el.has_attr("class") and "metadata-summary-macro" in el["class"]:
                return self.convert_page_properties_report(el, text, parent_tags)

            return super().convert_table(el, text, parent_tags)

        def convert_page_properties_report(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:
            # TODO can this be queries via REST API instead?
            # api.cql('label = "curated-dataset" and space = STRUCT and parent = 688816133', expand='metadata.properties')
            # data-macro-id="5836d104-f9e9-44cf-9d05-e332b86275c0"
            # https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content---macro-body/#api-wiki-rest-api-content-id-history-version-macro-id-macroid-get
            # Find out how to fetch the macro content

            # TODO instead use markdown integrated front matter properties query

            data_cql = el.get("data-cql")
            if not data_cql:
                return ""
            soup = BeautifulSoup(self.page.body_export, "html.parser")
            table = soup.find("table", {"data-cql": data_cql})
            return super().convert_table(table, "", parent_tags)  # type: ignore -


def export_page(page_id: int, output_path: StrPath) -> None:
    """Export a Confluence page to Markdown.

    Args:
        page_id: The page id.
        output_path: The output path.
    """
    page = Page.from_id(page_id)
    page.export(output_path)


def export_pages(page_ids: list[int], output_path: StrPath) -> None:
    """Export a list of Confluence pages to Markdown.

    Args:
        page_ids: List of pages to export.
        output_path: The output path.
    """
    for page_id in (pbar := tqdm(page_ids, smoothing=0.05)):
        pbar.set_postfix_str(f"Exporting page {page_id}")
        export_page(page_id, output_path)
