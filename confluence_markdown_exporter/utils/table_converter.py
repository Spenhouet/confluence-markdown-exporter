import re
from typing import cast

from bs4 import BeautifulSoup
from bs4 import Tag
from markdownify import MarkdownConverter
from tabulate import tabulate

from confluence_markdown_exporter.utils.app_data_store import get_settings

_MAX_TABLE_LINE_LEN = 120

_LEADING_BR_OR_WS = re.compile(r"^(?:\s|<br\s*/?>)+")
_TRAILING_BR_OR_WS = re.compile(r"(?:\s|<br\s*/?>)+$")


def to_markdown_table(
    rows: list[list[str]],
    headers: list[str],
    *,
    escape_cells: bool = False,
) -> str:
    """Format a list of rows and headers as a compact GFM pipe table."""
    if not headers and not rows:
        return ""
    col_count = len(headers) if headers else (len(rows[0]) if rows else 0)
    if col_count == 0:
        return ""

    # Normalize headers to match col_count
    actual_headers = list(headers) if headers else [""] * col_count
    if len(actual_headers) < col_count:
        actual_headers.extend([""] * (col_count - len(actual_headers)))
    elif len(actual_headers) > col_count:
        actual_headers = actual_headers[:col_count]

    normalized_headers = (
        [normalize_table_cell_text(str(cell)) for cell in actual_headers]
        if escape_cells
        else [str(cell) for cell in actual_headers]
    )
    lines = []
    lines.append("| " + " | ".join(normalized_headers) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in rows:
        actual_row = [str(cell) for cell in row]
        if escape_cells:
            actual_row = [normalize_table_cell_text(cell) for cell in actual_row]
        if len(actual_row) < col_count:
            actual_row.extend([""] * (col_count - len(actual_row)))
        elif len(actual_row) > col_count:
            actual_row = actual_row[:col_count]
        lines.append("| " + " | ".join(actual_row) + " |")
    return "\n".join(lines)


def _get_int_attr(cell: Tag, attr: str, default: str = "1") -> int:
    val = cell.get(attr, default)
    if isinstance(val, list):
        val = val[0] if val else default
    try:
        return int(str(val))
    except (ValueError, TypeError):
        return int(default)


def pad(rows: list[list[Tag]]) -> list[list[Tag]]:
    """Expand rowspan and colspan into a rectangular grid of cells.

    Markdown tables cannot merge cells, so in a well-formed table every grid position a
    merged cell covers references the merge origin itself and therefore renders the same
    value. The same Tag object is reused on purpose, so callers can convert each origin
    only once.

    A ragged row, one with too few cells to reach a position reserved by an earlier
    rowspan, still drops that reservation, because the trailing sweep only fills the
    positions directly following the last cell of the row. Such markup is malformed and
    renders the same way it did before merged content was carried over.
    """
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
            # Every cell occupies at least one grid position: colspan="0" (valid in
            # HTML4, dropped in HTML5) or a negative value would otherwise erase it.
            # rowspan="0" validly means "to the end of the row group"; treating it as a
            # single row is a pragmatic simplification, not a spec-accurate reading.
            rs = max(_get_int_attr(cell, "rowspan", "1"), 1)
            cs = max(_get_int_attr(cell, "colspan", "1"), 1)
            # Repeat the cell across the columns it spans in this row.
            cur.extend([cell] * cs)
            # Reserve the positions it spans in the following rows.
            for i in range(1, rs):
                for j in range(cs):
                    occ[(r + i, c + j)] = cell
            c += cs
        while (r, c) in occ:
            cur.append(occ.pop((r, c)))
            c += 1
        padded.append(cur)
    return padded


def normalize_table_cell_text(text: str) -> str:
    text = text.replace("|", "\\|").replace("\n", "<br/>")
    text = _LEADING_BR_OR_WS.sub("", text)
    return _TRAILING_BR_OR_WS.sub("", text)


class TableConverter(MarkdownConverter):
    """Custom MarkdownConverter for converting HTML tables to markdown tables."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._table_column_width = kwargs.pop("table_column_width", None)
        super().__init__(*args, **kwargs)

    def _format_table(
        self,
        converted: list[list[str]],
        *,
        has_header: bool,
        is_nested: bool,
        mode: str,
    ) -> str:
        rows = converted[1:] if has_header else converted
        headers = converted[0] if has_header else [""] * len(converted[0])

        if mode == "compact":
            return to_markdown_table(rows, headers=headers)

        if mode == "aligned":
            return tabulate(rows, headers=headers, tablefmt="pipe")

        # mode == "mixed"
        if is_nested:
            return to_markdown_table(rows, headers=headers)

        aligned = tabulate(rows, headers=headers, tablefmt="pipe")
        max_line_len = max(len(line) for line in aligned.splitlines()) if aligned else 0
        if max_line_len > _MAX_TABLE_LINE_LEN:
            return to_markdown_table(rows, headers=headers)

        return aligned

    def convert_table(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        if "table" in parent_tags:
            return str(el)

        row_tags: list[Tag] = []
        for child in el.find_all(["thead", "tbody", "tfoot", "tr"], recursive=False):
            if child.name == "tr":
                row_tags.append(cast("Tag", child))
            else:
                row_tags.extend(cast("list[Tag]", child.find_all("tr", recursive=False)))
        rows = [
            cast("list[Tag]", tr.find_all(["td", "th"], recursive=False)) for tr in row_tags if tr
        ]

        # Check if rows is empty OR if all rows are empty lists (e.g., <tr></tr>)
        if not rows or not any(rows):
            return ""

        padded_rows = pad(rows)
        # A merged cell occupies several grid positions but must be converted only
        # once: conversion is stateful (e.g. the PlantUML macro index advances per
        # converted macro), so repeated positions reuse the first conversion.
        # Keyed on id() and not on the Tag itself: bs4 gives Tag a structural __eq__
        # and __hash__, so two distinct cells with identical markup would collapse
        # into one cache entry and wrongly share a conversion.
        cell_cache: dict[int, str] = {}
        converted: list[list[str]] = []
        for row in padded_rows:
            converted_row: list[str] = []
            for cell in row:
                if id(cell) not in cell_cache:
                    cell_cache[id(cell)] = self.process_tag(cell, parent_tags={"table"})
                converted_row.append(cell_cache[id(cell)])
            converted.append(converted_row)

        has_header = all(cell.name == "th" for cell in rows[0])

        mode = self._table_column_width
        if mode is None:
            try:
                mode = get_settings().export.table_column_width
            except (AttributeError, RuntimeError):
                mode = "mixed"

        is_nested = any(cell.find("table") is not None for row in padded_rows for cell in row)
        return self._format_table(
            converted,
            has_header=has_header,
            is_nested=is_nested,
            mode=mode,
        )

    def convert_th(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <th> tag."""
        return normalize_table_cell_text(text)

    def convert_tr(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <tr> tag."""
        return text

    def convert_td(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <td> tag."""
        return normalize_table_cell_text(text)

    def convert_thead(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <thead> tag."""
        return text

    def convert_tbody(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
        """This method is empty because we want a No-Op for the <tbody> tag."""
        return text

    ParentTags = list[str] | set[str]

    @staticmethod
    def _normalize_parent_tags(
        parent_tags: "TableConverter.ParentTags | bool",
    ) -> "TableConverter.ParentTags":
        # markdownify 1.x passes set[str]; older versions passed bool (convert_as_inline)
        return parent_tags if isinstance(parent_tags, list | set) else set()

    def convert_ol(
        self, el: BeautifulSoup, text: str, parent_tags: "TableConverter.ParentTags | bool"
    ) -> str:
        tags = self._normalize_parent_tags(parent_tags)
        if "td" in tags:
            lines = text.splitlines()
            if not lines:
                return ""
            start = int(el.get("start") or 1)
            numbered = [
                f"{start + i}. {item}".rstrip() if item.strip() else str(start + i)
                for i, item in enumerate(lines)
            ]
            return "<br>".join(n for n in numbered if n)
        return super().convert_ol(el, text, tags)

    def convert_li(
        self, el: BeautifulSoup, text: str, parent_tags: "TableConverter.ParentTags | bool"
    ) -> str:
        tags = self._normalize_parent_tags(parent_tags)
        if "td" in tags:
            return text.strip().removesuffix("<br/>") + "\n"
        return MarkdownConverter.convert_li(self, el, text, tags)  # type: ignore[attr-defined]

    def convert_ul(
        self, el: BeautifulSoup, text: str, parent_tags: "TableConverter.ParentTags | bool"
    ) -> str:
        tags = self._normalize_parent_tags(parent_tags)
        if "td" in tags:
            items = [item for item in text.splitlines() if item.strip()]
            if not items:
                return ""
            if len(items) == 1:
                return items[0]
            return "- " + "<br>- ".join(items)
        return super().convert_ul(el, text, tags)

    def convert_p(
        self, el: BeautifulSoup, text: str, parent_tags: "TableConverter.ParentTags | bool"
    ) -> str:
        tags = self._normalize_parent_tags(parent_tags)
        md = super().convert_p(el, text, tags)
        if "td" in tags:
            md = md.replace("\n", "") + "<br/>"
        return md
