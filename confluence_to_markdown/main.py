import typer

from confluence_to_markdown.confluence import Page

app = typer.Typer()


# TODO make output path configurable
# TODO build and publish to pypi


@app.command()
def page(page_id: int) -> None:
    page = Page.from_id(page_id)

    with open(f"scratch/{page.title}.html", "w") as file:
        file.write(page.html)

    with open(f"scratch/{page.title}.md", "w") as file:
        file.write(page.markdown)


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
