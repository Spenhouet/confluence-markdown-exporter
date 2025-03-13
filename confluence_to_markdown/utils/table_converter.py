from typing import cast

from bs4 import BeautifulSoup
from bs4 import Tag
from markdownify import MarkdownConverter
from tabulate import tabulate


class TableConverter(MarkdownConverter):
    def convert_table(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        rows = [
            cast(list[Tag], tr.find_all(["td", "th"])) for tr in cast(list[Tag], el.find_all("tr"))
        ]

        if not rows:
            return ""

        has_header = all(cell.name == "th" for cell in rows[0])
        rows = [[self.convert(str(cell)) for cell in row] for row in rows]

        if has_header:
            return tabulate(rows[1:], headers=rows[0], tablefmt="pipe")

        return tabulate(rows, headers=[""] * len(rows[0]), tablefmt="pipe")

    def convert_th(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <th> tag."""
        # return the html as is
        return text

    def convert_tr(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <tr> tag."""
        return text

    def convert_td(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <td> tag."""
        return text

    def convert_thead(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <thead> tag."""
        return text

    def convert_tbody(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <tbody> tag."""
        return text
