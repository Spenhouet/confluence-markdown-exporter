"""Unit tests for lockfile module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.utils.lockfile import AttachmentEntry
from confluence_markdown_exporter.utils.lockfile import ConfluenceLock
from confluence_markdown_exporter.utils.lockfile import LockfileManager
from confluence_markdown_exporter.utils.lockfile import PageEntry

LOCKFILE_FILENAME = "confluence-lock.json"


def _make_mock_page(
    page_id: int,
    version_number: int,
    export_path: str,
) -> MagicMock:
    """Create a mock page/descendant with the attributes used by LockfileManager."""
    page = MagicMock()
    page.id = page_id
    page.version.number = version_number
    page.export_path = Path(export_path)
    page.title = f"Page {page_id}"
    return page


def _make_mock_attachment(
    attachment_id: str,
    version_number: int,
    export_path: str,
    file_id: str = "",
    title: str = "",
) -> MagicMock:
    """Create a mock attachment with the attributes used by LockfileManager."""
    att = MagicMock()
    att.id = attachment_id
    att.version.number = version_number
    att.export_path = Path(export_path)
    att.file_id = file_id or f"fid-{attachment_id}"
    att.title = title or f"Attachment {attachment_id}"
    return att


@pytest.fixture(autouse=True)
def _reset_lockfile_manager() -> None:
    """Reset LockfileManager class state before each test."""
    LockfileManager._lockfile_path = None
    LockfileManager._lock = None
    LockfileManager._output_path = None
    LockfileManager._all_entries_snapshot = {}
    LockfileManager._seen_page_ids = set()


class TestLockfileManagerInit:
    """Test cases for LockfileManager.init."""

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_init_creates_empty_lock_when_no_lockfile(
        self,
        mock_get_settings: MagicMock,
    ) -> None:
        """When lockfile does not exist, init creates an empty lock."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_get_settings.return_value.export.output_path = Path(tmp)
            mock_get_settings.return_value.export.lockfile_name = LOCKFILE_FILENAME

            LockfileManager.init()

            assert LockfileManager._lock is not None
            assert LockfileManager._lock.pages == {}
            assert LockfileManager._lockfile_path == Path(tmp) / LOCKFILE_FILENAME

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_init_loads_existing_lockfile(
        self,
        mock_get_settings: MagicMock,
    ) -> None:
        """When lockfile exists, init loads its contents."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_get_settings.return_value.export.output_path = Path(tmp)
            mock_get_settings.return_value.export.lockfile_name = LOCKFILE_FILENAME
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            data = {
                "lockfile_version": 1,
                "last_export": "2025-01-01T00:00:00+00:00",
                "pages": {
                    "100": {
                        "title": "Page A",
                        "version": 3,
                        "export_path": "space/Page A.md",
                    }
                },
            }
            lockfile_path.write_text(json.dumps(data), encoding="utf-8")

            LockfileManager.init()

            assert LockfileManager._lock is not None
            assert "100" in LockfileManager._lock.pages
            assert LockfileManager._lock.pages["100"].version == 3

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_init_snapshots_all_entries(
        self,
        mock_get_settings: MagicMock,
    ) -> None:
        """Init snapshots all lockfile entries for moved-page detection."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_get_settings.return_value.export.output_path = Path(tmp)
            mock_get_settings.return_value.export.lockfile_name = LOCKFILE_FILENAME
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            data = {
                "lockfile_version": 1,
                "last_export": "",
                "pages": {
                    "100": {
                        "title": "A",
                        "version": 1,
                        "export_path": "a.md",
                    },
                    "200": {
                        "title": "B",
                        "version": 2,
                        "export_path": "b.md",
                    },
                },
            }
            lockfile_path.write_text(json.dumps(data), encoding="utf-8")

            LockfileManager.init()

            assert set(LockfileManager._all_entries_snapshot.keys()) == {
                "100",
                "200",
            }
            assert LockfileManager._seen_page_ids == set()


