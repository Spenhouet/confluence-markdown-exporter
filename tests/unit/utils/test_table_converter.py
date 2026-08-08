"""Tests for the table_converter module."""

from typing import Any

from bs4 import BeautifulSoup

from confluence_markdown_exporter.utils.table_converter import TableConverter


class _CountingTableConverter(TableConverter):
    """TableConverter that records the cells ``convert_table`` converts."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.converted_cell_ids: list[int] = []

    def process_tag(self, node: Any, *args: Any, **kwargs: Any) -> str:  # noqa: ANN401
        parent_tags = kwargs.get("parent_tags", args[0] if args else None)
        if getattr(node, "name", None) in {"td", "th"} and parent_tags == {"table"}:
            self.converted_cell_ids.append(id(node))
        return super().process_tag(node, *args, **kwargs)  # type: ignore[no-any-return]


class TestTableConverter:
    """Test TableConverter class."""

    def test_pipe_character_in_cell(self) -> None:
        """Test that pipe characters are escaped in table cells."""
        html = """
        <table>
            <tr>
                <th>Column 1</th>
                <th>Column 2</th>
            </tr>
            <tr>
                <td>Value with | pipe</td>
                <td>Normal value</td>
            </tr>
        </table>
        """
        BeautifulSoup(html, "html.parser")
        converter = TableConverter()
        result = converter.convert(html)

        # The pipe character should be escaped
        assert "\\|" in result
        # The result should still have proper table structure
        assert "Column 1" in result
        assert "Column 2" in result
        assert "Value with" in result
        assert "pipe" in result

    def test_multiple_pipes_in_cell(self) -> None:
        """Test that multiple pipe characters are escaped in table cells."""
        html = """
        <table>
            <tr>
                <th>Header</th>
            </tr>
            <tr>
                <td>Value | with | multiple | pipes</td>
            </tr>
        </table>
        """
        BeautifulSoup(html, "html.parser")
        converter = TableConverter()
        result = converter.convert(html)

        # All pipe characters should be escaped (3 pipes in the content)
        assert result.count("\\|") == 3
        assert "Value" in result
        assert "with" in result
        assert "multiple" in result
        assert "pipes" in result

    def test_pipe_character_in_header(self) -> None:
        """Test that pipe characters are escaped in table header cells."""
        html = """
        <table>
            <tr>
                <th>Column | 1</th>
                <th>Column | 2</th>
            </tr>
            <tr>
                <td>Value 1</td>
                <td>Value 2</td>
            </tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)

        # The pipe characters in headers should be escaped (2 pipes)
        assert result.count("\\|") == 2
        assert "Column" in result
        assert "Value 1" in result
        assert "Value 2" in result

    def test_table_without_pipes(self) -> None:
        """Test normal table conversion without pipe characters."""
        html = """
        <table>
            <tr>
                <th>Name</th>
                <th>Age</th>
            </tr>
            <tr>
                <td>John</td>
                <td>30</td>
            </tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)

        assert "Name" in result
        assert "Age" in result
        assert "John" in result
        assert "30" in result
        # Should have proper table structure
        assert "|" in result
        assert "---" in result
        # Should have no escaped pipes
        assert "\\|" not in result

    def test_nested_table_visual_fidelity_preserves_inner_table_html(self) -> None:
        """TableConverter always preserves nested table HTML instead of flattening rows."""
        html = """
        <table>
            <tr><td>Outer</td></tr>
            <tr>
                <td>
                    <p>Inner:</p>
                    <table>
                        <tr><td>x</td><td>y</td></tr>
                        <tr><td>1</td><td>2</td></tr>
                    </table>
                </td>
            </tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)

        assert "Inner:" in result
        assert "<table>" in result
        assert "<td>x</td>" in result
        assert not any(line.strip().startswith("| x") for line in result.splitlines())
        assert not any(line.strip().startswith("| 1") for line in result.splitlines())

    def test_convert_p_bool_parent_tags_no_crash(self) -> None:
        """convert_p must not crash when markdownify passes bool instead of set."""
        converter = TableConverter()
        el = BeautifulSoup("<p>text.</p>", "html.parser").p
        assert el is not None
        result = converter.convert_p(el, "text.", parent_tags=False)  # type: ignore[arg-type]
        assert "text." in result

    def test_convert_ol_bool_parent_tags_no_crash(self) -> None:
        """convert_ol must not crash when markdownify passes bool instead of set."""
        converter = TableConverter()
        el = BeautifulSoup("<ol><li>item</li></ol>", "html.parser").ol
        assert el is not None
        result = converter.convert_ol(el, "item", parent_tags=False)  # type: ignore[arg-type]
        assert "item" in result

    def test_convert_ul_bool_parent_tags_no_crash(self) -> None:
        """convert_ul must not crash when markdownify passes bool instead of set."""
        converter = TableConverter()
        el = BeautifulSoup("<ul><li>item</li></ul>", "html.parser").ul
        assert el is not None
        result = converter.convert_ul(el, "item", parent_tags=False)  # type: ignore[arg-type]
        assert "item" in result

    def test_single_item_ul_in_cell_strips_list_symbol(self) -> None:
        """Single-item ul in a table cell should not render a leading '- '."""
        html = """
        <table>
            <tr>
                <th>Header</th>
            </tr>
            <tr>
                <td><ul><li>Only item</li></ul></td>
            </tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)

        assert "Only item" in result
        assert "- Only item" not in result

    def test_multi_item_ul_in_cell_keeps_list_symbols(self) -> None:
        """Multi-item ul in a table cell should still render with '- ' prefixes."""
        html = """
        <table>
            <tr>
                <th>Header</th>
            </tr>
            <tr>
                <td><ul><li>First</li><li>Second</li></ul></td>
            </tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)

        assert "- First" in result
        assert "- Second" in result

    def test_ol_in_cell_with_empty_paragraph_shows_number(self) -> None:
        """Ol with empty <p> in a table cell should show the CSS-implicit number."""
        html = """
        <table>
            <tr><th>Header</th></tr>
            <tr><td><ol start="1"><li><p></p></li></ol></td></tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)
        assert "1" in result

    def test_ol_in_cell_with_empty_paragraph_respects_start(self) -> None:
        """Ol with start attribute and empty <p> should use the start number."""
        html = """
        <table>
            <tr><th>Header</th></tr>
            <tr><td><ol start="3"><li><p></p></li></ol></td></tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)
        assert "3" in result

    def test_ol_in_cell_with_content(self) -> None:
        """Ol with text content in a table cell should number each item."""
        html = """
        <table>
            <tr><th>Header</th></tr>
            <tr><td><ol start="1"><li><p>alpha</p></li><li><p>beta</p></li></ol></td></tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)
        assert "1. alpha" in result
        assert "2. beta" in result
        assert "<br>" in result

    def test_ul_in_cell_with_paragraph_items(self) -> None:
        """Ul with <p>-wrapped items in a table cell should use '- ' bullet syntax."""
        html = """
        <table>
            <tr><th>Header</th></tr>
            <tr><td><ul><li><p>First</p></li><li><p>Second</p></li><li><p>Third</p></li></ul></td></tr>
        </table>
        """
        converter = TableConverter()
        result = converter.convert(html)
        assert "- First" in result
        assert "<br>- Second" in result
        assert "<br>- Third" in result

    def test_td_detection_still_works_with_set_parent_tags(self) -> None:
        """set-based parent_tags (markdownify 1.x) must still trigger td-specific behaviour."""
        converter = TableConverter()
        el = BeautifulSoup("<p>text.</p>", "html.parser").p
        assert el is not None
        result = converter.convert_p(el, "text.", {"td", "_inline"})  # type: ignore[arg-type]
        assert result.endswith("<br/>")

    def test_table_column_width_aligned(self) -> None:
        """Test that aligned mode always uses tabulate."""
        html = "<table><tr><th>H1</th><th>H2</th></tr><tr><td>A</td><td>B</td></tr></table>"
        # Since it's aligned, the column should be aligned using spaces via tabulate.
        converter = TableConverter(table_column_width="aligned")
        result = converter.convert(html)
        assert "  " in result
        assert "| H1   | H2   |" in result

    def test_table_column_width_compact(self) -> None:
        """Test that compact mode never pads with spaces."""
        html = "<table><tr><th>H1</th><th>H2</th></tr><tr><td>A</td><td>B</td></tr></table>"
        converter = TableConverter(table_column_width="compact")
        result = converter.convert(html)
        assert "  " not in result
        assert "| H1 | H2 |" in result
        assert "| A | B |" in result

    def test_table_column_width_compact_escapes_pipes(self) -> None:
        """Compact mode must escape literal pipe characters inside cell text."""
        html = "<table><tr><th>H1</th></tr><tr><td>a|b</td></tr></table>"
        converter = TableConverter(table_column_width="compact")
        result = converter.convert(html)
        assert "| a\\|b |" in result

    def test_table_column_width_mixed_normal(self) -> None:
        """Test that mixed mode keeps small tables aligned."""
        html = "<table><tr><th>H1</th><th>H2</th></tr><tr><td>A</td><td>B</td></tr></table>"
        converter = TableConverter(table_column_width="mixed")
        result = converter.convert(html)
        assert "  " in result
        assert "| H1   | H2   |" in result

    def test_table_column_width_mixed_nested(self) -> None:
        """Test that mixed mode automatically uses compact mode for nested tables."""
        html = """
        <table>
            <tr><th>Header</th></tr>
            <tr>
                <td>
                    <table>
                        <tr><td>Inner</td></tr>
                    </table>
                </td>
            </tr>
        </table>
        """
        converter = TableConverter(table_column_width="mixed")
        result = converter.convert(html)
        # The outer table contains a nested table, so it should be compact (no space padding).
        assert "  " not in result

    def test_table_column_width_mixed_long(self) -> None:
        """Test that mixed mode falls back to compact mode for wide tables."""
        # Create a table that is wider than 120 characters when aligned.
        long_text = "x" * 125
        html = f"<table><tr><th>Header</th></tr><tr><td>{long_text}</td></tr></table>"
        converter = TableConverter(table_column_width="mixed")
        result = converter.convert(html)
        # Should be formatted compactly
        assert "  " not in result


class TestMergedCells:
    """Markdown has no merged cells, so a span repeats its value in every position."""

    @staticmethod
    def _convert(html: str) -> list[str]:
        """Convert compactly and return the table rows."""
        converter = TableConverter(table_column_width="compact")
        return [line for line in converter.convert(html).splitlines() if line.startswith("|")]

    def test_rowspan_repeats_value_in_following_row(self) -> None:
        """A rowspan=2 cell must render its value in both rows."""
        html = """
        <table>
            <tr><th>Env</th><th>Branch</th><th>Cluster</th></tr>
            <tr><td>Staging</td><td>release</td><td rowspan="2">Cluster A</td></tr>
            <tr><td>Test</td><td>main</td></tr>
        </table>
        """
        assert self._convert(html) == [
            "| Env | Branch | Cluster |",
            "| --- | --- | --- |",
            "| Staging | release | Cluster A |",
            "| Test | main | Cluster A |",
        ]

    def test_rowspan_three_repeats_in_all_rows(self) -> None:
        """A rowspan larger than two must fill every covered row."""
        html = """
        <table>
            <tr><th>H1</th><th>H2</th></tr>
            <tr><td rowspan="3">Shared</td><td>a</td></tr>
            <tr><td>b</td></tr>
            <tr><td>c</td></tr>
        </table>
        """
        assert self._convert(html)[2:] == [
            "| Shared | a |",
            "| Shared | b |",
            "| Shared | c |",
        ]

    def test_colspan_repeats_value_across_columns(self) -> None:
        """A colspan=3 cell must render its value in all three columns."""
        html = """
        <table>
            <tr><th>H1</th><th>H2</th><th>H3</th></tr>
            <tr><td colspan="3">Full width</td></tr>
        </table>
        """
        assert self._convert(html)[2:] == ["| Full width | Full width | Full width |"]

    def test_rowspan_and_colspan_fill_whole_block(self) -> None:
        """A combined rowspan/colspan cell must fill the full 2x2 block."""
        html = """
        <table>
            <tr><th>H1</th><th>H2</th><th>H3</th></tr>
            <tr><td>a</td><td rowspan="2" colspan="2">Block</td></tr>
            <tr><td>b</td></tr>
        </table>
        """
        assert self._convert(html)[2:] == [
            "| a | Block | Block |",
            "| b | Block | Block |",
        ]

    def test_rowspan_on_header_cell(self) -> None:
        """A rowspan on a header cell repeats into the row below it."""
        html = """
        <table>
            <tr><th rowspan="2">Name</th><th>A</th></tr>
            <tr><th>B</th></tr>
            <tr><td>x</td><td>y</td></tr>
        </table>
        """
        assert self._convert(html) == [
            "| Name | A |",
            "| --- | --- |",
            "| Name | B |",
            "| x | y |",
        ]

    def test_cells_after_a_span_keep_their_column(self) -> None:
        """A span in the first column must not shift the following cells."""
        html = """
        <table>
            <tr><th>H1</th><th>H2</th><th>H3</th></tr>
            <tr><td rowspan="2">R</td><td>b1</td><td>c1</td></tr>
            <tr><td>b2</td><td>c2</td></tr>
        </table>
        """
        assert self._convert(html)[2:] == [
            "| R | b1 | c1 |",
            "| R | b2 | c2 |",
        ]

    def test_malformed_span_attributes_keep_cells(self) -> None:
        """Unparsable or zero span values must fall back to a single cell."""
        html = """
        <table>
            <tr><th>H1</th><th>H2</th></tr>
            <tr><td colspan="abc">A</td><td rowspan="0">B</td></tr>
        </table>
        """
        assert self._convert(html)[2:] == ["| A | B |"]

    def test_spanned_cell_is_converted_only_once(self) -> None:
        """Repeated positions must reuse the conversion, not run it again.

        Cell conversion is stateful in ``Page.Converter`` (the PlantUML macro index
        advances per converted macro), so a repeated cell must not be reprocessed.
        """
        html = """
        <table>
            <tr><th>H1</th><th>H2</th></tr>
            <tr><td rowspan="3">Shared</td><td>a</td></tr>
            <tr><td>b</td></tr>
            <tr><td>c</td></tr>
        </table>
        """
        converter = _CountingTableConverter(table_column_width="compact")
        converter.convert(html)

        ids = converter.converted_cell_ids
        assert len(ids) == len(set(ids)), "a cell was converted more than once"
        # 2 headers + 1 spanned cell + 3 regular cells.
        assert len(ids) == 6
