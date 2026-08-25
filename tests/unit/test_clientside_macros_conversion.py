"""Unit tests for clientside macro rendering (Gliffy, DrawIO Server/DC)."""

from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from confluence_markdown_exporter.confluence import Page


class TestClientsideMacroAttachmentNames:
    """Test _clientside_macro_attachment_names() parsing."""

    @pytest.fixture
    def mock_page_gliffy(self) -> MagicMock:
        """Create a mock page with Gliffy macro in body.storage."""
        page = MagicMock(spec=Page)
        page.id = 12345
        page.title = "Gliffy Test Page"
        page.body_storage = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="diagramName">my_workflow</ac:parameter>'
            "</ac:structured-macro>"
        )
        return page

    @pytest.fixture
    def mock_page_drawio(self) -> MagicMock:
        """Create a mock page with DrawIO macro in body.storage."""
        page = MagicMock(spec=Page)
        page.id = 12346
        page.title = "DrawIO Test Page"
        page.body_storage = (
            '<ac:structured-macro ac:name="drawio">'
            '<ac:parameter ac:name="diagramName">architecture</ac:parameter>'
            "</ac:structured-macro>"
        )
        return page

    @pytest.fixture
    def mock_page_both(self) -> MagicMock:
        """Create a mock page with both Gliffy and DrawIO macros."""
        page = MagicMock(spec=Page)
        page.id = 12347
        page.title = "Mixed Macros Test Page"
        page.body_storage = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="diagramName">workflow</ac:parameter>'
            "</ac:structured-macro>"
            '<ac:structured-macro ac:name="drawio">'
            '<ac:parameter ac:name="diagramName">architecture</ac:parameter>'
            "</ac:structured-macro>"
        )
        return page

    @pytest.fixture
    def mock_page_no_macros(self) -> MagicMock:
        """Create a mock page with no clientside macros."""
        page = MagicMock(spec=Page)
        page.id = 12348
        page.title = "No Macros Page"
        page.body_storage = "<p>Just some text with no macros</p>"
        return page

    def test_gliffy_diagram_names_extracted(self, mock_page_gliffy: MagicMock) -> None:
        """Test that Gliffy diagram names are extracted from storage."""
        names = Page._clientside_macro_attachment_names(mock_page_gliffy)
        assert "my_workflow" in names
        assert "my_workflow.png" in names
        assert len(names) == 2

    def test_drawio_diagram_names_extracted(self, mock_page_drawio: MagicMock) -> None:
        """Test that DrawIO diagram names are extracted from storage."""
        names = Page._clientside_macro_attachment_names(mock_page_drawio)
        assert "architecture" in names
        assert "architecture.png" in names
        assert len(names) == 2

    def test_both_gliffy_and_drawio_extracted(self, mock_page_both: MagicMock) -> None:
        """Test that both Gliffy and DrawIO diagrams are extracted together."""
        names = Page._clientside_macro_attachment_names(mock_page_both)
        assert "workflow" in names
        assert "workflow.png" in names
        assert "architecture" in names
        assert "architecture.png" in names
        assert len(names) == 4

    def test_no_macros_returns_empty_set(self, mock_page_no_macros: MagicMock) -> None:
        """Test that empty storage returns empty set."""
        names = Page._clientside_macro_attachment_names(mock_page_no_macros)
        assert len(names) == 0
        assert isinstance(names, set)

    def test_missing_diagram_name_ignored(self) -> None:
        """Test that macros without diagramName parameter are ignored."""
        page = MagicMock(spec=Page)
        page.body_storage = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="otherParam">value</ac:parameter>'
            "</ac:structured-macro>"
        )
        names = Page._clientside_macro_attachment_names(page)
        assert len(names) == 0

    def test_empty_storage_returns_empty_set(self) -> None:
        """Test that empty body_storage returns empty set."""
        page = MagicMock(spec=Page)
        page.body_storage = ""
        names = Page._clientside_macro_attachment_names(page)
        assert len(names) == 0

    def test_none_storage_returns_empty_set(self) -> None:
        """Test that None body_storage returns empty set."""
        page = MagicMock(spec=Page)
        page.body_storage = None
        names = Page._clientside_macro_attachment_names(page)
        assert len(names) == 0


