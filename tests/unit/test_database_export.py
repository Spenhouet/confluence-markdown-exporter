"""Unit tests for Confluence Cloud database export features."""

import json
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from requests import HTTPError

from confluence_markdown_exporter.api_clients import ConfluenceRef
from confluence_markdown_exporter.api_clients import parse_confluence_path
from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.confluence import Space
from confluence_markdown_exporter.confluence import Version
from confluence_markdown_exporter.confluence import _extract_adf_text
from confluence_markdown_exporter.main import app
from confluence_markdown_exporter.utils.app_data_store import ExportConfig

BASE_URL = "https://example.atlassian.net"
MODULE = "confluence_markdown_exporter.confluence"


def _sample_fields() -> list[dict]:
    return [
        {"id": "title", "name": "Task Name", "type": "text"},
        {"id": "status", "name": "Status", "type": "select"},
        {"id": "done", "name": "Done", "type": "checkbox"},
        {"id": "due", "name": "Due Date", "type": "date"},
        {"id": "count", "name": "Count", "type": "number"},
        {"id": "link", "name": "Link", "type": "hyperlink"},
        {"id": "assignee", "name": "Assignee", "type": "user"},
        {"id": "issue", "name": "Jira Issue", "type": "jiraIssue"},
        {"id": "page", "name": "Related Page", "type": "pageLink"},
    ]


def _sample_entries() -> list[dict]:
    return [
        {
            "id": "entry-1",
            "databaseId": "42",
            "values": {
                "title": {"type": "text", "plain": "First Task", "rich": None},
                "status": {"type": "select", "value": [{"id": "s1", "label": "In Progress"}]},
                "done": {"type": "checkbox", "value": False},
                "due": {"type": "date", "value": "2026-12-01"},
                "count": {"type": "number", "value": "15"},
                "link": {
                    "type": "hyperlink",
                    "value": [{"url": "https://example.com", "label": "Example"}],
                },
                "assignee": {"type": "user", "value": [{"accountId": "user-123"}]},
                "issue": {"type": "jiraIssue", "value": [{"key": "PROJ-101"}]},
                "page": {"type": "pageLink", "value": [{"contentId": "999"}]},
            },
        },
        {
            "id": "entry-2",
            "databaseId": "42",
            "values": {
                "title": {
                    "type": "text",
                    "plain": None,
                    "rich": {
                        "type": "doc",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Second Task"}],
                            }
                        ],
                    },
                },
                "status": {"type": "select", "value": [{"id": "s2", "label": "Done"}]},
                "done": {"type": "checkbox", "value": True},
                "due": {"type": "date", "value": "2026-11-20"},
                "count": {"type": "number", "value": "3"},
                "link": {"type": "hyperlink", "value": [{"url": "https://test.org", "label": ""}]},
                "assignee": {"type": "user", "value": []},
                "issue": {"type": "jiraIssue", "value": []},
                "page": {"type": "pageLink", "value": []},
            },
        },
    ]


def _make_database_page(page_id: int = 42, title: str = "Project Tasks") -> Page:
    space = Space(base_url=BASE_URL, key="DEV", name="Development", description="", homepage=None)
    from confluence_markdown_exporter.confluence import _database_placeholder

    web_url = f"{BASE_URL}/wiki/spaces/DEV/database/{page_id}"
    placeholder = _database_placeholder(title, web_url)
    return Page(
        base_url=BASE_URL,
        id=page_id,
        type="database",
        title=title,
        web_url=web_url,
        tiny_url="",
        space=space,
        body=placeholder,
        body_export=placeholder,
        editor2="",
        labels=[],
        attachments=[],
        ancestors=[],
        version=Version.from_json({"number": 1}),
    )


