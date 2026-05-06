"""Tests for the table_converter module."""

from bs4 import BeautifulSoup

from confluence_markdown_exporter.utils.table_converter import TableConverter


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

