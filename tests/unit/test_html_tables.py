"""Tests for `export.table_format = html`."""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.utils.table_converter import _render_cell_html
from tests.unit.test_confluence import _make_attachment
from tests.unit.test_confluence import _make_page

MODULE = "confluence_markdown_exporter.confluence"

MERGED = (
    '<table class="confluenceTable"><colgroup><col/><col/></colgroup><tbody>'
    '<tr><th class="confluenceTh">Env</th><th class="confluenceTh">Cluster</th></tr>'
    '<tr><td class="confluenceTd">Staging</td>'
    '<td class="confluenceTd" rowspan="2" data-highlight-colour="#fff">Cluster A</td></tr>'
    '<tr><td class="confluenceTd">Test</td></tr>'
    '<tr><td class="confluenceTd" colspan="2">Full width</td></tr>'
    "</tbody></table>"
)


@contextmanager
def _settings(table_format: str = "html", page_href: str = "relative") -> Iterator[None]:
    with (
        patch(f"{MODULE}.settings.export.table_format", table_format),
        patch(f"{MODULE}.settings.export.page_href", page_href),
        patch(f"{MODULE}.settings.export.attachment_href", page_href),
    ):
        yield


def _convert(html: str, page: Page | None = None, **settings: str) -> str:
    page = page or _make_page(body="", body_export="", attachments=[])
    with _settings(**settings):
        return Page.Converter(page).convert(html)


def _table(markdown: str) -> BeautifulSoup:
    """Parse the HTML table out of *markdown*, as a Markdown renderer would see it."""
    rendered = MarkdownIt("commonmark", {"html": True}).render(markdown)
    return BeautifulSoup(rendered, "html.parser")


class TestMergedCells:
    def test_merged_cells_keep_their_span_and_appear_once(self) -> None:
        result = _convert(MERGED)

        soup = _table(result)
        assert soup.find("td", rowspan="2").get_text() == "Cluster A"
        assert soup.find("td", colspan="2").get_text() == "Full width"
        assert result.count("Cluster A") == 1
        assert result.count("Full width") == 1
        assert [th.get_text() for th in soup.find_all("th")] == ["Env", "Cluster"]

    def test_confluence_attributes_and_column_groups_are_dropped(self) -> None:
        result = _convert(MERGED)

        assert "confluence" not in result
        assert "data-highlight-colour" not in result
        assert "colgroup" not in result

    def test_ordinary_tables_are_html_too(self) -> None:
        result = _convert("<table><tr><td>a</td><td>b</td></tr></table>")

        assert result.strip() == "<table>\n<tr><td>a</td><td>b</td></tr>\n</table>"

    def test_default_stays_a_markdown_table_with_repeated_content(self) -> None:
        result = _convert(MERGED, table_format="markdown")

        assert "<table" not in result
        assert result.count("Cluster A") == 2
        assert result.count("Full width") == 2


class TestCellContent:
    def test_rich_content_is_html(self) -> None:
        html = (
            '<table><tr><td rowspan="2">'
            '<span class="status-macro aui-lozenge aui-lozenge-success" '
            'data-macro-name="status">DONE</span>'
            "<ul><li><strong>bold</strong> a &lt; b &amp; c</li><li>two</li></ul>"
            "</td><td>x | y</td></tr><tr><td>z</td></tr></table>"
        )

        soup = _table(_convert(html))

        cell = soup.find("td", rowspan="2")
        assert cell.find("mark").get_text() == "DONE"
        assert [li.get_text() for li in cell.find_all("li")] == ["bold a < b & c", "two"]
        assert cell.find("strong").get_text() == "bold"
        assert soup.find_all("td")[1].get_text() == "x | y"

    def test_code_block_keeps_angle_brackets_and_blank_lines(self) -> None:
        html = (
            '<table><tr><td colspan="2">'
            '<div class="code panel" data-macro-name="code"><div class="codeContent">'
            '<pre class="syntaxhighlighter-pre" data-syntaxhighlighter-params="brush: py">'
            'if a &lt; b:\n\n    print("&lt;tag&gt;")</pre></div></div>'
            "</td></tr></table><p>after</p>"
        )

        result = _convert(html)

        assert "\n\n" not in result.strip().split("</table>")[0]
        soup = _table(result)
        code = soup.find("code", class_="language-py")
        assert code.get_text() == 'if a < b:\n\n    print("<tag>")\n'
        assert soup.find("p").get_text() == "after"

    def test_single_paragraph_is_unwrapped(self) -> None:
        assert _render_cell_html("plain *text*") == "plain <em>text</em>"
        assert _render_cell_html("one\n\ntwo") == "<p>one</p>\n<p>two</p>"

    def test_nested_table_keeps_its_own_merges(self) -> None:
        html = (
            '<table><tr><td colspan="2"><table>'
            '<tr><td rowspan="2">inner</td><td>i1</td></tr><tr><td>i2</td></tr>'
            "</table></td></tr></table>"
        )

        soup = _table(_convert(html))

        outer = soup.find("table")
        inner = outer.find("table")
        assert outer.find("td")["colspan"] == "2"
        assert inner.find("td", rowspan="2").get_text() == "inner"
        assert len(soup.find_all("table")) == 2

    def test_empty_table_is_dropped(self) -> None:
        assert _convert("<table><tr></tr></table>").strip() == ""


class TestLinks:
    @pytest.fixture
    def target(self) -> Page:
        target = _make_page(body="", body_export="", attachments=[])
        target.id = 555
        target.title = "Target"
        return target

    @pytest.mark.parametrize("page_href", ["relative", "wiki"])
    def test_page_link_in_cell_is_an_html_link(self, target: Page, page_href: str) -> None:
        html = (
            '<table><tr><td><a href="/pages/viewpage.action?pageId=555" '
            'data-linked-resource-id="555" data-linked-resource-type="page">Target</a>'
            "</td></tr></table>"
        )
        with patch(f"{MODULE}._link_target", return_value=target):
            result = _convert(html, page_href=page_href)

        assert "[[" not in result
        assert _table(result).find("a")["href"] == "Target.md"

    def test_wiki_links_outside_tables_are_unchanged(self, target: Page) -> None:
        link = (
            '<a href="/pages/viewpage.action?pageId=555" '
            'data-linked-resource-id="555" data-linked-resource-type="page">Target</a>'
        )
        html = f"<table><tr><td>{link}</td></tr></table><p>{link}</p>"
        with patch(f"{MODULE}._link_target", return_value=target):
            result = _convert(html, page_href="wiki")

        assert result.rstrip().endswith("[[Target]]")

    @pytest.mark.parametrize("attachment_href", ["relative", "wiki"])
    def test_image_in_cell_points_to_exported_attachment(self, attachment_href: str) -> None:
        attachment = _make_attachment("123", "file-id", title="image.png", media_type="image/png")
        page = _make_page(body="", body_export="", attachments=[attachment])
        html = (
            '<table><tr><td rowspan="2"><img data-linked-resource-id="123" '
            'src="/download/attachments/1/image.png"/></td></tr></table>'
        )
        with (
            patch(
                f"{MODULE}.settings.export.attachment_path",
                "attachments/{attachment_id}{attachment_extension}",
            ),
            patch(f"{MODULE}.settings.export.embed_images", new=False),
            patch(f"{MODULE}.settings.export.image_captions", new=False),
        ):
            result = _convert(html, page=page, page_href=attachment_href)
            markdown = _convert(html, page=page, table_format="markdown")

        assert "![[" not in result
        # Same relative path as the Markdown table would use
        assert f"]({_table(result).find('img')['src']})" in markdown
