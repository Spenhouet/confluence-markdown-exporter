"""Confluence API documentation.

https://developer.atlassian.com/cloud/confluence/rest/v2/intro
"""

import re
from collections.abc import Set
from typing import TypeAlias
from typing import cast

import yaml
from atlassian import Confluence as ConfluenceApi
from bs4 import BeautifulSoup
from bs4 import Tag
from markdownify import ATX
from markdownify import MarkdownConverter
from pydantic import BaseModel
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from confluence_to_markdown.utils.table_converter import TableConverter

JsonResponse: TypeAlias = dict


class ApiSettings(BaseSettings):
    username: str = Field()
    password: str = Field()
    url: str = Field()

    model_config = SettingsConfigDict(env_file=".env")


settings = ApiSettings()  # type: ignore reportCallIssue as the parameters are read via env file
api = ConfluenceApi(
    url=settings.url,
    username=settings.username,
    password=settings.password,
)


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
    def from_username(cls, username: str) -> "User":
        return cls.from_json(cast(JsonResponse, api.get_user_details_by_username(username)))

    @classmethod
    def from_userkey(cls, userkey: str) -> "User":
        return cls.from_json(cast(JsonResponse, api.get_user_details_by_userkey(userkey)))

    @classmethod
    def from_accountid(cls, accountid: int) -> "User":
        return cls.from_json(cast(JsonResponse, api.get_user_details_by_accountid(accountid)))


class Space(BaseModel):
    key: str
    name: str
    description: str

    @classmethod
    def from_json(cls, data: JsonResponse) -> "Space":
        return cls(
            key=data.get("key", ""),
            name=data.get("name", ""),
            description=data.get("description", {}).get("plain", {}).get("value", ""),
        )

    @classmethod
    def from_key(cls, space_key: str) -> "Space":
        return cls.from_json(cast(JsonResponse, api.get_space(space_key)))


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


class Page(BaseModel):
    id: int
    title: str
    space: Space
    body: str
    labels: list["Label"]

    @property
    def html(self) -> str:
        return f"<h1>{self.title}</h1>{self.body}"

    @property
    def markdown(self) -> str:
        return self.Converter(self).markdown

    @classmethod
    def from_json(cls, data: JsonResponse) -> "Page":
        return cls(
            id=data.get("id", 0),
            title=data.get("title", ""),
            space=Space.from_json(data.get("space", {})),
            body=data.get("body", {}).get("view", {}).get("value", ""),
            labels=[Label.from_json(label) for label in data.get("labels", {}).get("results", [])],
        )

    @classmethod
    def from_id(cls, page_id: int) -> "Page":
        return cls.from_json(
            cast(
                JsonResponse,
                api.get_page_by_id(page_id, expand="body.view,space,labels"),
            )
        )

    class Converter(TableConverter, MarkdownConverter):
        """Create a custom MarkdownConverter for Confluence HTML to Markdown conversion."""

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

        class Options(MarkdownConverter.DefaultOptions):
            bullets = "-"
            heading_style = ATX
            macros_to_ignore: Set[str] = frozenset(
                ["scroll-ignore", "qc-read-and-understood-signature-box"]
            )
            front_matter_indent = 2

        def __init__(self, page: "Page", **options) -> None:  # noqa: ANN003
            super().__init__(**options)
            self.page = page
            self.page_properties = {}

        @property
        def markdown(self) -> str:
            md_body = self.convert(self.page.html)
            return f"{self.front_matter}\n{md_body}\n"  # Add newline at end of file

        # @classmethod
        # def export_page(cls, page_id: int, file_path: str, **options) -> None:
        #     instance = cls(page_id, **options)
        #     md = instance.convert_page()
        #     with open(f"{file_path}/{instance.title}", "w") as file:
        #         file.write(md)

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
        def labels(self) -> list[str]:
            return [f"#{label.name}" for label in self.page.labels]

        def set_page_properties(self, **props: list[str] | str | None) -> None:
            for key, value in props.items():
                if value:
                    self.page_properties[key.lower().replace(" ", "-").replace("_", "-")] = value

        def convert_page_properties(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> None:
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
