"""Test that Unicode whitespace (especially &nbsp;) is preserved in inline formatting."""

import pytest
from bs4 import BeautifulSoup


class TestNbspPreservation:
    """Test that non-breaking spaces and other Unicode whitespace are preserved."""

    @pytest.fixture
    def converter(self):
        """Create a minimal Page object with a Converter for testing."""
        from confluence_markdown_exporter.confluence import Page

        # Create a minimal page object for testing
        class MockPage:
            def __init__(self):
                self.id = "test-page"
                self.title = "Test Page"
                self.html = ""
                self.labels = []
                self.ancestors = []

            def get_attachment_by_file_id(self, file_id):
                return None

        page = MockPage()
        return Page.Converter(page)

    def test_em_with_leading_nbsp(self, converter):
        """Test <em>&nbsp;text</em> converts to ' *text*' (space before asterisk)."""
        html = "<em>&nbsp;text</em>"
        result = converter.convert(html).strip()
        assert result == "*text*", f"Expected '*text*' but got '{result}'"
        # The space is preserved in the conversion
        html_with_context = "word<em>&nbsp;text</em>"
        result_with_context = converter.convert(html_with_context).strip()
        assert "word *text*" in result_with_context or "word  *text*" in result_with_context

    def test_em_with_trailing_nbsp(self, converter):
        """Test <em>text&nbsp;</em> converts to '*text* ' (space after asterisk)."""
        html = "<em>text&nbsp;</em>"
        result = converter.convert(html).strip()
        assert result == "*text*", f"Expected '*text*' but got '{result}'"
        # The space is preserved in the conversion
        html_with_context = "<em>text&nbsp;</em>word"
        result_with_context = converter.convert(html_with_context).strip()
        assert "*text* word" in result_with_context or "*text*  word" in result_with_context

    def test_em_with_both_nbsp(self, converter):
        """Test <em>&nbsp;text&nbsp;</em> preserves both spaces."""
        html = "word<em>&nbsp;text&nbsp;</em>end"
        result = converter.convert(html).strip()
        # Should have spaces around the emphasis
        assert "*text*" in result
        # Check that there's space before and after
        assert "word *text* end" in result or "word  *text*  end" in result

    def test_strong_with_leading_nbsp(self, converter):
        """Test <strong>&nbsp;text</strong> converts to ' **text**'."""
        html = "word<strong>&nbsp;text</strong>"
        result = converter.convert(html).strip()
        assert "**text**" in result
        assert "word **text**" in result or "word  **text**" in result

    def test_strong_with_trailing_nbsp(self, converter):
        """Test <strong>text&nbsp;</strong> converts to '**text** '."""
        html = "<strong>text&nbsp;</strong>word"
        result = converter.convert(html).strip()
        assert "**text**" in result
        assert "**text** word" in result or "**text**  word" in result

    def test_code_with_leading_nbsp(self, converter):
        """Test <code>&nbsp;text</code> converts to ' `text`'."""
        html = "word<code>&nbsp;text</code>"
        result = converter.convert(html).strip()
        assert "`text`" in result
        assert "word `text`" in result or "word  `text`" in result

    def test_code_with_trailing_nbsp(self, converter):
        """Test <code>text&nbsp;</code> converts to '`text` '."""
        html = "<code>text&nbsp;</code>word"
        result = converter.convert(html).strip()
        assert "`text`" in result
        assert "`text` word" in result or "`text`  word" in result

    def test_i_tag_with_nbsp(self, converter):
        """Test <i>&nbsp;text</i> (italic alias) preserves space."""
        html = "word<i>&nbsp;text</i>"
        result = converter.convert(html).strip()
        assert "*text*" in result
        assert "word *text*" in result or "word  *text*" in result

    def test_b_tag_with_nbsp(self, converter):
        """Test <b>&nbsp;text</b> (bold alias) preserves space."""
        html = "word<b>&nbsp;text</b>"
        result = converter.convert(html).strip()
        assert "**text**" in result
        assert "word **text**" in result or "word  **text**" in result

    def test_real_world_confluence_example(self, converter):
        """Test the actual example from MOSART Audio.md."""
        html = "property<em>&nbsp;JungerRoot</em> ."
        result = converter.convert(html).strip()
        # Should NOT be "property*JungerRoot*" (missing space)
        assert "property*JungerRoot*" not in result, "Space was lost!"
        # Should be "property *JungerRoot*" or "property  *JungerRoot*"
        assert "*JungerRoot*" in result
        assert "property" in result

    def test_multiple_nbsp_in_sequence(self, converter):
        """Test multiple &nbsp; entities in a row."""
        html = "word<em>&nbsp;&nbsp;text</em>"
        result = converter.convert(html).strip()
        # Multiple nbsp should become multiple spaces
        assert "*text*" in result or "* text*" in result

    def test_mixed_whitespace(self, converter):
        """Test normal spaces work alongside nbsp."""
        html = "see <em>figure 1</em> below"
        result = converter.convert(html).strip()
        assert "see *figure 1* below" in result

    def test_normalize_helper_function(self, converter):
        """Test the _normalize_unicode_whitespace helper directly."""
        # Test with various Unicode whitespace characters
        test_text = "\xa0text\xa0"  # \xa0 is nbsp

        # Before normalization
        assert "\xa0" in test_text

        # Normalize
        normalized_text = converter._normalize_unicode_whitespace(test_text)

        # After normalization - nbsp should be replaced with regular space
        assert "\xa0" not in normalized_text, "nbsp should be replaced"
        assert normalized_text.strip() == "text", "Text should be preserved"
        # Spaces should now be regular spaces
        assert normalized_text.startswith(" "), "Leading space should be preserved"
        assert normalized_text.endswith(" "), "Trailing space should be preserved"

    def test_unicode_em_space(self, converter):
        """Test that EM SPACE (\u2003) is also normalized."""
        test_text = "\u2003text"  # EM SPACE

        normalized_text = converter._normalize_unicode_whitespace(test_text)

        assert "\u2003" not in normalized_text, "EM SPACE should be replaced"
        assert normalized_text.strip() == "text"
        assert normalized_text.startswith(" "), "Space should be preserved as regular space"

    def test_unicode_thin_space(self, converter):
        """Test that THIN SPACE (\u2009) is normalized."""
        test_text = "text\u2009end"  # THIN SPACE

        normalized_text = converter._normalize_unicode_whitespace(test_text)

        assert "\u2009" not in normalized_text, "THIN SPACE should be replaced"
        assert "text end" == normalized_text, "Space should be preserved as regular space"

    def test_preserves_newlines_and_tabs(self, converter):
        """Test that normal whitespace (newlines, tabs) are NOT affected."""
        test_text = "text\nwith\nnewlines"

        normalized_text = converter._normalize_unicode_whitespace(test_text)

        # Newlines should be preserved
        assert "\n" in normalized_text
        assert normalized_text == test_text, "Regular whitespace should not be touched"

    def test_no_modification_when_no_unicode_whitespace(self, converter):
        """Test that text without Unicode whitespace is not modified."""
        test_text = "normal text"

        normalized_text = converter._normalize_unicode_whitespace(test_text)

        assert normalized_text == test_text, "Normal text should not be modified"
