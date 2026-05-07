"""Unit tests for `include` / `excerpt-include` macro conversion."""

from unittest.mock import MagicMock
from unittest.mock import patch

from bs4 import BeautifulSoup

from confluence_markdown_exporter.confluence import Page


def _make_page(editor2: str) -> MagicMock:
    page = MagicMock(spec=Page)
    page.id = 12345
    page.title = "Test Page"
    page.html = "<h1>Test Page</h1>"
    page.labels = []
    page.ancestors = []
    page.attachments = []
    page.editor2 = editor2
    return page


INCLUDE_EDITOR2 = """<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="include" ac:schema-version="1"
    ac:local-id="local-1" ac:macro-id="macro-include-1">
    <ac:parameter ac:name="">
        <ac:link><ri:page ri:content-title="Shared Reference Page"
            ri:version-at-save="1" /></ac:link>
    </ac:parameter>
</ac:structured-macro>"""

EXCERPT_INCLUDE_EDITOR2 = """<?xml version="1.0" encoding="UTF-8"?>
<ac:structured-macro ac:name="excerpt-include" ac:schema-version="1"
    ac:local-id="local-2" ac:macro-id="macro-excerpt-1">
    <ac:parameter ac:name="">
        <ac:link><ri:page ri:content-title="Source Page" /></ac:link>
    </ac:parameter>
    <ac:parameter ac:name="name">Named Excerpt</ac:parameter>
</ac:structured-macro>"""


@patch("confluence_markdown_exporter.confluence.settings")
def test_include_macro_transclusion_mode(mock_settings: MagicMock) -> None:
    mock_settings.export.include_document_title = False
    mock_settings.export.page_breadcrumbs = False
    mock_settings.export.include_macro = "transclusion"

    converter = Page.Converter(_make_page(INCLUDE_EDITOR2))

    html = (
        '<div data-macro-name="include" data-macro-id="macro-include-1">'
        "<p>fallback inline text</p></div>"
    )
    el = BeautifulSoup(html, "html.parser").find("div")

    result = converter.convert_include(el, "fallback inline text", [])

    assert result.strip() == "![[Shared Reference Page]]"


@patch("confluence_markdown_exporter.confluence.settings")
def test_excerpt_include_macro_transclusion_mode(mock_settings: MagicMock) -> None:
    mock_settings.export.include_document_title = False
    mock_settings.export.page_breadcrumbs = False
    mock_settings.export.include_macro = "transclusion"

    converter = Page.Converter(_make_page(EXCERPT_INCLUDE_EDITOR2))

    html = (
        '<div data-macro-name="excerpt-include" data-macro-id="macro-excerpt-1">'
        "<p>resolved excerpt body</p></div>"
    )
    el = BeautifulSoup(html, "html.parser").find("div")

    result = converter.convert_include(el, "resolved excerpt body", [])

    assert result.strip() == "![[Source Page]]"


@patch("confluence_markdown_exporter.confluence.settings")
def test_include_macro_inline_mode(mock_settings: MagicMock) -> None:
    mock_settings.export.include_document_title = False
    mock_settings.export.page_breadcrumbs = False
    mock_settings.export.include_macro = "inline"

    converter = Page.Converter(_make_page(INCLUDE_EDITOR2))

    html = (
        '<div data-macro-name="include" data-macro-id="macro-include-1">'
        "<p>inlined content</p></div>"
    )
    el = BeautifulSoup(html, "html.parser").find("div")

    result = converter.convert_include(el, "inlined content", [])

    assert "![[" not in result


@patch("confluence_markdown_exporter.confluence.settings")
def test_excerpt_include_inline_strips_source_page_title_panel(
    mock_settings: MagicMock,
) -> None:
    mock_settings.export.include_document_title = False
    mock_settings.export.page_breadcrumbs = False
    mock_settings.export.include_macro = "inline"

    converter = Page.Converter(_make_page(EXCERPT_INCLUDE_EDITOR2))

    html = (
        '<div class="panel conf-macro output-inline" data-macro-name="excerpt-include"'
        ' data-macro-id="macro-excerpt-1">'
        '<div class="panelHeader"><b>Source Page</b></div>'
        '<div class="panelContent"><table><tr><td>body cell</td></tr></table></div>'
        "</div>"
    )

    stripped = converter._strip_excerpt_include_panel_titles(html)

    assert "Source Page" not in stripped
    assert "panelHeader" not in stripped
    assert "panelContent" not in stripped
    assert "body cell" in stripped


@patch("confluence_markdown_exporter.confluence.settings")
def test_excerpt_include_inline_keeps_body_when_no_panel(
    mock_settings: MagicMock,
) -> None:
    mock_settings.export.include_document_title = False
    mock_settings.export.page_breadcrumbs = False
    mock_settings.export.include_macro = "inline"

    converter = Page.Converter(_make_page(EXCERPT_INCLUDE_EDITOR2))

    html = (
        '<span class="conf-macro output-inline" data-macro-name="excerpt-include"'
        ' data-macro-id="macro-excerpt-1">actual excerpt body</span>'
    )

    stripped = converter._strip_excerpt_include_panel_titles(html)

    assert "actual excerpt body" in stripped


@patch("confluence_markdown_exporter.confluence.settings")
def test_include_macro_transclusion_falls_back_when_target_unresolvable(
    mock_settings: MagicMock,
) -> None:
    mock_settings.export.include_document_title = False
    mock_settings.export.page_breadcrumbs = False
    mock_settings.export.include_macro = "transclusion"

    # editor2 has a different macro-id → lookup fails
    converter = Page.Converter(_make_page(INCLUDE_EDITOR2))

    html = '<div data-macro-name="include" data-macro-id="missing-id"><p>inlined content</p></div>'
    el = BeautifulSoup(html, "html.parser").find("div")

    result = converter.convert_include(el, "inlined content", [])

    assert "![[" not in result