class TestDatabaseUrlParsing:
    def test_parse_database_url_with_space(self) -> None:
        ref = parse_confluence_path("/wiki/spaces/DEV/database/42/Project+Tasks")
        assert ref == ConfluenceRef(space_key="DEV", database_id=42, page_title="Project Tasks")

    def test_parse_database_url_without_title(self) -> None:
        ref = parse_confluence_path("/wiki/spaces/DEV/database/42")
        assert ref == ConfluenceRef(space_key="DEV", database_id=42, page_title=None)

    def test_parse_database_url_without_space(self) -> None:
        ref = parse_confluence_path("/wiki/database/42/Project+Tasks")
        assert ref is not None
        assert ref.database_id == 42
        assert ref.page_title == "Project Tasks"

    def test_parse_database_url_simple(self) -> None:
        ref = parse_confluence_path("/database/42")
        assert ref is not None
        assert ref.database_id == 42


class TestDatabaseConfig:
    def test_default_config(self) -> None:
        cfg = ExportConfig()
        assert cfg.database_export == "table"
        assert cfg.database_formats == ["markdown"]
        assert cfg.database_placeholders is True

    def test_migration_from_placeholders_false(self) -> None:
        cfg = ExportConfig.model_validate({"database_placeholders": False})
        assert cfg.database_export == "none"
        assert cfg.database_placeholders is False

    def test_migration_from_placeholders_true(self) -> None:
        cfg = ExportConfig.model_validate({"database_placeholders": True})
        assert cfg.database_export == "table"
        assert cfg.database_placeholders is True

    def test_setter_database_placeholders(self) -> None:
        cfg = ExportConfig()
        cfg.database_placeholders = False
        assert cfg.database_export == "none"
        assert cfg.database_placeholders is False
        cfg.database_placeholders = True
        assert cfg.database_export == "table"


class TestExtractAdfText:
    def test_extract_nested_text(self) -> None:
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "content": [{"type": "text", "text": "Header"}],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "World!"},
                    ],
                },
            ],
        }
        text = _extract_adf_text(adf).strip()
        assert "Header" in text
        assert "Hello World!" in text


