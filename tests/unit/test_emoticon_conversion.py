"""Test that Confluence emoticon img tags are converted to unicode emoji."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from confluence_markdown_exporter.confluence import Page


@pytest.fixture
def converter() -> Page.Converter:
    from confluence_markdown_exporter.confluence import Page

    class MockPage:
        def __init__(self) -> None:
            self.id = "test-page"
            self.title = "Test Page"
            self.html = ""
            self.labels = []
            self.ancestors = []

        def get_attachment_by_file_id(self, file_id: str) -> None:
            return None

    return Page.Converter(MockPage())


class TestEmoticonConversion:
    def test_atlassian_check_mark(self, converter: Page.Converter) -> None:
        html = (
            '<img class="emoticon emoticon-tick"'
            ' data-emoji-id="atlassian-check_mark"'
            ' data-emoji-fallback=":check_mark:"'
            ' data-emoji-shortname=":check_mark:"'
            ' alt="(tick)" />'
        )
        assert converter.convert(html).strip() == "✅"

    def test_atlassian_cross_mark(self, converter: Page.Converter) -> None:
        html = (
            '<img class="emoticon emoticon-cross"'
            ' data-emoji-id="atlassian-cross_mark"'
            ' data-emoji-fallback=":cross_mark:"'
            ' data-emoji-shortname=":cross_mark:"'
            ' alt="(error)" />'
        )
        assert converter.convert(html).strip() == "❌"

    def test_unicode_emoji_by_hex_id(self, converter: Page.Converter) -> None:
        html = (
            '<img class="emoticon emoticon-blue-star"'
            ' data-emoji-id="1f6e0"'
            ' data-emoji-fallback="\U0001f6e0️"'
            ' data-emoji-shortname=":tools:"'
            ' alt="(blue star)" />'
        )
        assert converter.convert(html).strip() == "\U0001f6e0️"

    def test_unicode_emoji_fallback_direct(self, converter: Page.Converter) -> None:
        html = (
            '<img class="emoticon"'
            ' data-emoji-id="1f600"'
            ' data-emoji-fallback="\U0001f600"'
            ' alt="smile" />'
        )
        assert converter.convert(html).strip() == "\U0001f600"

    def test_non_emoticon_img_unchanged(self, converter: Page.Converter) -> None:
        html = '<img src="http://example.com/image.png" alt="photo" />'
        result = converter.convert(html).strip()
        assert "emoticon" not in result
        assert "example.com" in result

    def test_emoticon_inline_in_text(self, converter: Page.Converter) -> None:
        html = (
            'Status: <img class="emoticon emoticon-tick"'
            ' data-emoji-id="atlassian-check_mark"'
            ' data-emoji-fallback=":check_mark:"'
            ' alt="(tick)" /> Done'
        )
        result = converter.convert(html).strip()
        assert "✅" in result
        assert "Done" in result
