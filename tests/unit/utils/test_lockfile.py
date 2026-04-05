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
from confluence_markdown_exporter.utils.lockfile import OrgEntry
from confluence_markdown_exporter.utils.lockfile import PageEntry
from confluence_markdown_exporter.utils.lockfile import SpaceEntry

LOCKFILE_FILENAME = "confluence-lock.json"
_TEST_BASE_URL = "https://test.atlassian.net"
_TEST_SPACE_KEY = "TEST"


def _make_mock_page(
    page_id: int,
    version_number: int,
    export_path: str,
    *,
    base_url: str = _TEST_BASE_URL,
    space_key: str = _TEST_SPACE_KEY,
) -> MagicMock:
    """Create a mock page/descendant with the attributes used by LockfileManager."""
    page = MagicMock()
    page.id = page_id
    page.version.number = version_number
    page.export_path = Path(export_path)
    page.title = f"Page {page_id}"
    page.base_url = base_url
    page.space.key = space_key
    return page


def _lock_with_pages(
    pages: dict,
    *,
    base_url: str = _TEST_BASE_URL,
    space_key: str = _TEST_SPACE_KEY,
) -> ConfluenceLock:
    """Build a ConfluenceLock with pages nested under the given org/space."""
    return ConfluenceLock(
        orgs={
            base_url: OrgEntry(
                spaces={space_key: SpaceEntry(pages=pages)}
            )
        }
    )


