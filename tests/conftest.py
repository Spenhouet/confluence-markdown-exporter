"""Shared test fixtures and configuration for confluence-markdown-exporter tests."""

import importlib
import sys
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

# Store original functions before any patching
_original_get_confluence = None
_original_get_jira = None


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Configure pytest and mock API clients before test collection."""
    import confluence_markdown_exporter.api_clients

    global _original_get_confluence, _original_get_jira  # noqa: PLW0603

    # Save the original functions
    _original_get_confluence = confluence_markdown_exporter.api_clients.get_confluence_instance
    _original_get_jira = confluence_markdown_exporter.api_clients.get_jira_instance

    # Create mock objects that will be returned by the wrapper
    mock_confluence = MagicMock()
    mock_confluence.get_all_spaces.return_value = []

    mock_jira = MagicMock()

    # Replace with wrapper functions that return mocks
    confluence_markdown_exporter.api_clients.get_confluence_instance = lambda: mock_confluence
    confluence_markdown_exporter.api_clients.get_jira_instance = lambda: mock_jira


def pytest_unconfigure(config: pytest.Config) -> None:  # noqa: ARG001
    """Restore original functions after test session."""
    import confluence_markdown_exporter.api_clients

    global _original_get_confluence, _original_get_jira  # noqa: PLW0602

    if _original_get_confluence:
        confluence_markdown_exporter.api_clients.get_confluence_instance = _original_get_confluence
    if _original_get_jira:
        confluence_markdown_exporter.api_clients.get_jira_instance = _original_get_jira


@pytest.fixture(autouse=True)
def restore_api_functions_for_specific_tests(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Restore original API functions for api_clients tests that test those functions.

    This allows those tests to properly mock and test the actual function behavior.
    """
    import confluence_markdown_exporter.api_clients

    global _original_get_confluence, _original_get_jira  # noqa: PLW0602

    # Check if this is a test that needs the original functions
    is_api_client_function_test = (
        "test_api_clients.py" in str(request.fspath) and
        ("TestGetConfluenceInstance" in request.node.nodeid or
         "TestGetJiraInstance" in request.node.nodeid)
    )

    if is_api_client_function_test and _original_get_confluence and _original_get_jira:
        # Temporarily restore original functions
        confluence_markdown_exporter.api_clients.get_confluence_instance = _original_get_confluence
        confluence_markdown_exporter.api_clients.get_jira_instance = _original_get_jira

        # Force reimport in the test module to pick up the restored functions
        # This is needed because the test module imported the mocked versions at collection time
        if "tests.unit.test_api_clients" in sys.modules:
            importlib.reload(sys.modules["tests.unit.test_api_clients"])

    yield

    # Re-apply mocks after the test
    if is_api_client_function_test:
        mock_confluence = MagicMock()
        mock_confluence.get_all_spaces.return_value = []
        mock_jira = MagicMock()

        confluence_markdown_exporter.api_clients.get_confluence_instance = lambda: mock_confluence
        confluence_markdown_exporter.api_clients.get_jira_instance = lambda: mock_jira


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
