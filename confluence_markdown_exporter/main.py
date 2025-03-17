import os
from pathlib import Path
from typing import Annotated

import typer
from tqdm import tqdm

from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.confluence import Space
from confluence_markdown_exporter.utils.measure_time import measure

DEBUG: bool = bool(os.getenv("DEBUG"))

app = typer.Typer()


# TODO build and publish to pypi
# TODO rename to confluence-markdown-exporter
# TODO Write readme


@app.command()
def page(
    page_id: Annotated[int, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    with measure(f"page {page_id}"):
        _page = Page.from_id(page_id)
        _page.export(output_path)


@app.command()
def page_with_descendants(
    page_id: Annotated[int, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    with measure(f"page_with_descendants {page_id}"):
        _page = Page.from_id(page_id)
        _page.export(output_path)

        for descendant_id in tqdm(_page.descendants):
            descendant_page = Page.from_id(descendant_id)
            descendant_page.export(output_path)


@app.command()
def space(
    space_key: Annotated[str, typer.Argument()],
    output_path: Annotated[Path, typer.Argument()] = Path("."),
) -> None:
    with measure(f"space {space_key}"):
        space = Space.from_key(space_key)
        page_with_descendants(space.homepage, output_path)


if __name__ == "__main__":
    app()
