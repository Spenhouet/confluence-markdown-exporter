"""Unit tests for PlantUML auto-detection in code blocks."""

from unittest.mock import MagicMock
from unittest.mock import patch

from bs4 import BeautifulSoup

from confluence_markdown_exporter.confluence import Page


class TestPlantUMLCodeBlockDetection:
    """Test cases for @startuml auto-detection in <pre> code blocks."""

    def _make_page(self) -> MagicMock:
        page = MagicMock(spec=Page)
        page.id = 12345
        page.title = "Test Page"
        page.html = "<h1>Test Page</h1>"
        page.labels = []
        page.ancestors = []
        page.attachments = []
        page.editor2 = ""
        page.body_storage = ""
        return page

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_pre_with_startuml_uses_plantuml_fence(self, mock_settings: MagicMock) -> None:
        """Code block containing @startuml should be fenced as plantuml."""
        mock_settings.export.include_document_title = False

        converter = Page.Converter(self._make_page())

        html = (
            '<pre data-syntaxhighlighter-params="brush: java; gutter: false">'
            "@startuml\nA -> B\n@enduml</pre>"
        )
        el = BeautifulSoup(html, "html.parser").find("pre")

        result = converter.convert_pre(el, "@startuml\nA -> B\n@enduml", [])

        assert "```plantuml" in result
        assert "```java" not in result

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_pre_without_startuml_keeps_original_language(self, mock_settings: MagicMock) -> None:
        """Regular code blocks should keep their original language."""
        mock_settings.export.include_document_title = False

        converter = Page.Converter(self._make_page())

        html = (
            '<pre data-syntaxhighlighter-params="brush: java; gutter: false">'
            "public class Foo {}</pre>"
        )
        el = BeautifulSoup(html, "html.parser").find("pre")

        result = converter.convert_pre(el, "public class Foo {}", [])

        assert "```java" in result
        assert "```plantuml" not in result

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_pre_empty_text_returns_empty(self, mock_settings: MagicMock) -> None:
        """Empty pre block should return empty string."""
        mock_settings.export.include_document_title = False

        converter = Page.Converter(self._make_page())

        html = "<pre></pre>"
        el = BeautifulSoup(html, "html.parser").find("pre")

        result = converter.convert_pre(el, "", [])

        assert result == ""

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_pre_no_language_with_startuml(self, mock_settings: MagicMock) -> None:
        """Pre block without brush param but containing @startuml gets plantuml fence."""
        mock_settings.export.include_document_title = False

        converter = Page.Converter(self._make_page())

        html = "<pre>@startuml\nBob -> Alice\n@enduml</pre>"
        el = BeautifulSoup(html, "html.parser").find("pre")

        result = converter.convert_pre(el, "@startuml\nBob -> Alice\n@enduml", [])

        assert "```plantuml" in result
