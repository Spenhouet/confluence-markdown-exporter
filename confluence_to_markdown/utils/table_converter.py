from typing import cast

from bs4 import BeautifulSoup
from bs4 import Tag
from markdownify import MarkdownConverter
from tabulate import tabulate


def pad(rows: list[list[Tag]]) -> list[list[Tag]]:
    padded: list[list[Tag]] = []
    occ: dict[tuple[int, int], Tag] = {}
    for r, row in enumerate(rows):
        if not row:
            continue
        cur: list[Tag] = []
        c = 0
        for cell in row:
            while (r, c) in occ:
                cur.append(occ.pop((r, c)))
                c += 1
            rs = int(cell.get("rowspan", 1))  # type: ignore -
            cs = int(cell.get("colspan", 1))  # type: ignore -
            cur.append(cell)
            # Append extra cells for colspan
            for _ in range(1, cs):
                cur.append(make_empty_cell())
            # Mark future cells for rowspan and colspan
            for i in range(rs):
                for j in range(cs):
                    if i or j:
                        occ[(r + i, c + j)] = make_empty_cell()
            c += cs
        while (r, c) in occ:
            cur.append(occ.pop((r, c)))
            c += 1
        padded.append(cur)
    return padded


def make_empty_cell() -> Tag:
    """Return an empty <td> Tag."""
    return Tag(name="td")


class TableConverter(MarkdownConverter):
    def convert_table(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        rows = [
            cast(list[Tag], tr.find_all(["td", "th"])) for tr in cast(list[Tag], el.find_all("tr"))
        ]

        if not rows:
            return ""

        padded_rows = pad(rows)
        converted = [[self.convert(str(cell)) for cell in row] for row in padded_rows]

        has_header = all(cell.name == "th" for cell in rows[0])
        if has_header:
            return tabulate(converted[1:], headers=converted[0], tablefmt="pipe")

        return tabulate(converted, headers=[""] * len(converted[0]), tablefmt="pipe")

    def convert_th(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <th> tag."""
        # return the html as is
        return text

    def convert_tr(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <tr> tag."""
        return text

    def convert_td(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <td> tag."""
        return text.replace("\n", "<br/>").removesuffix("<br/>").removeprefix("<br/>")

    def convert_thead(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <thead> tag."""
        return text

    def convert_tbody(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <tbody> tag."""
        return text

    def convert_ol(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        if "td" in parent_tags:
            return str(el)
        return super().convert_ol(el, text, parent_tags)

    def convert_ul(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        if "td" in parent_tags:
            return str(el)
            # return super().convert_ul(el, text, parent_tags).strip().replace("\n", "<br/>")
        return super().convert_ul(el, text, parent_tags)

    def convert_p(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        md = super().convert_p(el, text, parent_tags)
        if "td" in parent_tags:
            md = md.replace("\n", "") + "<br/>"
        return md