class TestLockfileManagerRecordPage:
    """Test cases for LockfileManager.record_page."""

    def test_record_page_creates_lockfile(self) -> None:
        """record_page creates the lockfile on disk and writes the page entry."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock()

            page = _make_mock_page(page_id=100, version_number=1, export_path="space/Page A.md")
            LockfileManager.record_page(page)

            assert lockfile_path.exists()
            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "100" in saved["pages"]
            assert saved["pages"]["100"]["version"] == 1

    def test_record_page_does_nothing_when_not_initialized(self) -> None:
        """record_page is a no-op when LockfileManager has not been initialized."""
        page = _make_mock_page(page_id=100, version_number=1, export_path="space/Page A.md")

        # Should not raise
        LockfileManager.record_page(page)

    def test_record_page_updates_existing_entry(self) -> None:
        """record_page updates an existing page entry with the new version."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(title="Page A", version=1, export_path="space/Page A.md"),
                }
            )

            page = _make_mock_page(page_id=100, version_number=2, export_path="space/Page A.md")
            LockfileManager.record_page(page)

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert saved["pages"]["100"]["version"] == 2

    def test_record_page_adds_to_seen_page_ids(self) -> None:
        """record_page adds the page ID to the seen set."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock()

            page = _make_mock_page(page_id=100, version_number=1, export_path="a.md")
            LockfileManager.record_page(page)

            assert "100" in LockfileManager._seen_page_ids


class TestLockfileManagerShouldExport:
    """Test cases for LockfileManager.should_export."""

    def test_page_not_in_lockfile_should_export(self) -> None:
        """A page not present in the lockfile should be exported."""
        LockfileManager._lock = ConfluenceLock(
            pages={
                "999": PageEntry(title="Other", version=1, export_path="other.md"),
            }
        )

        page = _make_mock_page(page_id=123, version_number=1, export_path="space/New.md")
        assert LockfileManager.should_export(page) is True

    def test_page_in_lockfile_same_version_same_path_should_not_export(self) -> None:
        """A page with same version and same path should NOT be exported."""
        LockfileManager._lock = ConfluenceLock(
            pages={
                "123": PageEntry(title="Page A", version=5, export_path="space/Page A.md"),
            }
        )

        page = _make_mock_page(page_id=123, version_number=5, export_path="space/Page A.md")
        assert LockfileManager.should_export(page) is False

    def test_page_in_lockfile_different_version_should_export(self) -> None:
        """A page whose version has changed should be exported."""
        LockfileManager._lock = ConfluenceLock(
            pages={
                "123": PageEntry(title="Page A", version=5, export_path="space/Page A.md"),
            }
        )

        page = _make_mock_page(page_id=123, version_number=6, export_path="space/Page A.md")
        assert LockfileManager.should_export(page) is True

    def test_page_in_lockfile_different_export_path_should_export(self) -> None:
        """A page whose export path has changed (file moved) should be exported."""
        LockfileManager._lock = ConfluenceLock(
            pages={
                "123": PageEntry(title="Page A", version=5, export_path="old/Page A.md"),
            }
        )

        page = _make_mock_page(page_id=123, version_number=5, export_path="new/Page A.md")
        assert LockfileManager.should_export(page) is True

    def test_lock_is_none_should_export(self) -> None:
        """When lockfile manager is not initialized, all pages should be exported."""
        assert LockfileManager._lock is None

        page = _make_mock_page(page_id=123, version_number=1, export_path="space/Page A.md")
        assert LockfileManager.should_export(page) is True

    def test_missing_output_file_should_export(self) -> None:
        """A page whose output file no longer exists on disk should be re-exported."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            LockfileManager._output_path = output
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "123": PageEntry(title="Page A", version=5, export_path="space/Page A.md"),
                }
            )

            # File does NOT exist on disk
            page = _make_mock_page(page_id=123, version_number=5, export_path="space/Page A.md")
            assert LockfileManager.should_export(page) is True

    def test_existing_output_file_unchanged_should_not_export(self) -> None:
        """A page whose output file exists and is up-to-date should NOT be re-exported."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            md_file = output / "space" / "Page A.md"
            md_file.parent.mkdir(parents=True)
            md_file.write_text("content")

            LockfileManager._output_path = output
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "123": PageEntry(title="Page A", version=5, export_path="space/Page A.md"),
                }
            )

            page = _make_mock_page(page_id=123, version_number=5, export_path="space/Page A.md")
            assert LockfileManager.should_export(page) is False


class TestLockfileManagerMarkSeen:
    """Test cases for LockfileManager.mark_seen."""

    def test_mark_seen_adds_page_ids(self) -> None:
        """mark_seen adds page IDs to the seen set."""
        LockfileManager.mark_seen([100, 200, 300])
        assert LockfileManager._seen_page_ids == {"100", "200", "300"}

    def test_mark_seen_accumulates(self) -> None:
        """mark_seen accumulates across multiple calls."""
        LockfileManager.mark_seen([100])
        LockfileManager.mark_seen([200])
        assert LockfileManager._seen_page_ids == {"100", "200"}


class TestLockfileManagerCleanup:
    """Test cases for LockfileManager.cleanup."""

    def test_cleanup_noop_when_not_initialized(self) -> None:
        """Cleanup does nothing when not initialized."""
        LockfileManager.remove_pages(set())  # Should not raise

    def test_cleanup_deletes_file_for_removed_page(self) -> None:
        """Pages deleted from Confluence have their files removed."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            md_file = output / "space" / "Removed.md"
            md_file.parent.mkdir(parents=True)
            md_file.write_text("content")

            lockfile_path = output / LOCKFILE_FILENAME
            LockfileManager._output_path = output
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Removed",
                        version=1,
                        export_path="space/Removed.md",
                    ),
                }
            )
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.pages)
            LockfileManager._seen_page_ids = set()  # page 100 not seen

            LockfileManager.remove_pages({"100"})

            assert not md_file.exists()

    def test_cleanup_removes_entry_from_lockfile(self) -> None:
        """Deleted pages are removed from the lockfile."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            lockfile_path = output / LOCKFILE_FILENAME
            LockfileManager._output_path = output
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Removed",
                        version=1,
                        export_path="space/Removed.md",
                    ),
                    "200": PageEntry(
                        title="Kept",
                        version=1,
                        export_path="space/Kept.md",
                    ),
                }
            )
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.pages)
            LockfileManager._seen_page_ids = {"200"}

            LockfileManager.remove_pages({"100"})

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "100" not in saved["pages"]
            assert "200" in saved["pages"]

    def test_cleanup_deletes_old_file_for_moved_page(self) -> None:
        """When a page's export_path changes, the old file is deleted."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            old_file = output / "old" / "Page.md"
            old_file.parent.mkdir(parents=True)
            old_file.write_text("old content")

            lockfile_path = output / LOCKFILE_FILENAME
            LockfileManager._output_path = output
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._all_entries_snapshot = {
                "100": PageEntry(
                    title="Page",
                    version=1,
                    export_path="old/Page.md",
                ),
            }
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Page",
                        version=2,
                        export_path="new/Page.md",
                    ),
                }
            )
            LockfileManager._seen_page_ids = {"100"}

            LockfileManager.remove_pages(set())

            assert not old_file.exists()

    def test_cleanup_keeps_page_existing_on_confluence(self) -> None:
        """Unseen pages that still exist on Confluence are kept."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            md_file = output / "space" / "Still.md"
            md_file.parent.mkdir(parents=True)
            md_file.write_text("content")

            lockfile_path = output / LOCKFILE_FILENAME
            LockfileManager._output_path = output
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Still",
                        version=1,
                        export_path="space/Still.md",
                    ),
                }
            )
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.pages)
            LockfileManager._seen_page_ids = set()

            LockfileManager.remove_pages(set())

            assert md_file.exists()
            assert "100" in LockfileManager._lock.pages

    def test_cleanup_keeps_unchanged_seen_pages(self) -> None:
        """Pages that were seen during export are not checked via API."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            lockfile_path = output / LOCKFILE_FILENAME
            LockfileManager._output_path = output
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Seen",
                        version=1,
                        export_path="a.md",
                    ),
                }
            )
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.pages)
            LockfileManager._seen_page_ids = {"100"}

            LockfileManager.remove_pages(set())
            # fetch_deleted_page_ids is never called — all pages were seen

    def test_cleanup_handles_already_deleted_file(self) -> None:
        """Cleanup does not fail when the file is already gone."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            lockfile_path = output / LOCKFILE_FILENAME
            LockfileManager._output_path = output
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Gone",
                        version=1,
                        export_path="space/Gone.md",
                    ),
                }
            )
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.pages)
            LockfileManager._seen_page_ids = set()

            LockfileManager.remove_pages({"100"})  # Should not raise

    def test_cleanup_api_failure_keeps_pages(self) -> None:
        """When API check fails, pages are kept (safe default)."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            md_file = output / "space" / "Safe.md"
            md_file.parent.mkdir(parents=True)
            md_file.write_text("content")

            lockfile_path = output / LOCKFILE_FILENAME
            LockfileManager._output_path = output
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Safe",
                        version=1,
                        export_path="space/Safe.md",
                    ),
                }
            )
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.pages)
            LockfileManager._seen_page_ids = set()

            # Pass empty set: safe default — don't delete anything on API failure
            LockfileManager.remove_pages(set())

            assert md_file.exists()
            assert "100" in LockfileManager._lock.pages