class TestGliffyConversion:
    """Test Gliffy macro conversion to Markdown."""

    @pytest.fixture
    def mock_page_with_attachment(self) -> MagicMock:
        """Create a mock page with Gliffy and attachment."""
        page = MagicMock(spec=Page)
        page.id = 12349
        page.title = "Gliffy with Attachment"
        page.body_storage = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="diagramName">workflow</ac:parameter>'
            "</ac:structured-macro>"
        )

        # Mock attachment
        attachment = MagicMock()
        attachment.export_path.name = "workflow.png"

        page.get_attachments_by_title = MagicMock(return_value=[attachment])

        return page

    @pytest.fixture
    def mock_page_no_attachment(self) -> MagicMock:
        """Create a mock page with Gliffy but no attachment."""
        page = MagicMock(spec=Page)
        page.id = 12350
        page.title = "Gliffy no Attachment"
        page.body_storage = (
            '<ac:structured-macro ac:name="gliffy">'
            '<ac:parameter ac:name="diagramName">workflow</ac:parameter>'
            "</ac:structured-macro>"
        )
        page.get_attachments_by_title = MagicMock(return_value=[])
        return page

    @pytest.fixture
    def mock_page_no_storage(self) -> MagicMock:
        """Create a mock page with no body.storage."""
        page = MagicMock(spec=Page)
        page.id = 12351
        page.body_storage = ""
        page.get_attachments_by_title = MagicMock(return_value=[])
        return page

    @pytest.mark.parametrize("attachment_href", ["relative", "absolute"])
    def test_gliffy_renders_as_image_markdown_link(
        self, mock_page_with_attachment: MagicMock, attachment_href: str
    ) -> None:
        """Test that Gliffy diagrams render as markdown image links."""
        from unittest.mock import patch

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.attachment_href = attachment_href
            mock_settings.export.include_document_title = False

            converter = Page.Converter(mock_page_with_attachment)

            html = '<div data-macro-name="gliffy"></div>'
            el = BeautifulSoup(html, "html.parser").find("div")

            result = converter.convert_gliffy(el, "", [])

            if attachment_href == "wiki":
                assert "![[" in result
                assert "]]" in result
            else:
                assert "![" in result
                assert "](" in result
                assert "workflow.png" in result

    def test_gliffy_missing_attachment_returns_error_comment(
        self, mock_page_no_attachment: MagicMock
    ) -> None:
        """Test that missing attachments generate error comments."""
        from unittest.mock import patch

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.attachment_href = "relative"
            mock_settings.export.include_document_title = False

            converter = Page.Converter(mock_page_no_attachment)

            html = '<div data-macro-name="gliffy"></div>'
            el = BeautifulSoup(html, "html.parser").find("div")

            result = converter.convert_gliffy(el, "", [])

            assert "<!--" in result
            assert "Gliffy" in result
            assert "not found" in result

    def test_gliffy_no_storage_returns_error_comment(
        self, mock_page_no_storage: MagicMock
    ) -> None:
        """Test that empty storage generates error comment."""
        from unittest.mock import patch

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.attachment_href = "relative"
            mock_settings.export.include_document_title = False

            converter = Page.Converter(mock_page_no_storage)

            html = '<div data-macro-name="gliffy"></div>'
            el = BeautifulSoup(html, "html.parser").find("div")

            result = converter.convert_gliffy(el, "", [])

            assert "<!--" in result or result == ""  # Either error comment or empty


class TestDrawIOServerDCFallback:
    """Test improved DrawIO conversion with Server/DC fallback."""

    @pytest.fixture
    def mock_page_drawio_storage(self) -> MagicMock:
        """Create a mock page with DrawIO in storage (Server/DC format)."""
        page = MagicMock(spec=Page)
        page.id = 12352
        page.title = "DrawIO Server Storage"
        page.body_storage = (
            '<ac:structured-macro ac:name="drawio">'
            '<ac:parameter ac:name="diagramName">architecture</ac:parameter>'
            "</ac:structured-macro>"
        )
        page.body = ""  # No HTML pattern (Server/DC renders clientside)

        # Mock attachments
        drawio_attachment = MagicMock()
        drawio_attachment.export_path.name = "architecture.drawio"

        preview_attachment = MagicMock()
        preview_attachment.export_path.name = "architecture.png"

        def get_attachments_by_name(name: str):
            if name == "architecture":
                return [drawio_attachment]
            elif name == "architecture.png":
                return [preview_attachment]
            return []

        page.get_attachments_by_title = MagicMock(side_effect=get_attachments_by_name)

        return page

    def test_drawio_cloud_html_pattern_still_works(self) -> None:
        """Test that Cloud format (HTML pattern) still works."""
        from unittest.mock import patch

        page = MagicMock(spec=Page)
        page.body_storage = ""  # No storage (Cloud)
        page.body = ""

        drawio_attachment = MagicMock()
        drawio_attachment.export_path.name = "diagram.drawio"

        preview_attachment = MagicMock()
        preview_attachment.export_path.name = "diagram.png"

        page.get_attachments_by_title = MagicMock(
            side_effect=lambda name: (
                [drawio_attachment] if name == "diagram"
                else [preview_attachment] if name == "diagram.png"
                else []
            )
        )

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.attachment_href = "relative"
            mock_settings.export.include_document_title = False

            converter = Page.Converter(page)

            # Cloud format has the pattern in the HTML
            html = '<div data-macro-name="drawio">|diagramName=diagram|</div>'
            el = BeautifulSoup(html, "html.parser").find("div")

            result = converter.convert_drawio(el, "", [])

            assert "![" in result or "![[" in result
            assert "diagram" in result

    def test_drawio_server_dc_storage_fallback(
        self, mock_page_drawio_storage: MagicMock
    ) -> None:
        """Test that Server/DC format (storage-based) works."""
        from unittest.mock import patch

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.attachment_href = "relative"
            mock_settings.export.include_document_title = False

            converter = Page.Converter(mock_page_drawio_storage)

            # Server/DC renders as empty div (no pattern in HTML)
            html = '<div data-macro-name="drawio"></div>'
            el = BeautifulSoup(html, "html.parser").find("div")

            result = converter.convert_drawio(el, "", [])

            # Should fall back to storage and render successfully
            assert "![" in result
            assert "architecture" in result
