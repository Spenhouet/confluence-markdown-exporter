"""Unit tests for clientside macro rendering (Gliffy, DrawIO Server/DC)."""

from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from confluence_markdown_exporter.confluence import Page

Converter = Page.Converter


class SimplePageForTesting:
    """Minimal Page-like object for testing."""

    def __init__(self, body_storage: str | None = None, id_val: int = 0) -> None:
        self.body_storage = body_storage
        self.id = id_val


class TestClientsideMacroAttachmentNames:
    """Test _clientside_macro_attachment_names() parsing."""

    def test_gliffy_diagram_names_extracted(self) -> None:
        """Test that Gliffy diagram names are extracted from storage."""
        page = SimplePageForTesting(
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="diagramName">my_workflow</ac:parameter>'
            '</ac:structured-macro>',
            12345
        )
        names = Page._clientside_macro_attachment_names(page)
        assert "my_workflow" in names
        assert "my_workflow.png" in names
        assert len(names) == 2

    def test_drawio_diagram_names_extracted(self) -> None:
        """Test that DrawIO diagram names are extracted from storage."""
        page = SimplePageForTesting(
            '<ac:structured-macro ac:name="drawio">'
            '<ac:parameter ac:name="diagramName">architecture</ac:parameter>'
            '</ac:structured-macro>',
            12346
        )
        names = Page._clientside_macro_attachment_names(page)
        assert "architecture" in names
        assert "architecture.png" in names
        assert len(names) == 2

    def test_both_gliffy_and_drawio_extracted(self) -> None:
        """Test that both Gliffy and DrawIO diagrams are extracted together."""
        page = SimplePageForTesting(
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="diagramName">workflow</ac:parameter>'
            '</ac:structured-macro>'
            '<ac:structured-macro ac:name="drawio">'
            '<ac:parameter ac:name="diagramName">architecture</ac:parameter>'
            '</ac:structured-macro>',
            12347
        )
        names = Page._clientside_macro_attachment_names(page)
        assert "workflow" in names
        assert "workflow.png" in names
        assert "architecture" in names
        assert "architecture.png" in names
        assert len(names) == 4

    def test_no_macros_returns_empty_set(self) -> None:
        """Test that non-macro storage returns empty set."""
        page = SimplePageForTesting("<p>Just some text with no macros</p>", 12348)
        names = Page._clientside_macro_attachment_names(page)
        assert names == set()

    def test_missing_diagram_name_ignored(self) -> None:
        """Test that macros without diagramName parameter are ignored."""
        page = SimplePageForTesting(
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="otherParam">value</ac:parameter>'
            '</ac:structured-macro>',
            12349
        )
        names = Page._clientside_macro_attachment_names(page)
        assert names == set()

    def test_empty_storage_returns_empty_set(self) -> None:
        """Test that empty body.storage returns empty set."""
        page = SimplePageForTesting("", 12350)
        names = Page._clientside_macro_attachment_names(page)
        assert names == set()

    def test_none_storage_returns_empty_set(self) -> None:
        """Test that None body.storage returns empty set."""
        page = SimplePageForTesting(None, 12351)
        names = Page._clientside_macro_attachment_names(page)
        assert names == set()


class TestGliffyConversion:
    """Test Gliffy diagram conversion to markdown."""

    @pytest.mark.parametrize("href_mode", ["wiki", "relative"])
    def test_gliffy_renders_as_image_link(self, href_mode: str) -> None:
        """Test that Gliffy diagrams render as markdown image links."""
        page = MagicMock(spec=Page)
        page.body_storage = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="diagramName">my_diagram</ac:parameter>'
            '</ac:structured-macro>'
        )

        # Mock attachment
        attachment = MagicMock()
        attachment.export_path.name = "my_diagram.png"
        page.get_attachments_by_title = MagicMock(return_value=[attachment])

        converter = MagicMock(spec=Converter)
        converter.page = page

        # Call convert_gliffy
        result = Converter.convert_gliffy(converter, BeautifulSoup("", "html.parser"), "", [])

        # Should contain the diagram name and be an image link
        assert "my_diagram" in result
        assert ("![" in result or "![[" in result)

    def test_gliffy_missing_attachment_returns_error(self) -> None:
        """Test that missing Gliffy attachment returns error comment."""
        page = MagicMock(spec=Page)
        page.body_storage = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="diagramName">missing_diagram</ac:parameter>'
            '</ac:structured-macro>'
        )
        page.get_attachments_by_title = MagicMock(return_value=[])

        converter = MagicMock(spec=Converter)
        converter.page = page

        result = Converter.convert_gliffy(converter, BeautifulSoup("", "html.parser"), "", [])
        assert "not found" in result

    def test_gliffy_no_storage_returns_error(self) -> None:
        """Test that Gliffy with no storage returns error."""
        page = MagicMock(spec=Page)
        page.body_storage = None

        converter = MagicMock(spec=Converter)
        converter.page = page

        result = Converter.convert_gliffy(converter, BeautifulSoup("", "html.parser"), "", [])
        assert "not found" in result


class TestDrawIOServerDCFallback:
    """Test DrawIO fallback to Server/DC storage format."""

    def test_drawio_cloud_html_pattern_still_works(self) -> None:
        """Test that Cloud format (HTML pattern) still works."""
        page = MagicMock(spec=Page)
        page.body_storage = ""

        # Mock attachments
        drawio_att = MagicMock()
        drawio_att.export_path.name = "architecture.drawio"

        preview_att = MagicMock()
        preview_att.export_path.name = "architecture.png"

        def get_atts(name: str) -> list:
            if name == "architecture":
                return [drawio_att]
            if name == "architecture.png":
                return [preview_att]
            return []

        page.get_attachments_by_title = MagicMock(side_effect=get_atts)

        converter = MagicMock(spec=Converter)
        converter.page = page
        converter._get_path_for_href = MagicMock(return_value="attachments/architecture.drawio")

        # Cloud HTML format with |diagramName=...| pattern
        html_el = BeautifulSoup("Something |diagramName=architecture| something", "html.parser")
        result = Converter.convert_drawio(converter, html_el, "", [])

        assert "architecture" in result

    def test_drawio_server_dc_storage_fallback(self) -> None:
        """Test that Server/DC format (storage fallback) works."""
        page = MagicMock(spec=Page)
        page.body_storage = (
            '<ac:structured-macro ac:name="drawio">'
            '<ac:parameter ac:name="diagramName">architecture</ac:parameter>'
            '</ac:structured-macro>'
        )

        # Mock attachments
        drawio_att = MagicMock()
        drawio_att.export_path.name = "architecture.drawio"

        preview_att = MagicMock()
        preview_att.export_path.name = "architecture.png"

        def get_atts(name: str) -> list:
            if name == "architecture":
                return [drawio_att]
            if name == "architecture.png":
                return [preview_att]
            return []

        page.get_attachments_by_title = MagicMock(side_effect=get_atts)

        converter = MagicMock(spec=Converter)
        converter.page = page
        converter._get_path_for_href = MagicMock(return_value="attachments/architecture.drawio")

        # Mock _extract_drawio_name_from_storage to return the diagram name
        converter._extract_drawio_name_from_storage = MagicMock(return_value="architecture")

        # No Cloud pattern - should fall back to storage
        html_el = BeautifulSoup("", "html.parser")
        result = Converter.convert_drawio(converter, html_el, "", [])

        assert "architecture" in result
