"""Unit tests for confluence module URL resolution."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.confluence import _get_web_url


class MockPage:
    """Minimal page object for Converter tests."""

    def __init__(self) -> None:
        self.id = "test-page"
        self.title = "Test Page"
        self.html = ""
        self.web_url = "https://example.atlassian.net/wiki/spaces/TEST/pages/123/Test+Page"
        self.labels = []
        self.ancestors = []

    def get_attachment_by_file_id(self, file_id: str) -> None:
        return None


@pytest.fixture
def converter() -> Page.Converter:
    return Page.Converter(MockPage())


class TestAnchorLinkConversion:
    """Internal anchor links must use the href value for slug, not link text."""

    def test_anchor_uses_href_not_link_text(self, converter: Page.Converter) -> None:
        """Anchor slug derived from href, not display text."""
        html = '<a href="#1.-Request-Service">request service</a>'
        result = converter.convert(html).strip()
        assert result == "[request service](#1-request-service)"

    def test_anchor_plain_heading(self, converter: Page.Converter) -> None:
        """Simple heading anchor round-trips correctly."""
        html = '<a href="#My-Heading">My Heading</a>'
        result = converter.convert(html).strip()
        assert result == "[My Heading](#my-heading)"

    def test_anchor_with_numbers_and_punctuation(self, converter: Page.Converter) -> None:
        """Numbered heading anchors match GitHub markdown anchor format."""
        html = '<a href="#2.-Setup-Steps">setup steps</a>'
        result = converter.convert(html).strip()
        assert result == "[setup steps](#2-setup-steps)"

    def test_wiki_anchor_uses_link_text(self, converter: Page.Converter) -> None:
        """Wiki links use link text for slug, not href."""
        from unittest.mock import patch

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.page_href = "wiki"
            html = '<a href="#1.-Request-Service">Request Service</a>'
            result = converter.convert(html).strip()
        assert result == "[[#Request Service]]"


class TestPageWebUrl:
    """Original Confluence page URL handling."""

    def test_get_web_url_combines_base_and_webui(self) -> None:
        data = {
            "_links": {
                "base": "https://example.atlassian.net/wiki",
                "webui": "/spaces/TEST/pages/123/Test+Page",
            }
        }

        assert _get_web_url(data) == (
            "https://example.atlassian.net/wiki/spaces/TEST/pages/123/Test+Page"
        )

    def test_get_web_url_returns_empty_string_when_links_are_missing(self) -> None:
        assert _get_web_url({}) == ""

    def test_markdown_includes_web_url_when_enabled(self) -> None:
        page = MockPage()
        page.html = "<p>Hello</p>"

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.include_confluence_page_url = True
            mock_settings.export.page_breadcrumbs = False
            result = Page.Converter(page).markdown

        assert (
            "Confluence page: "
            "https://example.atlassian.net/wiki/spaces/TEST/pages/123/Test+Page"
        ) in result


class TestPageFromUrl:
    """Test cases for Page.from_url."""

    def test_from_url_prefers_page_id_query_parameter_for_legacy_server_url(self) -> None:
        """Legacy Server/DC viewpage.action links should resolve by pageId."""
        page_url = (
            "https://wiki.example.com/pages/viewpage.action"
            "?pageId=317425825&src=contextnavpagetreemode"
        )

        with (
            patch("confluence_markdown_exporter.confluence.get_confluence_instance"),
            patch("confluence_markdown_exporter.confluence.Page.from_id") as mock_from_id,
            patch("confluence_markdown_exporter.confluence.get_thread_confluence") as mock_client,
        ):
            mock_from_id.return_value = "page"

            result = Page.from_url(page_url)

        assert result == "page"
        mock_from_id.assert_called_once_with(317425825, "https://wiki.example.com")
        mock_client.assert_not_called()
