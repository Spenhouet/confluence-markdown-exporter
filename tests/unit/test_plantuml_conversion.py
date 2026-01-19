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
        """Create a mock page with PlantUML content."""
        page = MagicMock(spec=Page)
        page.id = 12345
        page.title = "Test Page"
        page.html = "<h1>Test Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []

        # Sample editor2 XML with PlantUML macro
        uml_data = '{"umlDefinition":"@startuml\\nAlice -> Bob: Hello\\n@enduml"}'
        page.editor2 = f'''<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="plantuml" ac:schema-version="1"
    ac:macro-id="test-macro-id-123">
    <ac:parameter ac:name="fileName">plantuml_test</ac:parameter>
    <ac:plain-text-body><![CDATA[{uml_data}]]></ac:plain-text-body>
</ac:structured-macro>'''

        return page

    @patch('confluence_markdown_exporter.confluence.settings')
    def test_convert_plantuml_basic(
        self, mock_settings: MagicMock, mock_page: MagicMock
    ) -> None:
        """Test basic PlantUML conversion to Markdown."""
        mock_settings.export.include_document_title = False
        mock_settings.export.page_breadcrumbs = False

        # Create the converter
        converter = Page.Converter(mock_page)

        # Create HTML element that represents PlantUML in the view
        html = '<div data-macro-name="plantuml" data-macro-id="test-macro-id-123"></div>'
        el = BeautifulSoup(html, 'html.parser').find('div')

        # Convert
        result = converter.convert_plantuml(el, "", [])

        # Verify the output is a PlantUML code block
        assert "```plantuml" in result
        assert "@startuml" in result
        assert "Alice -> Bob: Hello" in result
        assert "@enduml" in result
        assert "```" in result

    @patch('confluence_markdown_exporter.confluence.settings')
    def test_convert_plantuml_no_macro_id(
        self, mock_settings: MagicMock, mock_page: MagicMock
    ) -> None:
        """Test PlantUML conversion when macro-id is missing."""
        mock_settings.export.include_document_title = False

        converter = Page.Converter(mock_page)

        # HTML element without macro-id
        html = '<div data-macro-name="plantuml"></div>'
        el = BeautifulSoup(html, 'html.parser').find('div')

        result = converter.convert_plantuml(el, "", [])

        # Should return a comment
        assert "<!-- PlantUML diagram" in result
        assert "no macro-id found" in result

    @patch('confluence_markdown_exporter.confluence.settings')
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
        el = BeautifulSoup(html, 'html.parser').find('div')

        result = converter.convert_plantuml(el, "", [])

        # Verify complex content is preserved
        assert "```plantuml" in result
        assert "@startuml" in result
        assert "skinparam backgroundColor white" in result
        assert "title Test Diagram" in result
        assert "@enduml" in result

    @patch('confluence_markdown_exporter.confluence.settings')
    def test_convert_plantuml_not_found_in_editor2(
        self, mock_settings: MagicMock, mock_page: MagicMock
    ) -> None:
        """Test PlantUML conversion when macro not found in editor2."""
        mock_settings.export.include_document_title = False

        # Set editor2 with different macro-id
        mock_page.editor2 = '''<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="plantuml" ac:macro-id="different-id">
    <ac:plain-text-body><![CDATA[{"umlDefinition":"test"}]]></ac:plain-text-body>
</ac:structured-macro>'''

        converter = Page.Converter(mock_page)

        html = '<div data-macro-name="plantuml" data-macro-id="test-macro-id-123"></div>'
        el = BeautifulSoup(html, 'html.parser').find('div')

        result = converter.convert_plantuml(el, "", [])

        assert "<!-- PlantUML diagram" in result
        assert "not found in editor2" in result

    @patch('confluence_markdown_exporter.confluence.settings')
    def test_convert_plantuml_invalid_json(self, mock_settings: MagicMock) -> None:
        """Test PlantUML conversion with invalid JSON."""
        mock_settings.export.include_document_title = False

        page = MagicMock(spec=Page)
        page.id = 12345
        page.title = "Test Page"
        page.html = "<h1>Test Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []

        # Invalid JSON in CDATA
        page.editor2 = '''<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="plantuml" ac:macro-id="invalid-json-id">
    <ac:plain-text-body><![CDATA[{invalid json}]]></ac:plain-text-body>
</ac:structured-macro>'''

        converter = Page.Converter(page)

        html = '<div data-macro-name="plantuml" data-macro-id="invalid-json-id"></div>'
        el = BeautifulSoup(html, 'html.parser').find('div')

        result = converter.convert_plantuml(el, "", [])

        assert "<!-- PlantUML diagram" in result
        assert "invalid JSON" in result