def _lock_data(
    pages: dict,
    *,
    base_url: str = _TEST_BASE_URL,
    space_key: str = _TEST_SPACE_KEY,
) -> dict:
    """Build a lockfile JSON-compatible dict with pages nested under org/space."""
    return {
        "lockfile_version": 2,
        "last_export": "2025-01-01T00:00:00+00:00",
        "orgs": {
            base_url: {
                "spaces": {
                    space_key: {"pages": pages}
                }
            }
        },
    }


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
            assert LockfileManager._lock.orgs == {}
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
            data = _lock_data(
                {"100": {"title": "Page A", "version": 3, "export_path": "space/Page A.md"}}
            )
            lockfile_path.write_text(json.dumps(data), encoding="utf-8")

            LockfileManager.init()

            assert LockfileManager._lock is not None
            entry = LockfileManager._lock.get_page("100")
            assert entry is not None
            assert entry.version == 3

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
            data = _lock_data({
                "100": {"title": "A", "version": 1, "export_path": "a.md"},
                "200": {"title": "B", "version": 2, "export_path": "b.md"},
            })
            lockfile_path.write_text(json.dumps(data), encoding="utf-8")

            LockfileManager.init()

            assert set(LockfileManager._all_entries_snapshot.keys()) == {"100", "200"}
            assert LockfileManager._seen_page_ids == set()

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_init_discards_v1_lockfile(
        self,
        mock_get_settings: MagicMock,
    ) -> None:
        """A v1 lockfile (flat pages dict) is discarded and replaced with an empty lock."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_get_settings.return_value.export.output_path = Path(tmp)
            mock_get_settings.return_value.export.lockfile_name = LOCKFILE_FILENAME
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            v1_data = {
                "lockfile_version": 1,
                "last_export": "2025-01-01T00:00:00+00:00",
                "pages": {
                    "100": {"title": "Old Page", "version": 1, "export_path": "old.md"},
                },
            }
            lockfile_path.write_text(json.dumps(v1_data), encoding="utf-8")

            LockfileManager.init()

            assert LockfileManager._lock is not None
            assert LockfileManager._lock.orgs == {}


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
            pages = saved["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]
            assert "100" in pages
            assert pages["100"]["version"] == 1

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
            LockfileManager._lock = _lock_with_pages({
                "100": PageEntry(title="Page A", version=1, export_path="space/Page A.md"),
            })

            page = _make_mock_page(page_id=100, version_number=2, export_path="space/Page A.md")
            LockfileManager.record_page(page)

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            pages = saved["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]
            assert pages["100"]["version"] == 2

    def test_record_page_adds_to_seen_page_ids(self) -> None:
        """record_page adds the page ID to the seen set."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock()

            page = _make_mock_page(page_id=100, version_number=1, export_path="a.md")
            LockfileManager.record_page(page)

            assert "100" in LockfileManager._seen_page_ids

    def test_record_page_across_multiple_orgs_and_spaces(self) -> None:
        """Pages from different orgs and spaces are stored independently."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock()

            page_a = _make_mock_page(
                100, 1, "a.md", base_url="https://org-a.atlassian.net", space_key="AAA"
            )
            page_b = _make_mock_page(
                200, 1, "b.md", base_url="https://org-b.atlassian.net", space_key="BBB"
            )
            LockfileManager.record_page(page_a)
            LockfileManager.record_page(page_b)

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "100" in saved["orgs"]["https://org-a.atlassian.net"]["spaces"]["AAA"]["pages"]
            assert "200" in saved["orgs"]["https://org-b.atlassian.net"]["spaces"]["BBB"]["pages"]


class TestLockfileManagerShouldExport:
    """Test cases for LockfileManager.should_export."""

    def test_page_not_in_lockfile_should_export(self) -> None:
        """A page not present in the lockfile should be exported."""
        LockfileManager._lock = _lock_with_pages({
            "999": PageEntry(title="Other", version=1, export_path="other.md"),
        })

        page = _make_mock_page(page_id=123, version_number=1, export_path="space/New.md")
        assert LockfileManager.should_export(page) is True

    def test_page_in_lockfile_same_version_same_path_should_not_export(self) -> None:
        """A page with same version and same path should NOT be exported."""
        LockfileManager._lock = _lock_with_pages({
            "123": PageEntry(title="Page A", version=5, export_path="space/Page A.md"),
        })

        page = _make_mock_page(page_id=123, version_number=5, export_path="space/Page A.md")
        assert LockfileManager.should_export(page) is False

    def test_page_in_lockfile_different_version_should_export(self) -> None:
        """A page whose version has changed should be exported."""
        LockfileManager._lock = _lock_with_pages({
            "123": PageEntry(title="Page A", version=5, export_path="space/Page A.md"),
        })

        page = _make_mock_page(page_id=123, version_number=6, export_path="space/Page A.md")
        assert LockfileManager.should_export(page) is True

    def test_page_in_lockfile_different_export_path_should_export(self) -> None:
        """A page whose export path has changed (file moved) should be exported."""
        LockfileManager._lock = _lock_with_pages({
            "123": PageEntry(title="Page A", version=5, export_path="old/Page A.md"),
        })

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
            LockfileManager._lock = _lock_with_pages({
                "123": PageEntry(title="Page A", version=5, export_path="space/Page A.md"),
            })

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
            LockfileManager._lock = _lock_with_pages({
                "123": PageEntry(title="Page A", version=5, export_path="space/Page A.md"),
            })

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
            LockfileManager._lock = _lock_with_pages({
                "100": PageEntry(title="Removed", version=1, export_path="space/Removed.md"),
            })
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.all_pages())
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
            LockfileManager._lock = _lock_with_pages({
                "100": PageEntry(title="Removed", version=1, export_path="space/Removed.md"),
                "200": PageEntry(title="Kept", version=1, export_path="space/Kept.md"),
            })
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.all_pages())
            LockfileManager._seen_page_ids = {"200"}

            LockfileManager.remove_pages({"100"})

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            pages = saved["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]
            assert "100" not in pages
            assert "200" in pages

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
                "100": PageEntry(title="Page", version=1, export_path="old/Page.md"),
            }
            LockfileManager._lock = _lock_with_pages({
                "100": PageEntry(title="Page", version=2, export_path="new/Page.md"),
            })
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
            LockfileManager._lock = _lock_with_pages({
                "100": PageEntry(title="Still", version=1, export_path="space/Still.md"),
            })
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.all_pages())
            LockfileManager._seen_page_ids = set()

            LockfileManager.remove_pages(set())

            assert md_file.exists()
            assert LockfileManager._lock.get_page("100") is not None

    def test_cleanup_keeps_unchanged_seen_pages(self) -> None:
        """Pages that were seen during export are not checked via API."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            lockfile_path = output / LOCKFILE_FILENAME
            LockfileManager._output_path = output
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = _lock_with_pages({
                "100": PageEntry(title="Seen", version=1, export_path="a.md"),
            })
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.all_pages())
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
            LockfileManager._lock = _lock_with_pages({
                "100": PageEntry(title="Gone", version=1, export_path="space/Gone.md"),
            })
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.all_pages())
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
            LockfileManager._lock = _lock_with_pages({
                "100": PageEntry(title="Safe", version=1, export_path="space/Safe.md"),
            })
            LockfileManager._all_entries_snapshot = dict(LockfileManager._lock.all_pages())
            LockfileManager._seen_page_ids = set()

            # Pass empty set: safe default — don't delete anything on API failure
            LockfileManager.remove_pages(set())

            assert md_file.exists()
            assert LockfileManager._lock.get_page("100") is not None


