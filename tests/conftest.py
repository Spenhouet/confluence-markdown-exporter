"""Shared test fixtures and configuration for confluence-markdown-exporter tests."""

import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import AnyHttpUrl
from pydantic import SecretStr

from confluence_markdown_exporter.utils.app_data_store import ApiDetails
from confluence_markdown_exporter.utils.app_data_store import AuthConfig
from confluence_markdown_exporter.utils.app_data_store import ConfigModel
from confluence_markdown_exporter.utils.app_data_store import ConnectionConfig
from confluence_markdown_exporter.utils.app_data_store import ExportConfig


@pytest.fixture
def temp_config_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_confluence_client() -> MagicMock:
    """Create a mock Confluence client for testing."""
    mock_client = MagicMock()
    mock_client.get_all_spaces.return_value = [
        {"key": "TEST", "name": "Test Space", "id": "123456"}
    ]
    mock_client.get_page_by_id.return_value = {
        "id": "123456",
        "title": "Test Page",
        "body": {"storage": {"value": "<p>Test content</p>"}},
        "space": {"key": "TEST"},
        "version": {"number": 1},
    }
    return mock_client


@pytest.fixture
def mock_jira_client() -> MagicMock:
    """Create a mock Jira client for testing."""
    mock_client = MagicMock()
    mock_client.get_all_projects.return_value = [
        {"key": "TEST", "name": "Test Project", "id": "10000"}
    ]
    mock_client.get_issue.return_value = {
        "key": "TEST-123",
        "fields": {
            "summary": "Test Issue",
            "description": "Test description",
            "status": {"name": "Open"},
        },
    }
    return mock_client


@pytest.fixture
def sample_api_details() -> ApiDetails:
    """Create sample API details for testing."""
    return ApiDetails(
        url=AnyHttpUrl("https://test.atlassian.net/"),
        username=SecretStr("test@example.com"),
        api_token=SecretStr("test-token"),
        pat=SecretStr("test-pat"),
    )


@pytest.fixture
def sample_connection_config() -> ConnectionConfig:
    """Create sample connection configuration for testing."""
    return ConnectionConfig(
        backoff_and_retry=True,
        backoff_factor=2,
        max_backoff_seconds=60,
        max_backoff_retries=5,
        retry_status_codes=[413, 429, 502, 503, 504],
        verify_ssl=True,
    )


@pytest.fixture
def sample_config_model(
    sample_api_details: ApiDetails,
    sample_connection_config: ConnectionConfig,
    temp_config_dir: Path,
) -> ConfigModel:
    """Create sample configuration for testing."""
    auth_config = AuthConfig(
        confluence=sample_api_details,
        jira=sample_api_details,
    )

    export_config = ExportConfig(
        output_path=temp_config_dir / "output",
    )

    return ConfigModel(
        auth=auth_config,
        export=export_config,
        connection_config=sample_connection_config,
    )


@pytest.fixture
def confluence_page_response() -> dict[str, Any]:
    """Sample Confluence page response for testing."""
    return {
        "id": "123456",
        "type": "page",
        "status": "current",
        "title": "Test Page",
        "space": {"key": "TEST", "name": "Test Space", "id": "123"},
        "version": {
            "number": 1,
            "when": "2023-01-01T00:00:00.000Z",
            "by": {"displayName": "Test User", "username": "testuser"},
        },
        "ancestors": [],
        "children": {"page": {"results": [], "size": 0}},
        "descendants": {"page": {"results": [], "size": 0}},
        "body": {
            "storage": {
                "value": (
                    "<h1>Test Heading</h1><p>Test content with <strong>bold</strong> text.</p>"
                ),
                "representation": "storage",
            }
        },
        "_links": {
            "webui": "/spaces/TEST/pages/123456/Test+Page",
            "base": "https://test.atlassian.net/wiki",
        },
    }


@pytest.fixture
def confluence_space_response() -> dict[str, Any]:
    """Sample Confluence space response for testing."""
    return {
        "id": "123",
        "key": "TEST",
        "name": "Test Space",
        "description": {"plain": {"value": "A test space"}},
        "homepage": {"id": "123456"},
        "_links": {
            "webui": "/spaces/TEST",
            "base": "https://test.atlassian.net/wiki",
        },
    }


@pytest.fixture
def jira_issue_response() -> dict[str, Any]:
    """Sample Jira issue response for testing."""
    return {
        "id": "10000",
        "key": "TEST-123",
        "fields": {
            "summary": "Test Issue Summary",
            "description": "This is a test issue description",
            "status": {"name": "Open", "id": "1"},
            "priority": {"name": "Medium", "id": "3"},
            "issuetype": {"name": "Bug", "id": "1"},
            "created": "2023-01-01T00:00:00.000+0000",
            "updated": "2023-01-01T12:00:00.000+0000",
        },
    }
