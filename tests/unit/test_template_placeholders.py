"""Test that <template> placeholders are escaped for Obsidian compatibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from confluence_markdown_exporter.confluence import Page


class TestTemplatePlaceholderEscaping:
    """Test that angle-bracket template placeholders are escaped for Obsidian."""

    @pytest.fixture
    def converter(self) -> Page.Converter:
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

    def test_multi_word_placeholder_escaped(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("Replace <medical device> here.")
        assert result == "Replace \\<medical device\\> here."

    def test_allcaps_placeholder_escaped(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders(
            "Page: Literature Search Report: <TOPIC>"
        )
        assert result == "Page: Literature Search Report: \\<TOPIC\\>"

    def test_complex_placeholder_escaped(self, converter: Page.Converter) -> None:
        text = "the <(e.g., clinical performance or state of the art)> of <medical device>."
        result = converter._escape_template_placeholders(text)
        assert "\\<(e.g., clinical performance or state of the art)\\>" in result
        assert "\\<medical device\\>" in result

    def test_placeholder_with_slash_in_name_escaped(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders(
            "the <medical device/equivalent device> here"
        )
        assert "\\<medical device/equivalent device\\>" in result

    def test_fake_closing_tag_placeholder_escaped(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("use the </insert excerpt> function")
        assert "\\</insert excerpt\\>" in result

    def test_br_tag_preserved(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("text<br/>more text")
        assert result == "text<br/>more text"

    def test_br_with_space_preserved(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("text<br />more text")
        assert result == "text<br />more text"

    def test_br_uppercase_preserved(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("text<BR/>more text")
        assert result == "text<BR/>more text"

    def test_closing_html_tag_preserved(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("</div>")
        assert result == "</div>"

    def test_inline_code_not_modified(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("Use `<TOPIC>` here.")
        assert result == "Use `<TOPIC>` here."

    def test_fenced_code_block_not_modified(self, converter: Page.Converter) -> None:
        text = "before\n```\n<TOPIC>\n<medical device>\n```\nafter"
        result = converter._escape_template_placeholders(text)
        assert "<TOPIC>" in result
        assert "<medical device>" in result
        assert "\\<TOPIC\\>" not in result

    def test_tilde_fenced_code_block_not_modified(self, converter: Page.Converter) -> None:
        text = "before\n~~~\n<TOPIC>\n~~~\nafter"
        result = converter._escape_template_placeholders(text)
        assert "<TOPIC>" in result

    def test_text_outside_code_block_still_escaped(self, converter: Page.Converter) -> None:
        text = "Replace <TOPIC> here.\n```\n<TOPIC>\n```\nAlso <medical device>."
        result = converter._escape_template_placeholders(text)
        lines = result.split("\n")
        assert "\\<TOPIC\\>" in lines[0]
        assert "<TOPIC>" in lines[2]
        assert "\\<medical device\\>" in lines[4]

    def test_https_autolink_preserved(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders(
            "URL: <https://api.airamed.de/v1/udi>."
        )
        assert result == "URL: <https://api.airamed.de/v1/udi>."

    def test_http_autolink_preserved(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("see <http://example.com/path?q=1>")
        assert result == "see <http://example.com/path?q=1>"

    def test_mailto_autolink_preserved(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("contact <mailto:foo@bar.com>")
        assert result == "contact <mailto:foo@bar.com>"

    def test_email_autolink_preserved(self, converter: Page.Converter) -> None:
        result = converter._escape_template_placeholders("contact <foo@bar.com> now")
        assert result == "contact <foo@bar.com> now"

    def test_autolink_with_space_still_escaped(self, converter: Page.Converter) -> None:
        # Not a valid autolink (contains whitespace) — treat as placeholder
        result = converter._escape_template_placeholders("<https://x y>")
        assert result == "\\<https://x y\\>"
