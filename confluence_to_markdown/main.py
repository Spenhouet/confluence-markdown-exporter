import typer

from confluence_to_markdown.converter import ConfluencePageConverter

app = typer.Typer()

# Confluence API documentation
# https://developer.atlassian.com/cloud/confluence/rest/v2/intro


# TODO make output path configurable
# TODO build and publish to pypi


@app.command()
def page(page_id: int) -> None:
    converter = ConfluencePageConverter()

    # TODO remove
    html = converter.html(page_id)
    with open(f"scratch/{page_id}.html", "w") as file:
        file.write(html)

    markdown = converter.convert_page(page_id)

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
