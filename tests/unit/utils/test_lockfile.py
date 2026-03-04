"""Unit tests for lockfile module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.utils.lockfile import LOCKFILE_FILENAME
from confluence_markdown_exporter.utils.lockfile import ConfluenceLock
from confluence_markdown_exporter.utils.lockfile import LockfileManager
from confluence_markdown_exporter.utils.lockfile import PageEntry


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

            page = _make_mock_page(
                page_id=100, version_number=1, export_path="space/Page A.md"
            )
            LockfileManager.record_page(page)

            assert lockfile_path.exists()
            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "100" in saved["pages"]
            assert saved["pages"]["100"]["version"] == 1

    def test_record_page_does_nothing_when_not_initialized(self) -> None:
        """record_page is a no-op when LockfileManager has not been initialized."""
        page = _make_mock_page(
            page_id=100, version_number=1, export_path="space/Page A.md"
        )

        # Should not raise
        LockfileManager.record_page(page)

    def test_record_page_updates_existing_entry(self) -> None:
        """record_page updates an existing page entry with the new version."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Page A", version=1, export_path="space/Page A.md"
                    ),
                }
            )

            page = _make_mock_page(
                page_id=100, version_number=2, export_path="space/Page A.md"
            )
            LockfileManager.record_page(page)

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert saved["pages"]["100"]["version"] == 2

    def test_record_page_adds_to_seen_page_ids(self) -> None:
        """record_page adds the page ID to the seen set."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock()

            page = _make_mock_page(
                page_id=100, version_number=1, export_path="a.md"
            )
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

        page = _make_mock_page(
            page_id=123, version_number=1, export_path="space/New.md"
        )
        assert LockfileManager.should_export(page) is True

    def test_page_in_lockfile_same_version_same_path_should_not_export(self) -> None:
        """A page with same version and same path should NOT be exported."""
        LockfileManager._lock = ConfluenceLock(
            pages={
                "123": PageEntry(
                    title="Page A", version=5, export_path="space/Page A.md"
                ),
            }
        )

        page = _make_mock_page(
            page_id=123, version_number=5, export_path="space/Page A.md"
        )
        assert LockfileManager.should_export(page) is False

    def test_page_in_lockfile_different_version_should_export(self) -> None:
        """A page whose version has changed should be exported."""
        LockfileManager._lock = ConfluenceLock(
            pages={
                "123": PageEntry(
                    title="Page A", version=5, export_path="space/Page A.md"
                ),
            }
        )

        page = _make_mock_page(
            page_id=123, version_number=6, export_path="space/Page A.md"
        )
        assert LockfileManager.should_export(page) is True

    def test_page_in_lockfile_different_export_path_should_export(self) -> None:
        """A page whose export path has changed (file moved) should be exported."""
        LockfileManager._lock = ConfluenceLock(
            pages={
                "123": PageEntry(
                    title="Page A", version=5, export_path="old/Page A.md"
                ),
            }
        )

        page = _make_mock_page(
            page_id=123, version_number=5, export_path="new/Page A.md"
        )
        assert LockfileManager.should_export(page) is True

    def test_lock_is_none_should_export(self) -> None:
        """When lockfile manager is not initialized, all pages should be exported."""
        assert LockfileManager._lock is None

        page = _make_mock_page(
            page_id=123, version_number=1, export_path="space/Page A.md"
        )
        assert LockfileManager.should_export(page) is True


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
        LockfileManager.cleanup()  # Should not raise

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
            LockfileManager._all_entries_snapshot = dict(
                LockfileManager._lock.pages
            )
            LockfileManager._seen_page_ids = set()  # page 100 not seen

            with patch.object(
                LockfileManager,
                "_check_pages_exist",
                return_value=set(),
            ):
                LockfileManager.cleanup()

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
            LockfileManager._all_entries_snapshot = dict(
                LockfileManager._lock.pages
            )
            LockfileManager._seen_page_ids = {"200"}

            with patch.object(
                LockfileManager,
                "_check_pages_exist",
                return_value=set(),
            ):
                LockfileManager.cleanup()

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

            with patch.object(
                LockfileManager,
                "_check_pages_exist",
                return_value=set(),
            ):
                LockfileManager.cleanup()

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
            LockfileManager._all_entries_snapshot = dict(
                LockfileManager._lock.pages
            )
            LockfileManager._seen_page_ids = set()

            with patch.object(
                LockfileManager,
                "_check_pages_exist",
                return_value={"100"},
            ):
                LockfileManager.cleanup()

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
            LockfileManager._all_entries_snapshot = dict(
                LockfileManager._lock.pages
            )
            LockfileManager._seen_page_ids = {"100"}

            with patch.object(
                LockfileManager,
                "_check_pages_exist",
            ) as mock_check:
                LockfileManager.cleanup()
                # Should not be called since all pages are seen
                mock_check.assert_not_called()

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
            LockfileManager._all_entries_snapshot = dict(
                LockfileManager._lock.pages
            )
            LockfileManager._seen_page_ids = set()

            with patch.object(
                LockfileManager,
                "_check_pages_exist",
                return_value=set(),
            ):
                LockfileManager.cleanup()  # Should not raise

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
            LockfileManager._all_entries_snapshot = dict(
                LockfileManager._lock.pages
            )
            LockfileManager._seen_page_ids = set()

            # _check_pages_exist returns all IDs on failure (safe default)
            with patch.object(
                LockfileManager,
                "_check_pages_exist",
                return_value={"100"},
            ):
                LockfileManager.cleanup()

            assert md_file.exists()
            assert "100" in LockfileManager._lock.pages


class TestCheckPagesExist:
    """Test cases for LockfileManager._check_pages_exist."""

    def test_empty_input_returns_empty(self) -> None:
        """Empty set of IDs returns empty set."""
        result = LockfileManager._check_pages_exist(set())
        assert result == set()

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_returns_existing_ids(self, mock_confluence: MagicMock) -> None:
        """Returns IDs that exist on Confluence."""
        mock_confluence.get.return_value = {
            "results": [{"id": "100"}, {"id": "300"}],
        }

        result = LockfileManager._check_pages_exist({"100", "200", "300"})
        assert result == {"100", "300"}

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_api_error_returns_all_ids(
        self, mock_confluence: MagicMock
    ) -> None:
        """On API error, returns all IDs in the batch (safe default)."""
        mock_confluence.get.side_effect = Exception("Network error")

        result = LockfileManager._check_pages_exist({"100", "200"})
        assert result == {"100", "200"}

    @patch("confluence_markdown_exporter.confluence.confluence")
    def test_batches_large_sets(self, mock_confluence: MagicMock) -> None:
        """IDs are split into batches of _BATCH_SIZE."""
        ids = {str(i) for i in range(300)}
        mock_confluence.get.return_value = {"results": []}

        LockfileManager._check_pages_exist(ids)

        assert mock_confluence.get.call_count == 2


class TestConfluenceLockSave:
    """Test cases for ConfluenceLock.save."""

    def test_save_is_atomic_on_success(self) -> None:
        """After save, the file contains valid, complete JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                pages={
                    "100": PageEntry(
                        title="Page A", version=1, export_path="space/Page A.md"
                    ),
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
                    "100": PageEntry(
                        title="Page A", version=1, export_path="space/Page A.md"
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
            lockfile_path.write_text(
                json.dumps(original_data), encoding="utf-8"
            )

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
                    "100": PageEntry(
                        title="A", version=1, export_path="a.md"
                    ),
                    "200": PageEntry(
                        title="B", version=1, export_path="b.md"
                    ),
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
                    "999": PageEntry(
                        title="Page C", version=1, export_path="c.md"
                    ),
                    "123": PageEntry(
                        title="Page A", version=2, export_path="a.md"
                    ),
                    "456": PageEntry(
                        title="Page B", version=1, export_path="b.md"
                    ),
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
                    "100": PageEntry(
                        title="Page A", version=1, export_path="a.md"
                    ),
                }
            )

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            keys = list(data.keys())
            assert keys == ["lockfile_version", "last_export", "pages"]
