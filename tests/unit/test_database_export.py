"""Unit tests for Confluence Cloud database export features."""

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from requests import HTTPError

from confluence_markdown_exporter.api_clients import ConfluenceRef
from confluence_markdown_exporter.api_clients import parse_confluence_path
from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.confluence import Space
from confluence_markdown_exporter.confluence import Version
from confluence_markdown_exporter.confluence import _extract_adf_text
from confluence_markdown_exporter.main import app
from confluence_markdown_exporter.utils.app_data_store import ExportConfig
from confluence_markdown_exporter.utils.database_cache import DatabaseDataCache
from confluence_markdown_exporter.utils.database_cache import PageMetadataCache
from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry

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
        assert cfg.database_resolve_depth == 2

    def test_database_resolve_depth_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            ExportConfig.model_validate({"database_resolve_depth": -1})

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


class TestDatabaseReferenceResolution:
    @pytest.fixture(autouse=True)
    def _setup_cache(self) -> Iterator[None]:
        PageTitleRegistry.reset()
        DatabaseDataCache.reset()
        PageMetadataCache.reset()
        yield
        PageTitleRegistry.reset()
        DatabaseDataCache.reset()
        PageMetadataCache.reset()

    @patch(f"{MODULE}.settings")
    def test_entry_link_depth_0_returns_raw_uuid(self, mock_settings: MagicMock) -> None:
        mock_settings.export.database_resolve_depth = 0
        page = _make_database_page(page_id=1, title="DB1")

        field = {"id": "ref", "name": "Ref", "type": "entryLink"}
        cell_data = {
            "type": "entryLink",
            "value": [{"entryId": "uuid-123", "databaseContentId": "2"}],
        }

        result = page._format_database_cell_value(field, cell_data, for_markdown=True)
        assert result == "uuid-123"

    @patch(f"{MODULE}.settings")
    def test_entry_link_depth_1_in_scope_relative_link(self, mock_settings: MagicMock) -> None:
        mock_settings.export.database_resolve_depth = 1
        mock_settings.export.page_href = "relative"
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        db1 = _make_database_page(page_id=1, title="DB1")
        db2 = _make_database_page(page_id=2, title="DB2")

        # Register both in scope
        PageTitleRegistry.register(1, "DB1", db1.export_path)
        PageTitleRegistry.register(2, "DB2", db2.export_path)

        # Seed DB2 in cache
        db2_fields = [{"id": "title", "name": "Title", "type": "text"}]
        db2_entries = [
            {"id": "entry-row-1", "values": {"title": {"type": "text", "plain": "Customer Acme"}}}
        ]
        DatabaseDataCache.set("2", db2_fields, db2_entries, "DB2")

        field = {"id": "ref", "name": "Customer", "type": "entryLink"}
        cell_data = {
            "type": "entryLink",
            "value": [{"entryId": "entry-row-1", "databaseContentId": "2"}],
        }

        result_md = db1._format_database_cell_value(field, cell_data, for_markdown=True)
        assert result_md == "[Customer Acme](DB2.md)"

        result_csv = db1._format_database_cell_value(field, cell_data, for_markdown=False)
        assert result_csv == "Customer Acme"

    @patch(f"{MODULE}.settings")
    def test_entry_link_depth_1_out_of_scope_plain_text(self, mock_settings: MagicMock) -> None:
        mock_settings.export.database_resolve_depth = 1
        mock_settings.export.page_href = "relative"

        db1 = _make_database_page(page_id=1, title="DB1")
        # DB2 is NOT registered in PageTitleRegistry export scope

        db2_fields = [{"id": "title", "name": "Title", "type": "text"}]
        db2_entries = [
            {"id": "entry-row-2", "values": {"title": {"type": "text", "plain": "External Org"}}}
        ]
        DatabaseDataCache.set("99", db2_fields, db2_entries, "External DB")

        field = {"id": "ref", "name": "Partner", "type": "entryLink"}
        cell_data = {
            "type": "entryLink",
            "value": [{"entryId": "entry-row-2", "databaseContentId": "99"}],
        }

        # Per user requirement: out of scope references should NOT be a link, but plain text
        result_md = db1._format_database_cell_value(field, cell_data, for_markdown=True)
        assert result_md == "External Org"

        result_csv = db1._format_database_cell_value(field, cell_data, for_markdown=False)
        assert result_csv == "External Org"

    @patch(f"{MODULE}.settings")
    def test_entry_details_depth_0_empty(self, mock_settings: MagicMock) -> None:
        mock_settings.export.database_resolve_depth = 0
        db1 = _make_database_page(page_id=1, title="DB1")

        field = {
            "id": "det",
            "name": "Location",
            "type": "entryDetails",
            "settings": {"sourceFieldId": "link-col", "lookupFieldId": "loc-col"},
        }
        entry = {
            "id": "e1",
            "values": {
                "link-col": {
                    "type": "entryLink",
                    "value": [{"entryId": "row-1", "databaseContentId": "2"}],
                },
                "det": {"type": "entryDetails", "value": None},
            },
        }

        result = db1._format_database_cell_value(
            field, entry["values"]["det"], for_markdown=True, entry=entry
        )
        assert result == ""

    @patch(f"{MODULE}.settings")
    def test_entry_details_depth_1_resolved(self, mock_settings: MagicMock) -> None:
        mock_settings.export.database_resolve_depth = 1
        db1 = _make_database_page(page_id=1, title="DB1")

        # Seed DB2
        db2_fields = [
            {"id": "title", "name": "Title", "type": "text"},
            {"id": "loc-col", "name": "City", "type": "text"},
        ]
        db2_entries = [
            {
                "id": "row-1",
                "values": {
                    "title": {"type": "text", "plain": "Berlin Office"},
                    "loc-col": {"type": "text", "plain": "Berlin"},
                },
            }
        ]
        DatabaseDataCache.set("2", db2_fields, db2_entries, "DB2")

        field = {
            "id": "det",
            "name": "Location",
            "type": "entryDetails",
            "settings": {"sourceFieldId": "link-col", "lookupFieldId": "loc-col"},
        }
        entry = {
            "id": "e1",
            "values": {
                "link-col": {
                    "type": "entryLink",
                    "value": [{"entryId": "row-1", "databaseContentId": "2"}],
                },
                "det": {"type": "entryDetails", "value": None},
            },
        }

        result = db1._format_database_cell_value(
            field, entry["values"]["det"], for_markdown=True, entry=entry
        )
        assert result == "Berlin"

    @patch(f"{MODULE}.settings")
    def test_multi_hop_entry_details_depth_1_vs_depth_2(self, mock_settings: MagicMock) -> None:
        """DB1 has entryDetails pointing to DB2, which in turn points to DB3."""
        # Setup DB3
        db3_fields = [{"id": "t3", "name": "Country", "type": "text"}]
        db3_entries = [{"id": "e3", "values": {"t3": {"type": "text", "plain": "Germany"}}}]
        DatabaseDataCache.set("3", db3_fields, db3_entries, "DB3")

        # Setup DB2: has an entryLink to DB3 and entryDetail looking up 't3'
        db2_fields = [
            {"id": "t2", "name": "City", "type": "text"},
            {"id": "link-db3", "name": "Link to DB3", "type": "entryLink"},
            {
                "id": "detail-db3",
                "name": "Country Lookup",
                "type": "entryDetails",
                "settings": {"sourceFieldId": "link-db3", "lookupFieldId": "t3"},
            },
        ]
        db2_entries = [
            {
                "id": "e2",
                "values": {
                    "t2": {"type": "text", "plain": "Frankfurt"},
                    "link-db3": {
                        "type": "entryLink",
                        "value": [{"entryId": "e3", "databaseContentId": "3"}],
                    },
                    "detail-db3": {"type": "entryDetails", "value": None},
                },
            }
        ]
        DatabaseDataCache.set("2", db2_fields, db2_entries, "DB2")

        # Setup DB1: links to DB2, and has detail field looking up DB2's 'detail-db3'
        db1 = _make_database_page(page_id=1, title="DB1")
        field_in_db1 = {
            "id": "hop2",
            "name": "Country via DB2",
            "type": "entryDetails",
            "settings": {"sourceFieldId": "link-db2", "lookupFieldId": "detail-db3"},
        }
        entry_in_db1 = {
            "id": "e1",
            "values": {
                "link-db2": {
                    "type": "entryLink",
                    "value": [{"entryId": "e2", "databaseContentId": "2"}],
                },
                "hop2": {"type": "entryDetails", "value": None},
            },
        }

        # Depth = 1: 1 hop resolved (reaches DB2). Since DB2's field is another reference (to DB3),
        # remaining depth is 0, so DB2's lookup field cannot resolve DB3 (returns empty).
        mock_settings.export.database_resolve_depth = 1
        res_depth_1 = db1._format_database_cell_value(
            field_in_db1,
            entry_in_db1["values"]["hop2"],
            for_markdown=True,
            entry=entry_in_db1,
        )
        assert res_depth_1 == ""

        # Depth = 2: 2 hops resolved (DB1 -> DB2 -> DB3), successfully resolving "Germany"!
        mock_settings.export.database_resolve_depth = 2
        res_depth_2 = db1._format_database_cell_value(
            field_in_db1,
            entry_in_db1["values"]["hop2"],
            for_markdown=True,
            entry=entry_in_db1,
        )
        assert res_depth_2 == "Germany"

    @patch(f"{MODULE}.settings")
    def test_circular_reference_cycle_detection(self, mock_settings: MagicMock) -> None:
        """Circular reference between DB1 and DB2 terminates without infinite loop."""
        mock_settings.export.database_resolve_depth = 5

        db1 = _make_database_page(page_id=1, title="DB1")

        db2_fields = [
            {"id": "t2", "name": "Title", "type": "text"},
            {
                "id": "det2",
                "name": "BackToDB1",
                "type": "entryDetails",
                "settings": {"sourceFieldId": "link1", "lookupFieldId": "det1"},
            },
            {"id": "link1", "name": "Link to DB1", "type": "entryLink"},
        ]
        db2_entries = [
            {
                "id": "e2",
                "values": {
                    "t2": {"type": "text", "plain": "Node 2"},
                    "link1": {
                        "type": "entryLink",
                        "value": [{"entryId": "e1", "databaseContentId": "1"}],
                    },
                    "det2": {"type": "entryDetails", "value": None},
                },
            }
        ]
        DatabaseDataCache.set("2", db2_fields, db2_entries, "DB2")

        db1_fields = [
            {"id": "t1", "name": "Title", "type": "text"},
            {
                "id": "det1",
                "name": "ToDB2",
                "type": "entryDetails",
                "settings": {"sourceFieldId": "link2", "lookupFieldId": "det2"},
            },
            {"id": "link2", "name": "Link to DB2", "type": "entryLink"},
        ]
        db1_entries = [
            {
                "id": "e1",
                "values": {
                    "t1": {"type": "text", "plain": "Node 1"},
                    "link2": {
                        "type": "entryLink",
                        "value": [{"entryId": "e2", "databaseContentId": "2"}],
                    },
                    "det1": {"type": "entryDetails", "value": None},
                },
            }
        ]
        DatabaseDataCache.set("1", db1_fields, db1_entries, "DB1")

        # Resolving det1 should not raise RecursionError and return safely
        res = db1._format_database_cell_value(
            db1_fields[1],
            db1_entries[0]["values"]["det1"],
            for_markdown=True,
            entry=db1_entries[0],
            all_fields=db1_fields,
        )
        assert isinstance(res, str)


