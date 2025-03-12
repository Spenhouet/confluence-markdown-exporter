from typing import cast

import typer
import yaml

from confluence_to_markdown.converter import ConfluencePageConverter

app = typer.Typer()

# Confluence API documentation
# https://developer.atlassian.com/cloud/confluence/rest/v2/intro


# TODO make output path configurable


@app.command()
def page(page_id: int) -> None:
    # space = page_data.get("space", {})
    # space_key = space.get("key")
    # space_name = space.get("name")

    # Get labels
    # label_response = cast(dict, api_session.get_page_labels(page_id))
    # labels = (
    #     [f"#{label['name']}" for label in label_response["results"]]
    #     if label_response and label_response["results"]
    #     else ""
    # )

    converter = ConfluencePageConverter()

    # TODO remove
    html = converter.html(page_id)
    with open(f"scratch/{page_id}.html", "w") as file:
        file.write(html)

    markdown = converter.convert(page_id)

    # header = {
    #     "space": space_key,
    #     "space_name": space_name,
    #     "tags": labels,
    # }

    #     markdown = f"""\
    # ---
    # {yaml.dump(header, indent=2, sort_keys=False).strip()}
    # ---

    # # {page_title}

    # {markdown_body}
    # """

    with open(f"scratch/{page_id}.md", "w") as file:
        file.write(markdown)


@app.command()
def space(space_key: str) -> None:
    pass
    # api_session = get_session()
    # space = api_session.get_space(space_key)

    # if not space:
    #     msg = f"Space {space_key} does not exist."
    #     raise ValueError(msg)

    # print(space)


if __name__ == "__main__":
    app()
