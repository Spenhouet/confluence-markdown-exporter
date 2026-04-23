"""Unit tests for confluence module URL resolution."""

from unittest.mock import patch

from confluence_markdown_exporter.confluence import Page


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