class TestFetchDeletedPageIds:
    """Test cases for fetch_deleted_page_ids."""

    def test_empty_input_returns_empty(self) -> None:
        """Empty list returns empty set."""
        from confluence_markdown_exporter.confluence import fetch_deleted_page_ids

        result = fetch_deleted_page_ids([])
        assert result == set()

    @patch("confluence_markdown_exporter.confluence.settings")
    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_returns_deleted_ids(
        self, mock_confluence: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Returns IDs that no longer exist on Confluence."""
        mock_settings.connection_config.use_v2_api = True
        mock_settings.export.existence_check_batch_size = 250
        mock_confluence.get.return_value = {
            "results": [{"id": "100"}, {"id": "300"}],
        }

        from confluence_markdown_exporter.confluence import fetch_deleted_page_ids

        result = fetch_deleted_page_ids(["100", "200", "300"])
        assert result == {"200"}

    @patch("confluence_markdown_exporter.confluence.settings")
    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_api_error_returns_no_deleted_ids(
        self, mock_confluence: MagicMock, mock_settings: MagicMock
    ) -> None:
        """On API error, returns empty set (safe: don't delete anything)."""
        mock_settings.connection_config.use_v2_api = True
        mock_settings.export.existence_check_batch_size = 250
        mock_confluence.get.side_effect = Exception("Network error")

        from confluence_markdown_exporter.confluence import fetch_deleted_page_ids

        result = fetch_deleted_page_ids(["100", "200"])
        assert result == set()

    @patch("confluence_markdown_exporter.confluence.settings")
    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_batches_large_sets(self, mock_confluence: MagicMock, mock_settings: MagicMock) -> None:
        """300 IDs are split into 2 v2-API batches of 250."""
        mock_settings.connection_config.use_v2_api = True
        mock_settings.export.existence_check_batch_size = 250
        ids = [str(i) for i in range(300)]
        mock_confluence.get.return_value = {"results": []}

        from confluence_markdown_exporter.confluence import fetch_deleted_page_ids

        fetch_deleted_page_ids(ids)

        assert mock_confluence.get.call_count == 2


class TestConfluenceLockSave:
    """Test cases for ConfluenceLock.save."""

    def test_save_is_atomic_on_success(self) -> None:
        """After save, the file contains valid, complete JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                pages={
                    "100": PageEntry(title="Page A", version=1, export_path="space/Page A.md"),
                }
            )

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            assert data["pages"]["100"]["version"] == 1
            tmp_files = list(Path(tmp).glob("*.tmp"))
            assert tmp_files == []

    def test_save_cleans_up_tmp_on_error(self) -> None:
        """When writing fails, no .tmp files are left behind."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                pages={
                    "100": PageEntry(title="Page A", version=1, export_path="space/Page A.md"),
                }
            )

            with (
                patch(
                    "confluence_markdown_exporter.utils.lockfile.Path.replace",
                    side_effect=OSError("disk error"),
                ),
                pytest.raises(OSError, match="disk error"),
            ):
                lock.save(lockfile_path)

            tmp_files = list(Path(tmp).glob("*.tmp"))
            assert tmp_files == []

    def test_save_preserves_original_on_error(self) -> None:
        """When writing fails, the original lockfile is not corrupted."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            original_data = {
                "lockfile_version": 1,
                "last_export": "2025-01-01T00:00:00+00:00",
                "pages": {
                    "100": {
                        "title": "Page A",
                        "version": 1,
                        "export_path": "space/Page A.md",
                    }
                },
            }
            lockfile_path.write_text(json.dumps(original_data), encoding="utf-8")

            lock = ConfluenceLock(
                pages={
                    "200": PageEntry(
                        title="Page B",
                        version=1,
                        export_path="space/Page B.md",
                    ),
                }
            )

            with (
                patch(
                    "confluence_markdown_exporter.utils.lockfile.Path.replace",
                    side_effect=OSError("disk error"),
                ),
                pytest.raises(OSError, match="disk error"),
            ):
                lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            assert data == original_data

    def test_save_with_delete_ids(self) -> None:
        """Save removes entries specified in delete_ids."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                pages={
                    "100": PageEntry(title="A", version=1, export_path="a.md"),
                    "200": PageEntry(title="B", version=1, export_path="b.md"),
                }
            )

            lock.save(lockfile_path, delete_ids={"100"})

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "100" not in saved["pages"]
            assert "200" in saved["pages"]


