"""Unit tests for PlantUML diagram conversion."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from confluence_markdown_exporter.confluence import Page


class TestPlantUMLConversion:
    """Test cases for PlantUML diagram conversion."""

    @pytest.fixture
    def mock_page(self) -> MagicMock:
        """Create a mock page with PlantUML content in editor2 (Cloud format)."""
        page = MagicMock(spec=Page)
        page.id = 12345
        page.title = "Test Page"
        page.html = "<h1>Test Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []
        page.body_storage = ""

        # Sample editor2 XML with PlantUML macro
        uml_data = '{"umlDefinition":"@startuml\\nAlice -> Bob: Hello\\n@enduml"}'
        page.editor2 = f'''<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="plantuml" ac:schema-version="1"
    ac:macro-id="test-macro-id-123">
    <ac:parameter ac:name="fileName">plantuml_test</ac:parameter>
    <ac:plain-text-body><![CDATA[{uml_data}]]></ac:plain-text-body>
</ac:structured-macro>'''

        return page

    @pytest.fixture
    def mock_server_page(self) -> MagicMock:
        """Create a mock page with PlantUML content in body.storage (Server format)."""
        page = MagicMock(spec=Page)
        page.id = 67890
        page.title = "Server Page"
        page.html = "<h1>Server Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []
        page.editor2 = ""

        page.body_storage = (
            '<ac:structured-macro ac:name="plantuml">'
            "<ac:plain-text-body>"
            "<![CDATA[@startuml\nAlice -> Bob: Hello\n@enduml]]>"
            "</ac:plain-text-body>"
            "</ac:structured-macro>"
        )

        return page

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_convert_plantuml_cloud_editor2(
        self, mock_settings: MagicMock, mock_page: MagicMock
    ) -> None:
        """Test PlantUML conversion from editor2 XML (Cloud format)."""
        mock_settings.export.include_document_title = False
        mock_settings.export.page_breadcrumbs = False

        converter = Page.Converter(mock_page)

        html = '<div data-macro-name="plantuml" data-macro-id="test-macro-id-123"></div>'
        el = BeautifulSoup(html, "html.parser").find("div")

        result = converter.convert_plantuml(el, "", [])

        assert "```plantuml" in result
        assert "@startuml" in result
        assert "Alice -> Bob: Hello" in result
        assert "@enduml" in result

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_convert_plantuml_server_storage(
        self, mock_settings: MagicMock, mock_server_page: MagicMock
    ) -> None:
        """Test PlantUML conversion from body.storage (Server/DC format)."""
        mock_settings.export.include_document_title = False

        converter = Page.Converter(mock_server_page)

        # Server renders PlantUML as <span> without macro-id
        html = '<span class="plantuml-svg-image" data-macro-name="plantuml"></span>'
        el = BeautifulSoup(html, "html.parser").find("span")

        result = converter.convert_plantuml(el, "", [])

        assert "```plantuml" in result
        assert "@startuml" in result
        assert "Alice -> Bob: Hello" in result
        assert "@enduml" in result

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_convert_plantuml_server_multiple_diagrams(
        self, mock_settings: MagicMock
    ) -> None:
        """Test positional matching of multiple PlantUML diagrams on Server."""
        mock_settings.export.include_document_title = False

        page = MagicMock(spec=Page)
        page.id = 11111
        page.title = "Multi-Diagram Page"
        page.html = "<h1>Multi-Diagram Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []
        page.editor2 = ""

        page.body_storage = (
            '<ac:structured-macro ac:name="plantuml">'
            "<ac:plain-text-body>"
            "<![CDATA[@startuml\nAlice -> Bob: First\n@enduml]]>"
            "</ac:plain-text-body>"
            "</ac:structured-macro>"
            "<p>Some text between diagrams</p>"
            '<ac:structured-macro ac:name="plantuml">'
            "<ac:plain-text-body>"
            "<![CDATA[@startuml\nBob -> Carol: Second\n@enduml]]>"
            "</ac:plain-text-body>"
            "</ac:structured-macro>"
        )

        converter = Page.Converter(page)

        html1 = '<span data-macro-name="plantuml"></span>'
        el1 = BeautifulSoup(html1, "html.parser").find("span")
        result1 = converter.convert_plantuml(el1, "", [])

        html2 = '<span data-macro-name="plantuml"></span>'
        el2 = BeautifulSoup(html2, "html.parser").find("span")
        result2 = converter.convert_plantuml(el2, "", [])

        assert "Alice -> Bob: First" in result1
        assert "Bob -> Carol: Second" in result2

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_convert_plantuml_no_source_available(
        self, mock_settings: MagicMock
    ) -> None:
        """Test PlantUML conversion when neither editor2 nor storage has content."""
        mock_settings.export.include_document_title = False

        page = MagicMock(spec=Page)
        page.id = 99999
        page.title = "Empty Page"
        page.html = "<h1>Empty Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []
        page.editor2 = ""
        page.body_storage = ""

        converter = Page.Converter(page)

        html = '<div data-macro-name="plantuml"></div>'
        el = BeautifulSoup(html, "html.parser").find("div")

        result = converter.convert_plantuml(el, "", [])

        assert "<!-- PlantUML diagram" in result
        assert "source not found" in result

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_convert_plantuml_complex_diagram(self, mock_settings: MagicMock) -> None:
        """Test PlantUML conversion with a complex diagram."""
        mock_settings.export.include_document_title = False

        page = MagicMock(spec=Page)
        page.id = 12345
        page.title = "Test Page"
        page.html = "<h1>Test Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []
        page.body_storage = ""

        # Complex PlantUML diagram - properly escaped for JSON
        uml_definition = (
            "@startuml\\nskinparam backgroundColor white\\ntitle Test Diagram\\n\\n"
            "|Actor|\\nstart\\n:Action 1;\\n:Action 2;\\nstop\\n@enduml"
        )

        page.editor2 = f'''<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="plantuml" ac:schema-version="1"
    ac:macro-id="complex-macro-id">
    <ac:plain-text-body><![CDATA[{{"umlDefinition":"{uml_definition}"}}]]></ac:plain-text-body>
</ac:structured-macro>'''

        converter = Page.Converter(page)

        html = '<div data-macro-name="plantuml" data-macro-id="complex-macro-id"></div>'
        el = BeautifulSoup(html, "html.parser").find("div")

        result = converter.convert_plantuml(el, "", [])

        assert "```plantuml" in result
        assert "@startuml" in result
        assert "skinparam backgroundColor white" in result
        assert "title Test Diagram" in result
        assert "@enduml" in result

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_convert_plantuml_editor2_fallback_to_storage(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that when editor2 macro-id doesn't match, storage is used as fallback."""
        mock_settings.export.include_document_title = False

        page = MagicMock(spec=Page)
        page.id = 22222
        page.title = "Fallback Page"
        page.html = "<h1>Fallback Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []

        # editor2 has a macro but with a different ID
        page.editor2 = '''<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="plantuml" ac:macro-id="different-id">
    <ac:plain-text-body><![CDATA[{"umlDefinition":"@startuml\\nwrong\\n@enduml"}]]></ac:plain-text-body>
</ac:structured-macro>'''

        # body.storage has the correct content
        page.body_storage = (
            '<ac:structured-macro ac:name="plantuml">'
            "<ac:plain-text-body>"
            "<![CDATA[@startuml\nCorrect from storage\n@enduml]]>"
            "</ac:plain-text-body>"
            "</ac:structured-macro>"
        )

        converter = Page.Converter(page)

        # View element references an ID not found in editor2
        html = '<div data-macro-name="plantuml" data-macro-id="nonexistent-id"></div>'
        el = BeautifulSoup(html, "html.parser").find("div")

        result = converter.convert_plantuml(el, "", [])

        assert "```plantuml" in result
        assert "Correct from storage" in result

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_convert_plantuml_invalid_json_falls_through(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that invalid JSON in editor2 falls through to storage."""
        mock_settings.export.include_document_title = False

        page = MagicMock(spec=Page)
        page.id = 33333
        page.title = "Invalid JSON Page"
        page.html = "<h1>Invalid JSON Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []

        page.editor2 = '''<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="plantuml" ac:macro-id="json-error-id">
    <ac:plain-text-body><![CDATA[{invalid json}]]></ac:plain-text-body>
</ac:structured-macro>'''

        page.body_storage = (
            '<ac:structured-macro ac:name="plantuml">'
            "<ac:plain-text-body>"
            "<![CDATA[@startuml\nFallback content\n@enduml]]>"
            "</ac:plain-text-body>"
            "</ac:structured-macro>"
        )

        converter = Page.Converter(page)

        html = '<div data-macro-name="plantuml" data-macro-id="json-error-id"></div>'
        el = BeautifulSoup(html, "html.parser").find("div")

        result = converter.convert_plantuml(el, "", [])

        assert "```plantuml" in result
        assert "Fallback content" in result

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_convert_span_dispatches_plantuml(
        self, mock_settings: MagicMock, mock_server_page: MagicMock
    ) -> None:
        """Test that convert_span dispatches plantuml macros on Server."""
        mock_settings.export.include_document_title = False
        mock_settings.export.convert_text_highlights = False
        mock_settings.export.convert_font_colors = False

        converter = Page.Converter(mock_server_page)

        html = (
            '<span class="plantuml-svg-image conf-macro output-inline" '
            'data-hasbody="true" data-macro-name="plantuml">'
            "<svg>...</svg>"
            "</span>"
        )
        el = BeautifulSoup(html, "html.parser").find("span")

        result = converter.convert_span(el, "svg text", [])

        assert "```plantuml" in result
        assert "@startuml" in result

