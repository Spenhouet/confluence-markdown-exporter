import re
from collections.abc import Set
from typing import cast

from atlassian import Confluence
from bs4 import BeautifulSoup
from markdownify import ATX
from markdownify import MarkdownConverter
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class ConfluenceApiSettings(BaseSettings):
    username: str = Field()
    password: str = Field()
    url: str = Field()

    model_config = SettingsConfigDict(env_file=".env")


# TODO ensure images work
# TODO ensure drawio diagrams work
# TODO ensure other attachments work like PDF or ZIP
# TODO store whole space
# TODO resolve export internal/relative links
# TODO format markdown so that table lines aline
# TODO alternative for info boxes? https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts
# TODO ensure emojis work https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#using-emojis
# TODO ensure task lists work
# TODO use @ for mentions
# TODO add page properties to front matter
# TODO add labels to front matter

# TODO advanced: read version by version and commit in git using change comment and user info


class ConfluencePageConverter(MarkdownConverter):
    """Create a custom MarkdownConverter for Confluence HTML to Markdown conversion."""

    class Options(MarkdownConverter.DefaultOptions):
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

    def html(self, page_id: int) -> str:
        page_data = cast(dict, self.api.get_page_by_id(page_id=page_id, expand="body.view,space"))

        if not page_data:
            msg = f"PageID {page_id} does not exist."
            raise ValueError(msg)

        title = page_data.get("title", "Unknown")
        body_view = page_data.get("body", {}).get("view", {}).get("value")

        return f"<h1>{title}</h1>{body_view}"

    def convert(self, page_id: int) -> str:
        html = self.html(page_id)
        return super().convert(html) + "\n"  # Add newline at end of file

    def convert_div(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        # Handle Confluence macros
        if el.has_attr("data-macro-name"):
            if el["data-macro-name"] in self.options["macros_to_ignore"]:
                return ""

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

    def convert_img(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        # TODO download attachment via API?
        return super().convert_img(el, text, parent_tags)
