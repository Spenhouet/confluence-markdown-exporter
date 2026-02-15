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


class TestConfluenceLockAtomicSave:
    """Test cases for atomic write behaviour in ConfluenceLock.save."""

    def test_save_is_atomic_on_success(self) -> None:
        """After save, the file contains valid, complete JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / ".confluence-lock.json"
            lock = ConfluenceLock(
                pages={
                    "100": PageEntry(title="Page A", version=1, export_path="space/Page A.md"),
                }
            )

            lock.save(lockfile_path)

            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            assert data["pages"]["100"]["version"] == 1
            # No .tmp files left behind
            tmp_files = list(Path(tmp).glob("*.tmp"))
            assert tmp_files == []

    def test_save_cleans_up_tmp_on_error(self) -> None:
        """When writing fails, no .tmp files are left behind."""
        with tempfile.TemporaryDirectory() as tmp:
            lockfile_path = Path(tmp) / ".confluence-lock.json"
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
            lockfile_path = Path(tmp) / ".confluence-lock.json"
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

            # Original file should be intact
            content = lockfile_path.read_text(encoding="utf-8")
            data = json.loads(content)
            assert data == original_data
