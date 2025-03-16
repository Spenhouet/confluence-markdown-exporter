import os
from pathlib import Path
from typing import Annotated

import typer

from confluence_to_markdown.confluence import Page
from confluence_to_markdown.confluence import Space
from confluence_to_markdown.utils.measure_time import measure_time

DEBUG: bool = bool(os.getenv("DEBUG"))

app = typer.Typer()


# TODO build and publish to pypi


@measure_time
def export_page(page_id: int, output_path: Path) -> Page:
    _page = Page.from_id(page_id)
    _page.export(output_path)
    return _page


@app.command()
def page(
    page_id: Annotated[int, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    export_page(page_id, output_path)


@app.command()
def page_with_descendants(
    page_id: Annotated[int, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    _page = export_page(page_id, output_path)

    for descendant_id in _page.descendants:
        page(descendant_id, output_path)


@app.command()
def space(
    space_key: Annotated[str, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    space = Space.from_key(space_key)
    page_with_descendants(space.homepage, output_path)


if __name__ == "__main__":
    app()