class TestConfluencePageResolution:
    @pytest.fixture(autouse=True)
    def _setup_cache(self) -> Iterator[None]:
        PageTitleRegistry.reset()
        DatabaseDataCache.reset()
        PageMetadataCache.reset()
        yield
        PageTitleRegistry.reset()
        DatabaseDataCache.reset()
        PageMetadataCache.reset()

    @patch(f"{MODULE}.settings")
    def test_page_link_always_resolves_title(self, mock_settings: MagicMock) -> None:
        mock_settings.export.database_resolve_depth = 0
        mock_settings.export.page_href = "relative"

        db = _make_database_page(page_id=1, title="DB")
        PageMetadataCache.set(
            "100",
            {
                "title": "Architecture Overview",
                "web_url": "https://example.atlassian.net/wiki/spaces/DEV/pages/100",
            },
        )

        field = {"id": "page_col", "name": "Spec Page", "type": "pageLink"}
        cell_data = {"type": "pageLink", "value": [{"contentId": "100"}]}

        # Depth 0: still resolves page title (matching Confluence Cloud)
        res_md = db._format_database_cell_value(field, cell_data, for_markdown=True)
        expected_link = (
            "[Architecture Overview](https://example.atlassian.net/wiki/spaces/DEV/pages/100)"
        )
        assert expected_link in res_md

        res_csv = db._format_database_cell_value(field, cell_data, for_markdown=False)
        assert res_csv == "Architecture Overview"

    @patch(f"{MODULE}.settings")
    def test_page_link_in_scope_relative_markdown(self, mock_settings: MagicMock) -> None:
        mock_settings.export.database_resolve_depth = 0
        mock_settings.export.page_href = "relative"
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        db = _make_database_page(page_id=1, title="DB")
        PageTitleRegistry.register(200, "User Guide", Path("DEV/User Guide.md"))

        field = {"id": "p", "name": "Docs", "type": "pageLink"}
        cell_data = {"type": "pageLink", "value": [{"contentId": "200"}]}

        res = db._format_database_cell_value(field, cell_data, for_markdown=True)
        assert res == "[User Guide](User Guide.md)"

    @patch(f"{MODULE}.settings")
    def test_page_status_resolved(self, mock_settings: MagicMock) -> None:
        db = _make_database_page(page_id=1, title="DB")
        PageMetadataCache.set("300", {"title": "Roadmap", "status": "IN PROGRESS"})

        field = {
            "id": "status_field",
            "name": "Doc Status",
            "type": "pageStatus",
            "settings": {"sourceFieldId": "page_ref"},
        }
        entry = {
            "id": "e1",
            "values": {
                "page_ref": {"type": "pageLink", "value": [{"contentId": "300"}]},
                "status_field": {"type": "pageStatus", "value": None},
            },
        }

        res = db._format_database_cell_value(field, entry["values"]["status_field"], entry=entry)
        assert res == "IN PROGRESS"

    @patch(f"{MODULE}.settings")
    def test_page_labels_resolved(self, mock_settings: MagicMock) -> None:
        db = _make_database_page(page_id=1, title="DB")
        PageMetadataCache.set("400", {"title": "API Spec", "labels": ["backend", "api-v2"]})

        field = {
            "id": "labels_field",
            "name": "Page Labels",
            "type": "pageLabels",
            "settings": {"sourceFieldId": "page_ref"},
        }
        entry = {
            "id": "e1",
            "values": {
                "page_ref": {"type": "pageLink", "value": [{"contentId": "400"}]},
                "labels_field": {"type": "pageLabels", "value": None},
            },
        }

        res = db._format_database_cell_value(field, entry["values"]["labels_field"], entry=entry)
        assert res == "backend, api-v2"

    @patch(f"{MODULE}.settings")
    def test_page_details_resolved(self, mock_settings: MagicMock) -> None:
        db = _make_database_page(page_id=1, title="DB")
        PageMetadataCache.set(
            "500",
            {
                "title": "Release Notes",
                "created": "2026-10-01",
                "created_by": "Alice Engineer",
                "version": "3",
                "excerpt": "Key highlights of version 3.0",
            },
        )

        for prop_key, expected in [
            ("Created at", "2026-10-01"),
            ("Created by", "Alice Engineer"),
            ("Version number", "3"),
            ("Excerpt content", "Key highlights of version 3.0"),
        ]:
            field = {
                "id": "detail_field",
                "name": f"Detail {prop_key}",
                "type": "pageDetails",
                "settings": {"sourceFieldId": "page_ref", "pagePropertyKey": prop_key},
            }
            entry = {
                "id": "e1",
                "values": {
                    "page_ref": {"type": "pageLink", "value": [{"contentId": "500"}]},
                    "detail_field": {"type": "pageDetails", "value": None},
                },
            }
            res = db._format_database_cell_value(
                field, entry["values"]["detail_field"], entry=entry
            )
            assert res == expected