class TestConfluenceLockSaveSortsKeys:
    """Test cases for sorted key output in ConfluenceLock.save."""

    def test_save_sorts_page_keys(self) -> None:
        """Pages in the saved lockfile should be sorted by page ID."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                pages={
                    "999": PageEntry(title="Page C", version=1, export_path="c.md"),
                    "123": PageEntry(title="Page A", version=2, export_path="a.md"),
                    "456": PageEntry(title="Page B", version=1, export_path="b.md"),
                }
            )

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            page_ids = list(data["pages"].keys())
            assert page_ids == ["123", "456", "999"]

    def test_save_preserves_model_field_order(self) -> None:
        """Top-level keys should follow the model field order."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                pages={
                    "100": PageEntry(title="Page A", version=1, export_path="a.md"),
                }
            )

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            keys = list(data.keys())
            assert keys == ["lockfile_version", "last_export", "pages", "attachments"]


class TestAttachmentEntryModel:
    """Test cases for the AttachmentEntry pydantic model."""

    def test_attachment_entry_fields(self) -> None:
        """AttachmentEntry stores title, version, export_path and file_id."""
        entry = AttachmentEntry(
            title="diagram.png",
            version=3,
            export_path="space/attachments/abc123.png",
            file_id="abc123",
        )
        assert entry.title == "diagram.png"
        assert entry.version == 3
        assert entry.export_path == "space/attachments/abc123.png"
        assert entry.file_id == "abc123"


