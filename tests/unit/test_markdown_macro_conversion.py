"""Unit tests for Markdown macro conversion."""

from unittest.mock import MagicMock

import pytest

from confluence_markdown_exporter.confluence import Page


def _storage_macro(source: str, name: str = "markdown") -> str:
    return (
        f'<ac:structured-macro ac:name="{name}" ac:schema-version="1" ac:macro-id="x">'
        f"<ac:plain-text-body><![CDATA[{source}]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )


def _rendered_macro(inner: str, name: str = "markdown") -> str:
    """A Markdown macro as Server / Data Center renders it in body.view."""
    return (
        f'<div class="conf-macro output-block" data-hasbody="true" data-macro-name="{name}">'
        f"{inner}"
        "<script>AJS.$('[data-macro-name=\"markdown\"] code').each(function(i, b) {});</script>"
        "<style>.hljs {display: inline;}</style>"
        "</div>"
    )


@pytest.fixture
def page() -> MagicMock:
    page = MagicMock(spec=Page)
    page.id = 1
    page.title = "Server Page"
    page.base_url = "https://wiki.example.com"
    page.labels = []
    page.ancestors = []
    page.attachments = []
    page.editor2 = ""
    page.body_storage = ""
    return page


def _convert(page: MagicMock, html: str) -> str:
    return Page.Converter(page).convert(html)


class TestMarkdownMacroFromStorage:
    def test_source_taken_from_storage(self, page: MagicMock) -> None:
        source = "# 1. Versions\n\n| Version | Date |\n|---|---|\n| 1.0 | 2026-10-16 |\n"
        page.body_storage = _storage_macro(source)
        html = _rendered_macro('<h1 id="1-versions">1. Versions</h1><table></table>')

        result = _convert(page, html)

        assert "| Version | Date |" in result
        assert "| 1.0 | 2026-10-16 |" in result
        assert "content not found" not in result
        assert "AJS" not in result

    def test_several_macros_matched_by_position(self, page: MagicMock) -> None:
        page.body_storage = (
            _storage_macro("first source")
            + '<ac:structured-macro ac:name="expand"><ac:rich-text-body>'
            + _storage_macro("second source")
            + "</ac:rich-text-body></ac:structured-macro>"
            + _storage_macro("third source")
        )
        html = (
            _rendered_macro("<p>first</p>")
            + '<div class="expand-container" data-macro-name="expand">'
            '<span class="expand-control-text">More</span>'
            '<div class="expand-content">'
            + _rendered_macro("<p>second</p>")
            + "</div></div>"
            + _rendered_macro("<p>third</p>")
        )

        result = _convert(page, html)

        assert result.index("first source") < result.index("second source")
        assert result.index("second source") < result.index("third source")
        assert result.count("second source") == 1

    def test_macro_from_include_is_not_counted(self, page: MagicMock) -> None:
        page.body_storage = _storage_macro("own source")
        html = (
            '<div data-macro-name="include">'
            + _rendered_macro("<p>included</p>")
            + "</div>"
            + _rendered_macro("<p>own</p>")
        )

        result = _convert(page, html)

        assert "own source" in result
        assert "included" in result
        assert result.count("own source") == 1

    def test_count_mismatch_falls_back_to_rendered_content(self, page: MagicMock) -> None:
        page.body_storage = _storage_macro("only one in storage")
        html = _rendered_macro("<p>rendered one</p>") + _rendered_macro("<p>rendered two</p>")

        result = _convert(page, html)

        assert "only one in storage" not in result
        assert "rendered one" in result
        assert "rendered two" in result
        assert "AJS" not in result
        assert ".hljs" not in result

    def test_mohamicorp_parameter_in_storage(self, page: MagicMock) -> None:
        page.body_storage = (
            '<ac:structured-macro ac:name="mohamicorp-markdown">'
            '<ac:parameter ac:name="markdown">**bold source**</ac:parameter>'
            "</ac:structured-macro>"
        )
        html = _rendered_macro("<p><strong>bold</strong></p>", name="mohamicorp-markdown")

        assert "**bold source**" in _convert(page, html)

    def test_editor2_wins_over_storage(self, page: MagicMock) -> None:
        page.editor2 = (
            '<ac:structured-macro ac:name="markdown" ac:macro-id="m1">'
            "<ac:plain-text-body><![CDATA[editor2 source]]></ac:plain-text-body>"
            "</ac:structured-macro>"
        )
        page.body_storage = _storage_macro("storage source")
        html = '<div data-macro-name="markdown" data-macro-id="m1"><p>rendered</p></div>'

        result = _convert(page, html)

        assert "editor2 source" in result
        assert "storage source" not in result

    def test_empty_macro_keeps_placeholder_comment(self, page: MagicMock) -> None:
        html = '<div data-macro-name="markdown"></div>'

        assert "content not found" in _convert(page, html)


def test_storage_param_lookup_by_position_reads_page_body(page: MagicMock) -> None:
    """Used by draw.io and Gliffy on Server / Data Center when the view has no macro-id."""
    from bs4 import BeautifulSoup

    page.body = '<div class="drawio-macro"></div><div class="drawio-macro"></div>'
    page.body_storage = (
        '<ac:structured-macro ac:name="drawio"><ac:parameter ac:name="diagramName">'
        "first</ac:parameter></ac:structured-macro>"
        '<ac:structured-macro ac:name="drawio"><ac:parameter ac:name="diagramName">'
        "second</ac:parameter></ac:structured-macro>"
    )
    el = BeautifulSoup(page.body, "html.parser").find_all("div")[0]

    name = Page.Converter(page)._extract_macro_param_from_storage(el, "drawio", "diagramName")

    assert name == "first"
