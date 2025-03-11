import re
from typing import cast

import typer
import yaml
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from confluence_to_markdown.session import get_session

app = typer.Typer()

# Confluence API documentation
# https://developer.atlassian.com/cloud/confluence/rest/v2/intro


# TODO ensure images work
# TODO ensure drawio diagrams work
# TODO store whole space
# TODO make output path configurable


@app.command()
def page(page_id: int) -> None:
    api_session = get_session()
    page_data = cast(
        dict, api_session.get_page_by_id(page_id=page_id, expand="body.view,body.storage,space")
    )

    if not page_data:
        msg = f"PageID {page_id} does not exist."
        raise ValueError(msg)

    page_title = page_data.get("title", "Unknown")
    space = page_data.get("space", {})
    space_key = space.get("key")
    space_name = space.get("name")
    body_view = page_data.get("body", {}).get("view", {}).get("value")

    # Get labels
    label_response = cast(dict, api_session.get_page_labels(page_id))
    labels = (
        [f"#{label['name']}" for label in label_response["results"]]
        if label_response and label_response["results"]
        else ""
    )

    # Remove divs with data-macro-name="scroll-ignore"
    soup = BeautifulSoup(body_view, "html.parser")
    for div in soup.find_all("div", {"data-macro-name": "scroll-ignore"}):
        div.decompose()
    body_view = str(soup)

    def code_language_callback(el: BeautifulSoup) -> str | None:
        if not el.has_attr("data-syntaxhighlighter-params"):
            return None

        match = re.search(r"brush:\s*([^;]+)", str(el["data-syntaxhighlighter-params"]))
        return match.group(1) if match else None

    markdown_body = md(
        body_view, heading_style="ATX", code_language_callback=code_language_callback
    )

    header = {
        "space": space_key,
        "space_name": space_name,
        "tags": labels,
    }

    markdown = f"""\
---
{yaml.dump(header, indent=2, sort_keys=False).strip()}
---

# {page_title}

{markdown_body}
"""

    with open(f"scratch/{page_id}.md", "w") as file:
        file.write(markdown)


@app.command()
def space(space_key: str) -> None:
    api_session = get_session()
    space = api_session.get_space(space_key)

    if not space:
        msg = f"Space {space_key} does not exist."
        raise ValueError(msg)

    print(space)


if __name__ == "__main__":
    app()
