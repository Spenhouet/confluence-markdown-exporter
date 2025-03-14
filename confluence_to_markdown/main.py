from pathlib import Path
from typing import Annotated

import typer

from confluence_to_markdown.confluence import Page

app = typer.Typer()


# TODO build and publish to pypi


@app.command()
def page(
    page_id: Annotated[int, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    page = Page.from_id(page_id)

    with open(output_path / f"{page.title}.html", "w") as file:
        file.write(page.html)

    with open(output_path / f"{page.title}.md", "w") as file:
        file.write(page.markdown)


@app.command()
def space(
    space_key: Annotated[str, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    pass
    # api_session = get_session()
    # space = api_session.get_space(space_key)

    # if not space:
    #     msg = f"Space {space_key} does not exist."
    #     raise ValueError(msg)

    # print(space)


if __name__ == "__main__":
    app()