class TestFetchDeletedPageIds:
    """Test cases for fetch_deleted_page_ids."""

    def test_empty_input_returns_empty(self) -> None:
        """Empty list returns empty set."""
        from confluence_markdown_exporter.confluence import fetch_deleted_page_ids

        result = fetch_deleted_page_ids([], _TEST_BASE_URL)
        assert result == set()

    @patch("confluence_markdown_exporter.confluence.settings")
    @patch("confluence_markdown_exporter.confluence.get_thread_confluence")
    def test_returns_deleted_ids(
        self, mock_get_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Returns IDs that no longer exist on Confluence."""
        mock_settings.connection_config.use_v2_api = True
        mock_settings.export.existence_check_batch_size = 250
        mock_client = MagicMock()
        mock_client.get.return_value = {
            "results": [{"id": "100"}, {"id": "300"}],
        }
        mock_get_client.return_value = mock_client

        from confluence_markdown_exporter.confluence import fetch_deleted_page_ids

        result = fetch_deleted_page_ids(["100", "200", "300"], _TEST_BASE_URL)
        assert result == {"200"}

    @patch("confluence_markdown_exporter.confluence.settings")
    @patch("confluence_markdown_exporter.confluence.get_thread_confluence")
    def test_api_error_returns_no_deleted_ids(
        self, mock_get_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """On API error, returns empty set (safe: don't delete anything)."""
        mock_settings.connection_config.use_v2_api = True
        mock_settings.export.existence_check_batch_size = 250
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Network error")
        mock_get_client.return_value = mock_client

        from confluence_markdown_exporter.confluence import fetch_deleted_page_ids

        result = fetch_deleted_page_ids(["100", "200"], _TEST_BASE_URL)
        assert result == set()

    @patch("confluence_markdown_exporter.confluence.settings")
    @patch("confluence_markdown_exporter.confluence.get_thread_confluence")
    def test_batches_large_sets(
        self, mock_get_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """300 IDs are split into 2 v2-API batches of 250."""
        mock_settings.connection_config.use_v2_api = True
        mock_settings.export.existence_check_batch_size = 250
        ids = [str(i) for i in range(300)]
        mock_client = MagicMock()
        mock_client.get.return_value = {"results": []}
        mock_get_client.return_value = mock_client

        from confluence_markdown_exporter.confluence import fetch_deleted_page_ids

        fetch_deleted_page_ids(ids, _TEST_BASE_URL)

        assert mock_client.get.call_count == 2


class TestConfluenceLockSave:
    """Test cases for ConfluenceLock.save."""

    def test_save_is_atomic_on_success(self) -> None:
        """After save, the file contains valid, complete JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = _lock_with_pages({
                "100": PageEntry(title="Page A", version=1, export_path="space/Page A.md"),
            })

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            pages = data["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]
            assert pages["100"]["version"] == 1
            tmp_files = list(Path(tmp).glob("*.tmp"))
            assert tmp_files == []

    def test_save_cleans_up_tmp_on_error(self) -> None:
        """When writing fails, no .tmp files are left behind."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = _lock_with_pages({
                "100": PageEntry(title="Page A", version=1, export_path="space/Page A.md"),
            })

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
            original_data = _lock_data({
                "100": {"title": "Page A", "version": 1, "export_path": "space/Page A.md"},
            })
            lockfile_path.write_text(json.dumps(original_data), encoding="utf-8")

            lock = _lock_with_pages({
                "200": PageEntry(title="Page B", version=1, export_path="space/Page B.md"),
            })

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
            pages = data["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]
            assert "100" in pages
            assert "200" not in pages

    def test_save_with_delete_ids(self) -> None:
        """Save removes entries specified in delete_ids."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = _lock_with_pages({
                "100": PageEntry(title="A", version=1, export_path="a.md"),
                "200": PageEntry(title="B", version=1, export_path="b.md"),
            })

            lock.save(lockfile_path, delete_ids={"100"})

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            pages = saved["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]
            assert "100" not in pages
            assert "200" in pages


class TestConfluenceLockSaveSortsKeys:
    """Test cases for sorted key output in ConfluenceLock.save."""

    def test_save_sorts_page_keys(self) -> None:
        """Pages in the saved lockfile should be sorted by page ID."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = _lock_with_pages({
                "999": PageEntry(title="Page C", version=1, export_path="c.md"),
                "123": PageEntry(title="Page A", version=2, export_path="a.md"),
                "456": PageEntry(title="Page B", version=1, export_path="b.md"),
            })

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            pages = data["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]
            page_ids = list(pages.keys())
            assert page_ids == ["123", "456", "999"]

    def test_save_preserves_model_field_order(self) -> None:
        """Top-level keys should follow the model field order."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = _lock_with_pages({
                "100": PageEntry(title="Page A", version=1, export_path="a.md"),
            })

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            keys = list(data.keys())
            assert keys == ["lockfile_version", "last_export", "orgs"]

    def test_save_sorts_spaces_and_orgs(self) -> None:
        """Orgs and spaces within the saved lockfile should be sorted."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = ConfluenceLock(
                orgs={
                    "https://z-org.atlassian.net": OrgEntry(
                        spaces={
                            "ZZZ": SpaceEntry(
                                pages={"1": PageEntry(title="P", version=1, export_path="p.md")}
                            ),
                            "AAA": SpaceEntry(pages={}),
                        }
                    ),
                    "https://a-org.atlassian.net": OrgEntry(spaces={}),
                }
            )

            lock.save(lockfile_path)

            data = json.loads(lockfile_path.read_text(encoding="utf-8"))
            org_keys = list(data["orgs"].keys())
            assert org_keys == ["https://a-org.atlassian.net", "https://z-org.atlassian.net"]
            space_keys = list(data["orgs"]["https://z-org.atlassian.net"]["spaces"].keys())
            assert space_keys == ["AAA", "ZZZ"]