class TestDatabaseJsonExportResolvedValues:
    @patch(f"{MODULE}.settings")
    @patch(f"{MODULE}.get_thread_confluence")
    def test_json_export_includes_resolved_values(
        self, mock_client_factory: MagicMock, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        mock_settings.export.output_path = tmp_path
        mock_settings.export.database_export = "table"
        mock_settings.export.database_formats = ["json"]
        mock_settings.export.database_resolve_depth = 1
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        fields = [
            {"id": "title", "name": "Task", "type": "text"},
            {"id": "ref", "name": "Client", "type": "entryLink"},
        ]
        entries = [
            {
                "id": "entry-1",
                "databaseId": "42",
                "values": {
                    "title": {"type": "text", "plain": "Audit Task"},
                    "ref": {
                        "type": "entryLink",
                        "value": [{"entryId": "c1", "databaseContentId": "88"}],
                    },
                },
            }
        ]

        # Seed client DB 88
        DatabaseDataCache.set(
            "88",
            [{"id": "title", "name": "Title", "type": "text"}],
            [{"id": "c1", "values": {"title": {"type": "text", "plain": "Acme Corp"}}}],
            "Clients",
        )

        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"
        client.get.side_effect = lambda path: {"results": fields if "fields" in path else entries}
        mock_client_factory.return_value = client

        page = _make_database_page(page_id=42, title="Project Tasks")
        page.export()

        json_file = tmp_path / "DEV" / "Project Tasks.json"
        assert json_file.exists()

        data = json.loads(json_file.read_text(encoding="utf-8"))
        entry_exported = data["entries"][0]

        # Raw values intact
        assert entry_exported["values"]["ref"]["value"][0]["entryId"] == "c1"

        # Resolved values map present
        assert "resolved_values" in entry_exported
        assert entry_exported["resolved_values"]["title"] == "Audit Task"
        assert entry_exported["resolved_values"]["ref"] == "Acme Corp"


class TestDatabaseExtendedFieldTypesAndCaches:
    @pytest.fixture(autouse=True)
    def _setup_cache(self) -> Iterator[None]:
        PageTitleRegistry.reset()
        DatabaseDataCache.reset()
        PageMetadataCache.reset()
        yield
        PageTitleRegistry.reset()
        DatabaseDataCache.reset()
        PageMetadataCache.reset()

    @patch(f"{MODULE}.settings")
    def test_jira_issue_details_resolution(self, mock_settings: MagicMock) -> None:
        """Jira issue details fields extract requested attributes from the linked Jira issue."""
        mock_settings.export.database_resolve_depth = 1
        page = _make_database_page(page_id=10, title="Tickets DB")

        creator_field = {
            "id": "detail-creator",
            "name": "Creator",
            "type": "jiraIssueDetails",
            "settings": {"sourceFieldId": "jira-1", "jiraFieldKey": "creator"},
        }
        status_field = {
            "id": "detail-status",
            "name": "Status",
            "type": "jiraIssueDetails",
            "settings": {"sourceFieldId": "jira-1", "jiraFieldKey": "status"},
        }

        entry = {
            "id": "row-1",
            "values": {
                "jira-1": {
                    "type": "jiraIssue",
                    "value": [{"key": "PROJ-101"}],
                },
                "detail-creator": {"type": "jiraIssueDetails", "value": None},
                "detail-status": {"type": "jiraIssueDetails", "value": None},
            },
        }

        mock_issue = MagicMock()
        mock_issue.key = "PROJ-101"
        mock_issue.raw = {
            "fields": {
                "creator": {"displayName": "Alice Engineer"},
                "status": {"name": "In Review"},
            }
        }

        with patch(
            "confluence_markdown_exporter.confluence.JiraIssue.from_key",
            return_value=mock_issue,
        ):
            res_creator = page._format_database_cell_value(
                creator_field,
                entry["values"]["detail-creator"],
                for_markdown=True,
                entry=entry,
            )
            assert res_creator == "Alice Engineer"

            res_status = page._format_database_cell_value(
                status_field,
                entry["values"]["detail-status"],
                for_markdown=True,
                entry=entry,
            )
            assert res_status == "In Review"

    @patch(f"{MODULE}.settings")
    def test_backlink_markdown_link_and_count_resolution(self, mock_settings: MagicMock) -> None:
        """Backlink fields format markdown links (relative/absolute/wiki) or counts."""
        mock_settings.export.database_resolve_depth = 1
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None
        PageTitleRegistry.register(1, "Source DB", Path("DEV/Source DB.md"))
        PageTitleRegistry.register(2, "Target DB", Path("DEV/Target DB.md"))

        src_fields = [
            {"id": "name", "name": "Name", "type": "text"},
            {"id": "link", "name": "Link", "type": "entryLink"},
        ]
        src_entries = [
            {
                "id": "src-e1",
                "values": {
                    "name": {"type": "text", "plain": "Referencing Row"},
                    "link": {"type": "entryLink", "value": [{"entryId": "target-e1"}]},
                },
            }
        ]
        DatabaseDataCache.set("1", src_fields, src_entries, "Source DB")

        target_db = _make_database_page(page_id=2, title="Target DB")
        backlink_link_field = {
            "id": "bl-link",
            "name": "Backlink",
            "type": "backlink",
            "settings": {"sourceDatabaseContentId": "1"},
        }
        backlink_count_field = {
            "id": "bl-count",
            "name": "Backlink Count",
            "type": "backlink",
            "settings": {"sourceDatabaseContentId": "1", "display": "number"},
        }
        entry = {
            "id": "target-e1",
            "values": {
                "bl-link": {"type": "backlink", "value": None},
                "bl-count": {"type": "backlink", "value": None},
            },
        }

        mock_settings.export.page_href = "relative"
        assert (
            target_db._format_database_cell_value(
                backlink_link_field, entry["values"]["bl-link"], for_markdown=True, entry=entry
            )
            == "[Referencing Row](Source DB.md)"
        )

        mock_settings.export.page_href = "absolute"
        assert (
            target_db._format_database_cell_value(
                backlink_link_field, entry["values"]["bl-link"], for_markdown=True, entry=entry
            )
            == "[Referencing Row](/DEV/Source DB.md)"
        )

        mock_settings.export.page_href = "wiki"
        assert (
            target_db._format_database_cell_value(
                backlink_link_field, entry["values"]["bl-link"], for_markdown=True, entry=entry
            )
            == "[[Source DB|Referencing Row]]"
        )

        assert (
            target_db._format_database_cell_value(
                backlink_count_field, entry["values"]["bl-count"], for_markdown=True, entry=entry
            )
            == "1"
        )

    @patch(f"{MODULE}.settings")
    def test_entry_link_and_page_link_wiki_disambiguation(self, mock_settings: MagicMock) -> None:
        """Wiki links qualify paths when two registered objects share a title."""
        mock_settings.export.database_resolve_depth = 1
        mock_settings.export.page_href = "wiki"
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        db = _make_database_page(page_id=1, title="Main DB")
        PageTitleRegistry.register(10, "Shared Name", Path("DEV/Shared Name.md"))
        PageTitleRegistry.register(11, "Shared Name", Path("OPS/Shared Name.md"))

        DatabaseDataCache.set(
            "10",
            [{"id": "title", "name": "Title", "type": "text"}],
            [{"id": "e10", "values": {"title": {"type": "text", "plain": "Row A"}}}],
            "Shared Name",
        )

        entry_res = db._format_database_cell_value(
            {"id": "ref", "name": "Ref", "type": "entryLink"},
            {"type": "entryLink", "value": [{"entryId": "e10", "databaseContentId": "10"}]},
            for_markdown=True,
        )
        assert entry_res == "[[DEV/Shared Name|Row A]]"

        page_res = db._format_database_cell_value(
            {"id": "pg", "name": "Page", "type": "pageLink"},
            {"type": "pageLink", "value": [{"contentId": "11"}]},
            for_markdown=True,
        )
        assert page_res == "[[OPS/Shared Name|Shared Name]]"

    @patch(f"{MODULE}.settings")
    @patch(f"{MODULE}.get_thread_confluence")
    def test_database_cache_get_or_fetch_and_discovery_without_db_id(
        self, mock_client_factory: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Discover target DB via space search and pagination when databaseContentId is omitted."""
        mock_settings.export.database_resolve_depth = 1
        mock_settings.export.page_href = "relative"
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None

        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"

        def mock_get(path: str) -> dict:
            if "content/search" in path:
                return {"results": [{"id": "77"}]}
            if path == "api/v2/databases/77":
                return {"id": "77", "title": "Vendors"}
            if path == "api/v2/databases/77/fields":
                return {
                    "results": [{"id": "title", "name": "Title", "type": "text"}],
                    "_links": {},
                }
            if path == "api/v2/databases/77/entries":
                return {
                    "results": [
                        {"id": "v-1", "values": {"title": {"type": "text", "plain": "Vendor One"}}}
                    ],
                    "_links": {"next": "/wiki/api/v2/databases/77/entries?cursor=2"},
                }
            if "cursor=2" in path:
                return {
                    "results": [
                        {"id": "v-2", "values": {"title": {"type": "text", "plain": "Vendor Two"}}}
                    ],
                    "_links": {},
                }
            return {}

        client.get.side_effect = mock_get
        mock_client_factory.return_value = client

        db1 = _make_database_page(page_id=1, title="Projects")
        result = db1._format_database_cell_value(
            {"id": "vendor", "name": "Vendor", "type": "entryLink"},
            {"type": "entryLink", "value": [{"entryId": "v-2"}]},
            for_markdown=True,
        )
        assert result == "Vendor Two"
        assert DatabaseDataCache.get_database_id_for_entry("v-2") == "77"

    @patch(f"{MODULE}.get_thread_confluence")
    def test_page_metadata_cache_get_or_fetch_populates_excerpt_and_status(
        self, mock_client_factory: MagicMock
    ) -> None:
        """PageMetadataCache fetches page details via Page.from_id and v2 fallback."""
        client = MagicMock()
        client.url = f"{BASE_URL}/wiki"
        client.get.return_value = {"id": "321", "title": "Spec", "status": "current"}
        mock_client_factory.return_value = client

        mock_page = MagicMock()
        mock_page.title = "Spec"
        mock_page.web_url = f"{BASE_URL}/wiki/spaces/DEV/pages/321"
        mock_page.space = MagicMock(key="DEV")
        mock_page.labels = [MagicMock()]
        mock_page.labels[0].name = "architecture"
        mock_page.version = MagicMock(
            number=4, message="Added diagram", when="2026-10-15", by=MagicMock(display_name="Bob")
        )
        mock_page.history = MagicMock(
            created="2026-10-01", created_by=MagicMock(display_name="Alice")
        )
        mock_page.body_storage = (
            '<ac:structured-macro ac:name="excerpt">'
            "<ac:rich-text-body><p>Summary text</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )

        with patch(f"{MODULE}.Page.from_id", return_value=mock_page):
            meta = PageMetadataCache.get_or_fetch("321", BASE_URL)

        assert meta["title"] == "Spec"
        assert meta["status"] == "current"
        assert meta["labels"] == ["architecture"]
        assert meta["version"] == "4"
        assert meta["version_comment"] == "Added diagram"
        assert meta["created_by"] == "Alice"
        assert meta["last_modified_by"] == "Bob"
        assert meta["excerpt"] == "Summary text"
        # Cached hit does not re-fetch
        assert PageMetadataCache.get_or_fetch("321", BASE_URL) is meta
        assert client.get.call_count == 1

    @patch(f"{MODULE}.settings")
    def test_backlink_resolves_page_link_primary_column_title(
        self, mock_settings: MagicMock
    ) -> None:
        """Backlink resolves pageLink primary columns to page titles instead of raw contentId."""
        mock_settings.export.database_resolve_depth = 1
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None
        mock_settings.export.page_href = "relative"

        PageTitleRegistry.register(1, "Source DB", Path("DEV/Source DB.md"))
        PageTitleRegistry.register(2, "Target DB", Path("DEV/Target DB.md"))
        PageTitleRegistry.register(555, "Design Spec", Path("DEV/Design Spec.md"))

        src_fields = [
            {"id": "page-col", "name": "Spec", "type": "pageLink"},
            {"id": "link", "name": "Target", "type": "entryLink"},
        ]
        src_entries = [
            {
                "id": "src-e1",
                "values": {
                    "page-col": {"type": "pageLink", "value": [{"contentId": "555"}]},
                    "link": {"type": "entryLink", "value": [{"entryId": "target-e1"}]},
                },
            }
        ]
        DatabaseDataCache.set("1", src_fields, src_entries, "Source DB")

        target_db = _make_database_page(page_id=2, title="Target DB")
        backlink_field = {
            "id": "bl",
            "name": "Backlink",
            "type": "backlink",
            "settings": {"sourceDatabaseContentId": "1"},
        }
        entry = {"id": "target-e1", "values": {"bl": {"type": "backlink", "value": None}}}

        res = target_db._format_database_cell_value(
            backlink_field, entry["values"]["bl"], for_markdown=True, entry=entry
        )
        assert res == "[Design Spec](Source DB.md)"

    @patch(f"{MODULE}.settings")
    def test_backlink_with_direct_content_id_value_formats_page_link(
        self, mock_settings: MagicMock
    ) -> None:
        """Backlink without sourceDatabaseContentId formats direct contentId refs as page links."""
        mock_settings.export.database_resolve_depth = 1
        mock_settings.export.page_path = "{space_key}/{page_title}.md"
        mock_settings.export.page_path_if_parent = None
        mock_settings.export.page_href = "relative"

        PageTitleRegistry.register(555, "Design Spec", Path("DEV/Design Spec.md"))
        db = _make_database_page(page_id=2, title="Target DB")
        backlink_field = {"id": "bl", "name": "Backlink", "type": "backlink", "settings": {}}
        entry = {
            "id": "e1",
            "values": {"bl": {"type": "backlink", "value": [{"contentId": "555"}]}},
        }

        res = db._format_database_cell_value(
            backlink_field, entry["values"]["bl"], for_markdown=True, entry=entry
        )
        assert res == "[Design Spec](Design Spec.md)"
