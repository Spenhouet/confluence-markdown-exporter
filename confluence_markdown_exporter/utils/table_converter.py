import html
import re
from typing import cast

from bs4 import BeautifulSoup
from bs4 import Tag
from markdown_it import MarkdownIt
from markdownify import MarkdownConverter
from tabulate import tabulate

from confluence_markdown_exporter.utils.app_data_store import get_settings

_MAX_TABLE_LINE_LEN = 120

_LEADING_BR_OR_WS = re.compile(r"^(?:\s|<br\s*/?>)+")
_TRAILING_BR_OR_WS = re.compile(r"(?:\s|<br\s*/?>)+$")
_PRE_BLOCK = re.compile(r"<pre\b.*?</pre>", re.DOTALL)
_SINGLE_PARAGRAPH = re.compile(r"<p>((?:(?!</?p>).)*)</p>", re.DOTALL)

# Renders the Markdown of a cell back to HTML for `export.table_format = html`. Raw HTML
# the converter emits (e.g. <mark>, <details>) passes through unchanged.
_CELL_RENDERER = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])


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


def _table_rows(el: Tag) -> list[Tag]:
    """Return the rows of *el*, not of tables nested in it."""
    row_tags: list[Tag] = []
    for child in el.find_all(["thead", "tbody", "tfoot", "tr"], recursive=False):
        if child.name == "tr":
            row_tags.append(cast("Tag", child))
        else:
            row_tags.extend(cast("list[Tag]", child.find_all("tr", recursive=False)))
    return row_tags


def _render_cell_html(markdown: str) -> str:
    """Render the Markdown of one cell as HTML that stays inside an HTML block.

    A blank line ends a CommonMark HTML block, so newlines in preformatted text become
    character references and other blank lines are dropped. A cell that is a single
    paragraph loses the <p> wrapper.
    """
    rendered = _CELL_RENDERER.render(markdown).strip()
    if (match := _SINGLE_PARAGRAPH.fullmatch(rendered)) is not None:
        rendered = match.group(1)
    rendered = _PRE_BLOCK.sub(lambda m: m.group(0).replace("\n", "&#10;"), rendered)
    return re.sub(r"\n\s*\n", "\n", rendered)


def _span_attrs(cell: Tag) -> str:
    """Return the rowspan and colspan attributes of *cell* that merge cells."""
    attrs = ""
    for name in ("rowspan", "colspan"):
        if cell.has_attr(name) and _get_int_attr(cell, name) != 1:
            attrs += f' {name}="{html.escape(str(_get_int_attr(cell, name)))}"'
    return attrs


def normalize_table_cell_text(text: str) -> str:
    text = text.replace("|", "\\|").replace("\n", "<br/>")
    text = _LEADING_BR_OR_WS.sub("", text)
    return _TRAILING_BR_OR_WS.sub("", text)


class TableConverter(MarkdownConverter):
    """Custom MarkdownConverter for converting HTML tables to markdown tables."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._table_column_width = kwargs.pop("table_column_width", None)
        self._table_format = kwargs.pop("table_format", None)
        # Depth of HTML table cells being converted. Wiki links don't work inside HTML,
        # so links fall back to relative paths while it is above zero.
        self._html_cell_depth = 0
        super().__init__(*args, **kwargs)

    def _resolved_table_format(self) -> str:
        if self._table_format is not None:
            return str(self._table_format)
        try:
            return get_settings().export.table_format
        except (AttributeError, RuntimeError):
            return "markdown"

    def _convert_html_cell(self, cell: Tag, parent_tags: set[str]) -> str:
        """Convert the content of *cell* as ordinary page content and render it as HTML.

        The cell is converted as a block, not as a pipe table cell, so lists and code
        blocks keep their structure. The cell stays in the tree (renamed for the duration)
        because some converters look at the element's position in the page.
        """
        name = cell.name
        cell.name = "div"
        self._html_cell_depth += 1
        try:
            markdown = self.process_tag(cell, parent_tags=set(parent_tags))
        finally:
            self._html_cell_depth -= 1
            cell.name = name
        return _render_cell_html(markdown)

    def convert_html_table(self, el: Tag, parent_tags: set[str]) -> str:
        """Convert *el* to an HTML table whose cells hold HTML.

        Merged cells keep their rowspan and colspan, so each cell's content appears once.
        Confluence classes and other attributes are dropped. Tables nested in a cell are
        converted the same way through the cell content.
        """
        sections: list[tuple[str | None, list[Tag]]] = []
        for child in el.find_all(["thead", "tbody", "tfoot", "tr"], recursive=False):
            if child.name == "tr":
                if sections and sections[-1][0] is None:
                    sections[-1][1].append(cast("Tag", child))
                else:
                    sections.append((None, [cast("Tag", child)]))
            else:
                sections.append(
                    (child.name, cast("list[Tag]", child.find_all("tr", recursive=False)))
                )

        if not any(tr.find(["td", "th"], recursive=False) for _, rows in sections for tr in rows):
            return ""

        lines: list[str] = []
        for section, rows in sections:
            if section:
                lines.append(f"<{section}>")
            for tr in rows:
                cells = cast("list[Tag]", tr.find_all(["td", "th"], recursive=False))
                rendered = [
                    f"<{cell.name}{_span_attrs(cell)}>"
                    f"{self._convert_html_cell(cell, parent_tags)}</{cell.name}>"
                    for cell in cells
                ]
                lines.append("<tr>" + "".join(rendered) + "</tr>")
            if section:
                lines.append(f"</{section}>")
        return "\n\n<table>\n" + "\n".join(lines) + "\n</table>\n\n"

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

        if self._resolved_table_format() == "html":
            tags = {t for t in self._normalize_parent_tags(parent_tags) if t != "_inline"}
            return self.convert_html_table(cast("Tag", el), tags)

        row_tags = _table_rows(cast("Tag", el))
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