class TestConfluenceLockAttachments:
    """Test cases for attachment handling in ConfluenceLock."""

    def test_add_attachment(self) -> None:
        """add_attachment stores version and export_path keyed by attachment ID."""
        lock = ConfluenceLock()
        att = _make_mock_attachment(
            attachment_id="att-50",
            version_number=2,
            export_path="space/attachments/fid-att-50.png",
            file_id="fid-att-50",
        )

        lock.add_attachment(att)

        assert "att-50" in lock.attachments
        entry = lock.attachments["att-50"]
        assert entry.version == 2
        assert entry.export_path == "space/attachments/fid-att-50.png"
        assert entry.file_id == "fid-att-50"

    def test_add_attachment_updates_existing(self) -> None:
        """add_attachment overwrites an existing entry with the same ID."""
        lock = ConfluenceLock(
            attachments={
                "att-50": AttachmentEntry(
                    title="old.png", version=1, export_path="old.png", file_id="fid-50"
                ),
            }
        )
        att = _make_mock_attachment(
            attachment_id="att-50",
            version_number=2,
            export_path="new.png",
            file_id="fid-50",
            title="new.png",
        )

        lock.add_attachment(att)

        assert lock.attachments["att-50"].version == 2
        assert lock.attachments["att-50"].title == "new.png"

    def test_add_attachment_skips_none_version(self) -> None:
        """add_attachment is a no-op when attachment.version is None."""
        lock = ConfluenceLock()
        att = MagicMock()
        att.id = "att-50"
        att.version = None

        lock.add_attachment(att)

        assert "att-50" not in lock.attachments

    def test_save_and_load_round_trip_with_attachments(self) -> None:
        """Attachments survive a save/load round-trip."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                attachments={
                    "att-1": AttachmentEntry(
                        title="img.png",
                        version=3,
                        export_path="space/attachments/fid1.png",
                        file_id="fid1",
                    ),
                }
            )

            lock.save(lockfile_path)
            loaded = ConfluenceLock.load(lockfile_path)

            assert "att-1" in loaded.attachments
            assert loaded.attachments["att-1"].version == 3
            assert loaded.attachments["att-1"].file_id == "fid1"

    def test_save_sorts_attachment_keys(self) -> None:
        """Attachment keys in the saved lockfile are sorted."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                attachments={
                    "z-att": AttachmentEntry(
                        title="z.png", version=1, export_path="z.png", file_id="fz"
                    ),
                    "a-att": AttachmentEntry(
                        title="a.png", version=1, export_path="a.png", file_id="fa"
                    ),
                    "m-att": AttachmentEntry(
                        title="m.png", version=1, export_path="m.png", file_id="fm"
                    ),
                }
            )

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            att_ids = list(data["attachments"].keys())
            assert att_ids == ["a-att", "m-att", "z-att"]

    def test_save_with_delete_attachment_ids(self) -> None:
        """Save removes attachment entries specified in delete_attachment_ids."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                attachments={
                    "att-1": AttachmentEntry(
                        title="a.png", version=1, export_path="a.png", file_id="f1"
                    ),
                    "att-2": AttachmentEntry(
                        title="b.png", version=1, export_path="b.png", file_id="f2"
                    ),
                }
            )

            lock.save(lockfile_path, delete_attachment_ids={"att-1"})

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "att-1" not in saved["attachments"]
            assert "att-2" in saved["attachments"]

    def test_load_v1_lockfile_without_attachments(self) -> None:
        """A v1 lockfile (no attachments key) loads with an empty attachments dict."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            v1_data = {
                "lockfile_version": 1,
                "last_export": "2025-01-01T00:00:00+00:00",
                "pages": {
                    "100": {
                        "title": "Page A",
                        "version": 3,
                        "export_path": "space/Page A.md",
                    }
                },
            }
            lockfile_path.write_text(json.dumps(v1_data), encoding="utf-8")

            loaded = ConfluenceLock.load(lockfile_path)

            assert "100" in loaded.pages
            assert loaded.pages["100"].version == 3
            assert loaded.attachments == {}

    def test_save_upgrades_lockfile_version(self) -> None:
        """Saving a lock loaded from v1 upgrades lockfile_version to 2."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            v1_data = {
                "lockfile_version": 1,
                "last_export": "",
                "pages": {},
            }
            lockfile_path.write_text(json.dumps(v1_data), encoding="utf-8")

            lock = ConfluenceLock.load(lockfile_path)
            lock.save(lockfile_path)

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert saved["lockfile_version"] == 2
            assert "attachments" in saved


class TestLockfileManagerRecordAttachment:
    """Test cases for LockfileManager.record_attachment."""

    def test_record_attachment_creates_entry(self) -> None:
        """record_attachment writes the attachment entry to the lockfile."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock()

            att = _make_mock_attachment(
                attachment_id="att-10",
                version_number=2,
                export_path="space/attachments/fid-att-10.png",
            )
            LockfileManager.record_attachment(att)

            assert lockfile_path.exists()
            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "att-10" in saved["attachments"]
            assert saved["attachments"]["att-10"]["version"] == 2

    def test_record_attachment_does_nothing_when_not_initialized(self) -> None:
        """record_attachment is a no-op when LockfileManager has not been initialized."""
        att = _make_mock_attachment(
            attachment_id="att-10",
            version_number=2,
            export_path="space/attachments/fid.png",
        )
        # Should not raise
        LockfileManager.record_attachment(att)

    def test_record_attachment_updates_existing_entry(self) -> None:
        """record_attachment updates an existing attachment entry with the new version."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                attachments={
                    "att-10": AttachmentEntry(
                        title="img.png",
                        version=1,
                        export_path="space/attachments/fid.png",
                        file_id="fid",
                    ),
                }
            )

            att = _make_mock_attachment(
                attachment_id="att-10",
                version_number=3,
                export_path="space/attachments/fid.png",
                file_id="fid",
            )
            LockfileManager.record_attachment(att)

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert saved["attachments"]["att-10"]["version"] == 3


class TestLockfileManagerShouldDownloadAttachment:
    """Test cases for LockfileManager.should_download_attachment."""

    def test_attachment_not_in_lockfile_should_download(self) -> None:
        """An attachment not present in the lockfile should be downloaded."""
        LockfileManager._lock = ConfluenceLock(attachments={})

        att = _make_mock_attachment(
            attachment_id="att-10",
            version_number=1,
            export_path="space/attachments/fid.png",
        )
        assert LockfileManager.should_download_attachment(att) is True

    def test_attachment_same_version_same_path_should_not_download(self) -> None:
        """An attachment with same version and same path should NOT be downloaded."""
        LockfileManager._lock = ConfluenceLock(
            attachments={
                "att-10": AttachmentEntry(
                    title="img.png",
                    version=5,
                    export_path="space/attachments/fid.png",
                    file_id="fid",
                ),
            }
        )

        att = _make_mock_attachment(
            attachment_id="att-10",
            version_number=5,
            export_path="space/attachments/fid.png",
        )
        assert LockfileManager.should_download_attachment(att) is False

    def test_attachment_different_version_should_download(self) -> None:
        """An attachment whose version has changed should be downloaded."""
        LockfileManager._lock = ConfluenceLock(
            attachments={
                "att-10": AttachmentEntry(
                    title="img.png",
                    version=5,
                    export_path="space/attachments/fid.png",
                    file_id="fid",
                ),
            }
        )

        att = _make_mock_attachment(
            attachment_id="att-10",
            version_number=6,
            export_path="space/attachments/fid.png",
        )
        assert LockfileManager.should_download_attachment(att) is True

    def test_attachment_different_export_path_should_download(self) -> None:
        """An attachment whose export path changed should be re-downloaded."""
        LockfileManager._lock = ConfluenceLock(
            attachments={
                "att-10": AttachmentEntry(
                    title="img.png",
                    version=5,
                    export_path="old/fid.png",
                    file_id="fid",
                ),
            }
        )

        att = _make_mock_attachment(
            attachment_id="att-10",
            version_number=5,
            export_path="new/fid.png",
        )
        assert LockfileManager.should_download_attachment(att) is True

    def test_lock_is_none_should_download(self) -> None:
        """When lockfile manager is not initialized, all attachments should be downloaded."""
        assert LockfileManager._lock is None

        att = _make_mock_attachment(
            attachment_id="att-10",
            version_number=1,
            export_path="space/attachments/fid.png",
        )
        assert LockfileManager.should_download_attachment(att) is True

    def test_missing_file_on_disk_should_download(self) -> None:
        """An attachment whose file no longer exists on disk should be re-downloaded."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            LockfileManager._output_path = output
            LockfileManager._lock = ConfluenceLock(
                attachments={
                    "att-10": AttachmentEntry(
                        title="img.png",
                        version=5,
                        export_path="space/attachments/fid.png",
                        file_id="fid",
                    ),
                }
            )

            # File does NOT exist on disk
            att = _make_mock_attachment(
                attachment_id="att-10",
                version_number=5,
                export_path="space/attachments/fid.png",
            )
            assert LockfileManager.should_download_attachment(att) is True

    def test_existing_file_unchanged_should_not_download(self) -> None:
        """An attachment whose file exists and is up-to-date should NOT be re-downloaded."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            att_file = output / "space" / "attachments" / "fid.png"
            att_file.parent.mkdir(parents=True)
            att_file.write_bytes(b"PNG data")

            LockfileManager._output_path = output
            LockfileManager._lock = ConfluenceLock(
                attachments={
                    "att-10": AttachmentEntry(
                        title="img.png",
                        version=5,
                        export_path="space/attachments/fid.png",
                        file_id="fid",
                    ),
                }
            )

            att = _make_mock_attachment(
                attachment_id="att-10",
                version_number=5,
                export_path="space/attachments/fid.png",
            )
            assert LockfileManager.should_download_attachment(att) is False

    def test_version_none_should_download(self) -> None:
        """An attachment with version=None should always be downloaded."""
        LockfileManager._lock = ConfluenceLock(
            attachments={
                "att-10": AttachmentEntry(
                    title="img.png",
                    version=5,
                    export_path="space/attachments/fid.png",
                    file_id="fid",
                ),
            }
        )

        att = MagicMock()
        att.id = "att-10"
        att.version = None
        att.export_path = Path("space/attachments/fid.png")
        assert LockfileManager.should_download_attachment(att) is True


class TestLockfileManagerInitWithAttachments:
    """Test cases for LockfileManager.init with attachment state."""

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_init_loads_existing_attachments(
        self,
        mock_get_settings: MagicMock,
    ) -> None:
        """init() loads attachment entries from an existing lockfile."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_get_settings.return_value.export.output_path = Path(tmp)
            mock_get_settings.return_value.export.lockfile_name = LOCKFILE_FILENAME
            mock_get_settings.return_value.export.skip_unchanged = True
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            data = {
                "lockfile_version": 2,
                "last_export": "2025-01-01T00:00:00+00:00",
                "pages": {},
                "attachments": {
                    "att-1": {
                        "title": "img.png",
                        "version": 4,
                        "export_path": "space/attachments/fid1.png",
                        "file_id": "fid1",
                    }
                },
            }
            lockfile_path.write_text(json.dumps(data), encoding="utf-8")

            LockfileManager.init()

            assert LockfileManager._lock is not None
            assert "att-1" in LockfileManager._lock.attachments
            assert LockfileManager._lock.attachments["att-1"].version == 4

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_init_with_v1_lockfile_gets_empty_attachments(
        self,
        mock_get_settings: MagicMock,
    ) -> None:
        """init() with a v1 lockfile (no attachments) starts with empty attachment dict."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_get_settings.return_value.export.output_path = Path(tmp)
            mock_get_settings.return_value.export.lockfile_name = LOCKFILE_FILENAME
            mock_get_settings.return_value.export.skip_unchanged = True
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            v1_data = {
                "lockfile_version": 1,
                "last_export": "",
                "pages": {
                    "100": {
                        "title": "A",
                        "version": 1,
                        "export_path": "a.md",
                    }
                },
            }
            lockfile_path.write_text(json.dumps(v1_data), encoding="utf-8")

            LockfileManager.init()

            assert LockfileManager._lock is not None
            assert LockfileManager._lock.attachments == {}
            assert "100" in LockfileManager._lock.pages
