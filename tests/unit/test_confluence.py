"""Unit tests for confluence module."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.confluence import Folder
from confluence_markdown_exporter.confluence import get_folder_by_id
from confluence_markdown_exporter.confluence import get_folder_children


class TestGetFolderById:
    """Test cases for get_folder_by_id function."""

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_successful_fetch(self, mock_confluence: MagicMock) -> None:
        """Test successful folder fetch."""
        mock_response = {
            "id": "123456",
            "title": "Test Folder",
            "type": "folder",
            "spaceId": "TESTSPACE",
        }
        mock_confluence.get.return_value = mock_response

        result = get_folder_by_id("123456")

        assert result == mock_response
        mock_confluence.get.assert_called_once_with("api/v2/folders/123456")

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_folder_not_found(self, mock_confluence: MagicMock) -> None:
        """Test folder not found raises error."""
        mock_confluence.get.return_value = None

        from atlassian.errors import ApiNotFoundError

        with pytest.raises(ApiNotFoundError, match="not found or not accessible"):
            get_folder_by_id("invalid_id")


class TestGetFolderChildren:
    """Test cases for get_folder_children function."""

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_fetch_children_single_page(self, mock_confluence: MagicMock) -> None:
        """Test fetching children with single page result."""
        mock_response = {
            "results": [
                {"id": "111", "type": "page", "title": "Test Page 1"},
                {"id": "222", "type": "page", "title": "Test Page 2"},
            ],
            "_links": {},
        }
        mock_confluence.get.return_value = mock_response

        result = get_folder_children("123456")

        assert len(result) == 2
        assert result[0]["id"] == "111"
        assert result[1]["id"] == "222"
        mock_confluence.get.assert_called_once()

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_fetch_children_with_pagination(self, mock_confluence: MagicMock) -> None:
        """Test fetching children with pagination."""
        # First page
        mock_response_1 = {
            "results": [{"id": "111", "type": "page", "title": "Page 1"}],
            "_links": {"next": "/api/v2/folders/123/children?cursor=abc123"},
        }
        # Second page
        mock_response_2 = {
            "results": [{"id": "222", "type": "page", "title": "Page 2"}],
            "_links": {},
        }

        mock_confluence.get.side_effect = [mock_response_1, mock_response_2]

        result = get_folder_children("123456")

        assert len(result) == 2
        assert result[0]["id"] == "111"
        assert result[1]["id"] == "222"
        assert mock_confluence.get.call_count == 2

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_fetch_children_empty_folder(self, mock_confluence: MagicMock) -> None:
        """Test fetching children from empty folder."""
        mock_response = {"results": [], "_links": {}}
        mock_confluence.get.return_value = mock_response

        result = get_folder_children("123456")

        assert len(result) == 0

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_fetch_children_http_error_404(self, mock_confluence: MagicMock) -> None:
        """Test handling 404 error when fetching children."""
        from requests import HTTPError

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_confluence.get.side_effect = HTTPError(response=mock_response)

        result = get_folder_children("invalid_id")

        assert len(result) == 0


class TestFolderClass:
    """Test cases for Folder class."""

    @patch("confluence_markdown_exporter.confluence.Space.from_key")
    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_from_json(self, mock_confluence: MagicMock, mock_space_from_key: MagicMock) -> None:
        """Test creating Folder from JSON."""
        from confluence_markdown_exporter.confluence import Space

        mock_space = Space(key="TESTSPACE", name="Test Space", description="", homepage=0)
        mock_space_from_key.return_value = mock_space
        mock_confluence.get_space.return_value = {"key": "TESTSPACE", "name": "Test Space"}

        folder_data = {
            "id": "123456",
            "title": "Test Folder",
            "type": "folder",
            "spaceId": "TESTSPACE",
        }

        folder = Folder.from_json(folder_data)

        assert folder.id == "123456"
        assert folder.title == "Test Folder"

    @patch("confluence_markdown_exporter.confluence.Space.from_key")
    @patch("confluence_markdown_exporter.confluence.confluence")
    @patch("confluence_markdown_exporter.confluence.get_folder_by_id")
    def test_from_id(
        self,
        mock_get_folder: MagicMock,
        mock_confluence: MagicMock,
        mock_space_from_key: MagicMock,
    ) -> None:
        """Test creating Folder from ID."""
        from confluence_markdown_exporter.confluence import Space

        mock_space = Space(key="TESTSPACE", name="Test Space", description="", homepage=0)
        mock_space_from_key.return_value = mock_space

        mock_get_folder.return_value = {
            "id": "123456",
            "title": "Test Folder",
            "type": "folder",
            "spaceId": "TESTSPACE",
        }

        mock_confluence.get_space.return_value = {"key": "TESTSPACE", "name": "Test Space"}

        folder = Folder.from_id("123456")

        assert folder.id == "123456"
        assert folder.title == "Test Folder"
        mock_get_folder.assert_called_once_with("123456")

    @patch("confluence_markdown_exporter.confluence.Folder.from_id")
    @patch("confluence_markdown_exporter.confluence.settings")
    def test_from_url_spaces_folders_pattern(
        self, mock_settings: MagicMock, mock_from_id: MagicMock
    ) -> None:
        """Test creating Folder from URL with /spaces/SPACE/folders/ pattern."""
        mock_settings.auth.confluence.url = "https://company.atlassian.net/"

        mock_folder = MagicMock()
        mock_from_id.return_value = mock_folder

        url = "https://company.atlassian.net/wiki/spaces/MYSPACE/folders/123456"
        result = Folder.from_url(url)

        mock_from_id.assert_called_once_with("123456")
        assert result == mock_folder

    @patch("confluence_markdown_exporter.confluence.Folder.from_id")
    @patch("confluence_markdown_exporter.confluence.settings")
    def test_from_url_pages_folders_pattern(
        self, mock_settings: MagicMock, mock_from_id: MagicMock
    ) -> None:
        """Test creating Folder from URL with /pages/folders/ pattern."""
        mock_settings.auth.confluence.url = "https://company.atlassian.net/"

        mock_folder = MagicMock()
        mock_from_id.return_value = mock_folder

        url = "https://company.atlassian.net/wiki/spaces/MYSPACE/pages/folders/789012"
        result = Folder.from_url(url)

        mock_from_id.assert_called_once_with("789012")
        assert result == mock_folder

    @patch("confluence_markdown_exporter.confluence.Folder.from_id")
    @patch("confluence_markdown_exporter.confluence.settings")
    def test_from_url_generic_folders_pattern(
        self, mock_settings: MagicMock, mock_from_id: MagicMock
    ) -> None:
        """Test creating Folder from URL with generic /folders/ pattern."""
        mock_settings.auth.confluence.url = "https://company.atlassian.net/"

        mock_folder = MagicMock()
        mock_from_id.return_value = mock_folder

        url = "https://company.atlassian.net/wiki/x/folders/345678"
        result = Folder.from_url(url)

        mock_from_id.assert_called_once_with("345678")
        assert result == mock_folder

    @patch("confluence_markdown_exporter.confluence.settings")
    def test_from_url_invalid_url(self, mock_settings: MagicMock) -> None:
        """Test that invalid folder URL raises ValueError."""
        mock_settings.auth.confluence.url = "https://company.atlassian.net/"

        with pytest.raises(ValueError, match="Could not parse folder URL"):
            Folder.from_url("https://company.atlassian.net/wiki/invalid/path")

    @patch("confluence_markdown_exporter.confluence.get_folder_children")
    def test_pages_property_with_pages(self, mock_get_children: MagicMock) -> None:
        """Test pages property returns page IDs."""
        from confluence_markdown_exporter.confluence import Space

        mock_space = Space(key="TEST", name="Test", description="", homepage=0)

        mock_get_children.return_value = [
            {"id": "111", "type": "page"},
            {"id": "222", "type": "page"},
        ]

        folder = Folder(id="123", title="Test", space=mock_space)
        page_ids = folder.pages

        assert len(page_ids) == 2
        assert 111 in page_ids
        assert 222 in page_ids

    @patch("confluence_markdown_exporter.confluence.get_folder_children")
    def test_pages_property_empty_folder(self, mock_get_children: MagicMock) -> None:
        """Test pages property with empty folder."""
        from confluence_markdown_exporter.confluence import Space

        mock_space = Space(key="TEST", name="Test", description="", homepage=0)

        mock_get_children.return_value = []

        folder = Folder(id="123", title="Test", space=mock_space)
        page_ids = folder.pages

        assert len(page_ids) == 0

    @patch("confluence_markdown_exporter.confluence.export_pages")
    @patch("confluence_markdown_exporter.confluence.get_folder_children")
    def test_export_with_pages(
        self,
        mock_get_children: MagicMock,
        mock_export_pages: MagicMock,
    ) -> None:
        """Test exporting folder with pages."""
        from confluence_markdown_exporter.confluence import Space

        mock_space = Space(key="TEST", name="Test", description="", homepage=0)

        mock_get_children.return_value = [
            {"id": "111", "type": "page"},
            {"id": "222", "type": "page"},
        ]

        folder = Folder(id="123", title="Test", space=mock_space)
        folder.export()

        mock_export_pages.assert_called_once()
        called_page_ids = mock_export_pages.call_args[0][0]
        assert len(called_page_ids) == 2
        assert 111 in called_page_ids
        assert 222 in called_page_ids

    @patch("confluence_markdown_exporter.confluence.export_pages")
    @patch("confluence_markdown_exporter.confluence.get_folder_children")
    def test_export_empty_folder(
        self,
        mock_get_children: MagicMock,
        mock_export_pages: MagicMock,
    ) -> None:
        """Test exporting empty folder logs warning."""
        from confluence_markdown_exporter.confluence import Space

        mock_space = Space(key="TEST", name="Test", description="", homepage=0)

        mock_get_children.return_value = []

        folder = Folder(id="123", title="Test Folder", space=mock_space)

        with patch("confluence_markdown_exporter.confluence.logger") as mock_logger:
            folder.export()
            mock_logger.warning.assert_called_once()
            assert "No pages found" in mock_logger.warning.call_args[0][0]

        mock_export_pages.assert_called_once_with([])