class TestAttachmentEntryTracking:
    """Tests for attachment tracking in the lock file."""

    def test_page_entry_stores_attachments(self) -> None:
        """PageEntry persists attachment entries keyed by attachment ID."""
        entry = PageEntry(
            title="Page",
            version=1,
            export_path="a.md",
            attachments={
                "att1": AttachmentEntry(version=3, path="space/attachments/uuid-a.png"),
            },
        )
        assert entry.attachments["att1"].version == 3
        assert entry.attachments["att1"].path == "space/attachments/uuid-a.png"

    def test_page_entry_attachments_default_empty(self) -> None:
        """PageEntry.attachments defaults to empty dict (backward-compatible)."""
        entry = PageEntry(title="Page", version=1, export_path="a.md")
        assert entry.attachments == {}

    def test_lock_file_roundtrip_with_attachments(self) -> None:
        """Attachment entries survive a JSON save/load cycle."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            lock = _lock_with_pages({
                "100": PageEntry(
                    title="Page A",
                    version=1,
                    export_path="a.md",
                    attachments={
                        "att1": AttachmentEntry(version=2, path="space/attachments/file.png"),
                    },
                ),
            })

            lock.save(lockfile_path)

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            att = saved["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]["100"]["attachments"]["att1"]
            assert att["version"] == 2
            assert att["path"] == "space/attachments/file.png"

    def test_lock_file_missing_attachments_field_loads_as_empty(self) -> None:
        """Old lock files without 'attachments' field load without error."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / "confluence-lock.json"
            old_format = _lock_data({
                "100": {"title": "Page A", "version": 3, "export_path": "a.md"},
            })
            lockfile_path.write_text(json.dumps(old_format), encoding="utf-8")

            lock = ConfluenceLock.load(lockfile_path)

            entry = lock.get_page("100")
            assert entry is not None
            assert entry.attachments == {}

    def test_record_page_stores_attachment_entries(self) -> None:
        """record_page persists attachment entries to the lock file."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / LOCKFILE_FILENAME
            LockfileManager._lockfile_path = lockfile_path
            LockfileManager._lock = ConfluenceLock()

            page = _make_mock_page(page_id=100, version_number=1, export_path="a.md")
            attachment_entries = {
                "att42": AttachmentEntry(version=5, path="space/attachments/abc.png"),
            }
            LockfileManager.record_page(page, attachment_entries)

            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            pages = saved["orgs"][_TEST_BASE_URL]["spaces"][_TEST_SPACE_KEY]["pages"]
            att = pages["100"]["attachments"]["att42"]
            assert att["version"] == 5
            assert att["path"] == "space/attachments/abc.png"

    def test_get_page_attachment_entries_returns_entries(self) -> None:
        """get_page_attachment_entries returns the stored attachment dict for a page."""
        LockfileManager._lock = _lock_with_pages({
            "100": PageEntry(
                title="Page",
                version=1,
                export_path="a.md",
                attachments={
                    "att1": AttachmentEntry(version=2, path="space/attachments/x.png"),
                },
            ),
        })

        entries = LockfileManager.get_page_attachment_entries("100")
        assert "att1" in entries
        assert entries["att1"].version == 2

    def test_get_page_attachment_entries_returns_empty_for_unknown_page(self) -> None:
        """get_page_attachment_entries returns {} for a page not in the lock."""
        LockfileManager._lock = _lock_with_pages({})
        assert LockfileManager.get_page_attachment_entries("999") == {}

    def test_get_page_attachment_entries_returns_empty_when_not_initialized(self) -> None:
        """get_page_attachment_entries returns {} when the manager is not initialized."""
        assert LockfileManager._lock is None
        assert LockfileManager.get_page_attachment_entries("100") == {}