class TestDatabaseExporting:
    @patch(f"{MODULE}.settings")
    @patch(f"{MODULE}.get_thread_confluence")
    def test_export_markdown_table(
        self, mock_client_factory: MagicMock, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        mock_settings.export.output_path = tmp_path
        mock_settings.export.database_export = "table"
        mock_settings.export.database_formats = ["markdown"]
        mock_settings.export.table_format = "markdown"
        mock_settings.export.include_document_title = True
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None
        mock_settings.export.include_jira_status = False

        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"
        client.get.side_effect = lambda path: {
            "results": _sample_fields() if "fields" in path else _sample_entries()
        }
        mock_client_factory.return_value = client

        page = _make_database_page()
        with (
            patch(f"{MODULE}.User.from_accountid") as mock_user,
            patch(f"{MODULE}.JiraIssue.from_key") as mock_jira,
        ):
            mock_user.return_value = MagicMock(display_name="Alice Smith (Unlicensed)")
            mock_jira.return_value = MagicMock(
                key="PROJ-101", summary="Issue summary", status="Open"
            )

            page.export()

        out_file = tmp_path / "DEV" / "Project Tasks.md"
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "# Project Tasks" in content
        assert f"[Open Project Tasks in Confluence]({page.web_url})" in content
        assert "| Task Name" in content
        assert "First Task" in content
        assert "Second Task" in content
        assert "Alice Smith" in content
        assert "[x]" in content
        assert "[ ]" in content

    @patch(f"{MODULE}.settings")
    @patch(f"{MODULE}.get_thread_confluence")
    def test_export_html_table(
        self, mock_client_factory: MagicMock, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        mock_settings.export.output_path = tmp_path
        mock_settings.export.database_export = "table"
        mock_settings.export.database_formats = ["markdown"]
        mock_settings.export.table_format = "html"
        mock_settings.export.include_document_title = False
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"
        client.get.side_effect = lambda path: {
            "results": _sample_fields() if "fields" in path else _sample_entries()
        }
        mock_client_factory.return_value = client

        page = _make_database_page()
        page.export()

        out_file = tmp_path / "DEV" / "Project Tasks.md"
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "<table><thead><tr>" in content
        assert "<th>Task Name</th>" in content
        assert "<td>First Task</td>" in content

    @patch(f"{MODULE}.settings")
    @patch(f"{MODULE}.get_thread_confluence")
    def test_export_csv_and_json_sidecars(
        self, mock_client_factory: MagicMock, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        mock_settings.export.output_path = tmp_path
        mock_settings.export.database_export = "table"
        mock_settings.export.database_formats = ["markdown", "csv", "json"]
        mock_settings.export.table_format = "markdown"
        mock_settings.export.include_document_title = True
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"
        client.get.side_effect = lambda path: {
            "results": _sample_fields() if "fields" in path else _sample_entries()
        }
        mock_client_factory.return_value = client

        page = _make_database_page()
        page.export()

        md_file = tmp_path / "DEV" / "Project Tasks.md"
        csv_file = tmp_path / "DEV" / "Project Tasks.csv"
        json_file = tmp_path / "DEV" / "Project Tasks.json"

        assert md_file.exists()
        assert csv_file.exists()
        assert json_file.exists()

        csv_content = csv_file.read_text(encoding="utf-8")
        assert (
            "Task Name,Status,Done,Due Date,Count,Link,Assignee,Jira Issue,Related Page"
            in csv_content
        )
        assert "First Task,In Progress,false,2026-12-01,15,Example" in csv_content

        json_data = json.loads(json_file.read_text(encoding="utf-8"))
        assert json_data["id"] == "42"
        assert json_data["title"] == "Project Tasks"
        assert len(json_data["fields"]) == len(_sample_fields())
        assert len(json_data["entries"]) == len(_sample_entries())

    @patch(f"{MODULE}.settings")
    @patch(f"{MODULE}.get_thread_confluence")
    def test_export_only_csv(
        self, mock_client_factory: MagicMock, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        mock_settings.export.output_path = tmp_path
        mock_settings.export.database_export = "table"
        mock_settings.export.database_formats = ["csv"]
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"
        client.get.side_effect = lambda path: {
            "results": _sample_fields() if "fields" in path else _sample_entries()
        }
        mock_client_factory.return_value = client

        page = _make_database_page()
        page.export()

        md_file = tmp_path / "DEV" / "Project Tasks.md"
        csv_file = tmp_path / "DEV" / "Project Tasks.csv"

        assert not md_file.exists()
        assert csv_file.exists()

    @patch(f"{MODULE}.settings")
    @patch(f"{MODULE}.get_thread_confluence")
    def test_export_fallback_on_error(
        self,
        mock_client_factory: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_settings.export.output_path = tmp_path
        mock_settings.export.database_export = "table"
        mock_settings.export.database_formats = ["markdown"]
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"
        client.get.side_effect = HTTPError("403 Forbidden")
        mock_client_factory.return_value = client

        page = _make_database_page()
        page.export()

        md_file = tmp_path / "DEV" / "Project Tasks.md"
        assert md_file.exists()
        content = md_file.read_text(encoding="utf-8")
        assert "This is a Confluence database" in content
        assert "Falling back to placeholder" in caplog.text

    @patch(f"{MODULE}.settings")
    def test_export_none_skips(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        mock_settings.export.output_path = tmp_path
        mock_settings.export.database_export = "none"
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        page = _make_database_page()
        page.export()

        md_file = tmp_path / "DEV" / "Project Tasks.md"
        assert not md_file.exists()


class TestDatabasePagination:
    @patch(f"{MODULE}.settings")
    @patch(f"{MODULE}.get_thread_confluence")
    def test_pagination_follows_next_link(
        self, mock_client_factory: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_settings.export.database_export = "table"
        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"

        def mock_get(path: str) -> dict:
            if "cursor=2" in path:
                return {"results": [{"id": "entry-2", "values": {}}], "_links": {}}
            return {
                "results": [{"id": "entry-1", "values": {}}],
                "_links": {"next": "/wiki/api/v2/databases/42/entries?cursor=2"},
            }

        client.get.side_effect = mock_get
        mock_client_factory.return_value = client

        page = _make_database_page()
        entries = page.fetch_database_entries()
        assert len(entries) == 2
        assert [e["id"] for e in entries] == ["entry-1", "entry-2"]


class TestCliCommands:
    def test_database_commands_registered(self) -> None:
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "database" in command_names
        assert "databases" in command_names
