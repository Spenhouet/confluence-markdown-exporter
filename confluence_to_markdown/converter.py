import re
from collections.abc import Set
from typing import cast

import yaml
from atlassian import Confluence
from bs4 import BeautifulSoup
from bs4 import Tag
from markdownify import ATX
from markdownify import MarkdownConverter
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from confluence_to_markdown.utils.table_converter import TableConverter


class ConfluenceApiSettings(BaseSettings):
    username: str = Field()
    password: str = Field()
    url: str = Field()

    model_config = SettingsConfigDict(env_file=".env")


# TODO ensure images work
# TODO ensure drawio diagrams work
# TODO ensure other attachments work like PDF or ZIP
# TODO store whole space
# TODO ensure emojis work https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#using-emojis
# TODO support table and figure captions
# TODO ensure page properties report works

# Later
# TODO resolve export internal/relative links
# TODO Support badges via https://shields.io/badges/static-badge
# TODO advanced: read version by version and commit in git using change comment and user info


class ConfluencePageConverter(TableConverter, MarkdownConverter):
    """Create a custom MarkdownConverter for Confluence HTML to Markdown conversion."""

    class Options(MarkdownConverter.DefaultOptions):
        bullets = "-"
        heading_style = ATX
        macros_to_ignore: Set[str] = frozenset(
            ["scroll-ignore", "qc-read-and-understood-signature-box"]
        )

    def __init__(self, **options) -> None:  # noqa: ANN003
        super().__init__(**options)
        settings = ConfluenceApiSettings()  # type: ignore reportCallIssue as the parameters are read via env file
        self.api = Confluence(
            url=settings.url,
            username=settings.username,
            password=settings.password,
        )
        self.page_properties = {}

    def html(self, page_id: int) -> str:
        page_data = cast(dict, self.api.get_page_by_id(page_id=page_id, expand="body.view,space"))

        if not page_data:
            msg = f"PageID {page_id} does not exist."
            raise ValueError(msg)

        title = page_data.get("title", "Unknown")
        body_view = page_data.get("body", {}).get("view", {}).get("value")

        space = page_data.get("space", {})
        self.add_page_properties(space_name=space.get("name"), space_key=space.get("key"))

        return f"<h1>{title}</h1>{body_view}"

    def convert_page(self, page_id: int) -> str:
        self.add_page_properties(tags=self.labels(page_id))
        html = self.html(page_id)
        md_body = self.convert(html)
        return f"{self.front_matter()}\n{md_body}\n"  # Add newline at end of file

    def front_matter(self, indent: int = 2) -> str:
        yml = yaml.dump(self.page_properties, indent=indent).strip()
        # Indent the root level list items
        yml = re.sub(r"^( *)(- )", r"\1" + " " * indent + r"\2", yml, flags=re.MULTILINE)
        return f"---\n{yml}\n---\n"

    def labels(self, page_id: int) -> list[str]:
        label_response = cast(dict, self.api.get_page_labels(page_id))
        if not label_response or not label_response["results"]:
            return []

        return [f"#{label['name']}" for label in label_response["results"]]

    def add_page_properties(self, **props: list[str] | str | None) -> None:
        for key, value in props.items():
            if value:
                self.page_properties[key.lower().replace(" ", "-")] = value

    def convert_page_properties(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> None:
        rows = [
            cast(list[Tag], tr.find_all(["th", "td"])) for tr in cast(list[Tag], el.find_all("tr"))
        ]
        if not rows:
            return

        props = {
            row[0].get_text(strip=True): self.convert(str(row[1])).strip()
            for row in rows
            if len(row) == 2  # noqa: PLR2004
        }

        self.add_page_properties(**props)

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

    def convert_div(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        # Handle Confluence macros
        if el.has_attr("data-macro-name"):
            if el["data-macro-name"] in self.options["macros_to_ignore"]:
                return ""
            if el["data-macro-name"] in ["panel", "info", "note", "tip", "warning"]:
                return self.convert_alert(el, text, parent_tags)
            if el["data-macro-name"] == "details":
                self.convert_page_properties(el, text, parent_tags)

        return super().convert_div(el, text, parent_tags)

    def convert_pre(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        if not text:
            return ""

        code_language = ""
        if el.has_attr("data-syntaxhighlighter-params"):
            match = re.search(r"brush:\s*([^;]+)", str(el["data-syntaxhighlighter-params"]))
            if match:
                code_language = match.group(1)

        return f"\n\n```{code_language}\n{text}\n```\n\n"

    def convert_a(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        if el.has_attr("class") and "user-mention" in el["class"]:
            return self.convert_user(el, text, parent_tags)

        return super().convert_a(el, text, parent_tags)

    def convert_time(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        if el.has_attr("datetime"):
            return f"{el['datetime']}"  # TODO convert to date format?

        return f"{text}"

    def convert_user(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        return f"{text.replace(' (Unlicensed)', '')}"

    def convert_li(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        md = super().convert_li(el, text, parent_tags)
        bullet = self.options["bullets"][0]

        # Convert Confluence task lists to GitHub task lists
        if el.has_attr("data-inline-task-id"):
            is_checked = el.has_attr("class") and "checked" in el["class"]
            return md.replace(f"{bullet} ", f"{bullet} {'[x]' if is_checked else '[ ]'} ", 1)

        return md

    def convert_img(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        # TODO download attachment via API?
        return super().convert_img(el, text, parent_tags)
