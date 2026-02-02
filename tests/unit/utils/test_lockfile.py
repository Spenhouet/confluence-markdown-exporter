"""Unit tests for lockfile module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from confluence_markdown_exporter.utils.lockfile import LOCKFILE_FILENAME
from confluence_markdown_exporter.utils.lockfile import LOCKFILE_VERSION
from confluence_markdown_exporter.utils.lockfile import ConfluenceLock
from confluence_markdown_exporter.utils.lockfile import LockfileManager
from confluence_markdown_exporter.utils.lockfile import PageEntry


class TestPageEntry:
    """Test cases for PageEntry model."""

    def test_create_page_entry(self) -> None:
        """Test creating a PageEntry instance."""
        entry = PageEntry(
            title="Test Page",
            version=5,
            export_path="SPACE/Test Page.md",
        )

        assert entry.title == "Test Page"
        assert entry.version == 5
        assert entry.export_path == "SPACE/Test Page.md"

    def test_page_entry_serialization(self) -> None:
        """Test PageEntry serialization to JSON."""
        entry = PageEntry(
            title="Test Page",
            version=3,
            export_path="SPACE/subdir/Test Page.md",
        )

        data = entry.model_dump()
        assert data == {
            "title": "Test Page",
            "version": 3,
            "export_path": "SPACE/subdir/Test Page.md",
        }


class TestConfluenceLock:
    """Test cases for ConfluenceLock model."""

    def test_create_empty_lock(self) -> None:
        """Test creating an empty ConfluenceLock instance."""
        lock = ConfluenceLock()

        assert lock.lockfile_version == LOCKFILE_VERSION
        assert lock.last_export == ""
        assert lock.pages == {}

    def test_create_lock_with_pages(self) -> None:
        """Test creating ConfluenceLock with pages."""
        lock = ConfluenceLock(
            pages={
                "123": PageEntry(
                    title="Page 1",
                    version=1,
                    export_path="SPACE/Page 1.md",
                ),
                "456": PageEntry(
                    title="Page 2",
                    version=2,
                    export_path="SPACE/Page 2.md",
                ),
            }
        )

        assert len(lock.pages) == 2
        assert "123" in lock.pages
        assert "456" in lock.pages
        assert lock.pages["123"].title == "Page 1"
        assert lock.pages["456"].version == 2

    def test_load_nonexistent_file(self) -> None:
        """Test loading from non-existent file returns empty lock."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME

            lock = ConfluenceLock.load(lockfile_path)

            assert lock.lockfile_version == LOCKFILE_VERSION
            assert lock.pages == {}

    def test_load_existing_file(self) -> None:
        """Test loading from existing lock file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME
            lockfile_data = {
                "lockfile_version": 1,
                "last_export": "2024-01-15T10:30:00+00:00",
                "pages": {
                    "123": {
                        "title": "Test Page",
                        "version": 5,
                        "export_path": "SPACE/Test Page.md",
                    }
                },
            }
            lockfile_path.write_text(json.dumps(lockfile_data), encoding="utf-8")

            lock = ConfluenceLock.load(lockfile_path)

            assert lock.lockfile_version == 1
            assert lock.last_export == "2024-01-15T10:30:00+00:00"
            assert len(lock.pages) == 1
            assert lock.pages["123"].title == "Test Page"
            assert lock.pages["123"].version == 5

    def test_load_invalid_json(self) -> None:
        """Test loading invalid JSON returns empty lock."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME
            lockfile_path.write_text("not valid json", encoding="utf-8")

            lock = ConfluenceLock.load(lockfile_path)

            assert lock.lockfile_version == LOCKFILE_VERSION
            assert lock.pages == {}

    def test_save_lock(self) -> None:
        """Test saving lock file to disk."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME
            lock = ConfluenceLock(
                pages={
                    "123": PageEntry(
                        title="Test Page",
                        version=5,
                        export_path="SPACE/Test Page.md",
                    )
                }
            )

            lock.save(lockfile_path)

            assert lockfile_path.exists()
            saved_data = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert saved_data["lockfile_version"] == LOCKFILE_VERSION
            assert "last_export" in saved_data
            assert saved_data["pages"]["123"]["title"] == "Test Page"

    def test_save_creates_parent_directories(self) -> None:
        """Test that save creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile_path = Path(temp_dir) / "subdir" / "nested" / LOCKFILE_FILENAME
            lock = ConfluenceLock()

            lock.save(lockfile_path)

            assert lockfile_path.exists()

    def test_save_updates_last_export(self) -> None:
        """Test that save updates the last_export timestamp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME
            lock = ConfluenceLock()
            assert lock.last_export == ""

            lock.save(lockfile_path)

            assert lock.last_export != ""
            # Check it's a valid ISO format datetime
            assert "T" in lock.last_export

    def test_save_merges_with_existing(self) -> None:
        """Test that save merges with existing lock file (concurrent write safety)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME

            # Simulate process A: save page 1
            lock_a = ConfluenceLock(
                pages={
                    "1": PageEntry(title="Page 1", version=1, export_path="P1.md")
                }
            )
            lock_a.save(lockfile_path)

            # Simulate process B: starts with different state, saves page 2
            lock_b = ConfluenceLock(
                pages={
                    "2": PageEntry(title="Page 2", version=1, export_path="P2.md")
                }
            )
            lock_b.save(lockfile_path)

            # Verify both pages are in the file
            saved = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "1" in saved["pages"]
            assert "2" in saved["pages"]
            assert saved["pages"]["1"]["title"] == "Page 1"
            assert saved["pages"]["2"]["title"] == "Page 2"

            # Verify lock_b's state was updated to include merged data
            assert "1" in lock_b.pages
            assert "2" in lock_b.pages

    def test_add_page_with_version(self) -> None:
        """Test adding a page with version info."""
        lock = ConfluenceLock()

        # Create mock page with version
        mock_page = MagicMock()
        mock_page.id = 123
        mock_page.title = "Test Page"
        mock_page.version = MagicMock()
        mock_page.version.number = 5
        mock_page.export_path = Path("SPACE/Test Page.md")

        lock.add_page(mock_page)

        assert "123" in lock.pages
        assert lock.pages["123"].title == "Test Page"
        assert lock.pages["123"].version == 5
        assert lock.pages["123"].export_path == "SPACE/Test Page.md"

    def test_add_page_without_version(self) -> None:
        """Test that adding a page without version is skipped."""
        lock = ConfluenceLock()

        mock_page = MagicMock()
        mock_page.id = 123
        mock_page.version = None

        lock.add_page(mock_page)

        assert "123" not in lock.pages

    def test_add_page_updates_existing(self) -> None:
        """Test that adding a page with same ID updates existing entry."""
        lock = ConfluenceLock(
            pages={
                "123": PageEntry(
                    title="Old Title",
                    version=1,
                    export_path="SPACE/Old Title.md",
                )
            }
        )

        mock_page = MagicMock()
        mock_page.id = 123
        mock_page.title = "New Title"
        mock_page.version = MagicMock()
        mock_page.version.number = 2
        mock_page.export_path = Path("SPACE/New Title.md")

        lock.add_page(mock_page)

        assert lock.pages["123"].title == "New Title"
        assert lock.pages["123"].version == 2


class TestLockfileManager:
    """Test cases for LockfileManager class."""

    def setup_method(self) -> None:
        """Reset LockfileManager state before each test."""
        LockfileManager.reset()

    def teardown_method(self) -> None:
        """Reset LockfileManager state after each test."""
        LockfileManager.reset()

    def _mock_settings(self, output_path: Path) -> MagicMock:
        """Create mock settings with given output path."""
        mock_settings = MagicMock()
        mock_settings.export.output_path = output_path
        return mock_settings

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_init_creates_new_lock(self, mock_get_settings: MagicMock) -> None:
        """Test initializing manager creates new lock for non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_get_settings.return_value = self._mock_settings(Path(temp_dir))

            LockfileManager.init()

            assert LockfileManager.is_enabled()

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_init_loads_existing_lock(self, mock_get_settings: MagicMock) -> None:
        """Test initializing manager loads existing lock file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_get_settings.return_value = self._mock_settings(Path(temp_dir))
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME
            lockfile_data = {
                "lockfile_version": 1,
                "last_export": "2024-01-15T10:30:00+00:00",
                "pages": {
                    "123": {
                        "title": "Test Page",
                        "version": 5,
                        "export_path": "SPACE/Test Page.md",
                    }
                },
            }
            lockfile_path.write_text(json.dumps(lockfile_data), encoding="utf-8")

            LockfileManager.init()

            assert LockfileManager.is_enabled()

    def test_is_enabled_false_before_init(self) -> None:
        """Test is_enabled returns False before initialization."""
        assert not LockfileManager.is_enabled()

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_record_page_when_enabled(self, mock_get_settings: MagicMock) -> None:
        """Test recording a page when manager is enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_get_settings.return_value = self._mock_settings(Path(temp_dir))
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME
            LockfileManager.init()

            mock_page = MagicMock()
            mock_page.id = 456
            mock_page.title = "New Page"
            mock_page.version = MagicMock()
            mock_page.version.number = 1
            mock_page.export_path = Path("SPACE/New Page.md")

            LockfileManager.record_page(mock_page)

            # Verify file was saved
            assert lockfile_path.exists()
            saved_data = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert "456" in saved_data["pages"]
            assert saved_data["pages"]["456"]["title"] == "New Page"

    def test_record_page_when_disabled(self) -> None:
        """Test recording a page when manager is disabled does nothing."""
        mock_page = MagicMock()
        mock_page.id = 123

        # Should not raise any error
        LockfileManager.record_page(mock_page)

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_reset_clears_state(self, mock_get_settings: MagicMock) -> None:
        """Test reset clears manager state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_get_settings.return_value = self._mock_settings(Path(temp_dir))
            LockfileManager.init()
            assert LockfileManager.is_enabled()

            LockfileManager.reset()

            assert not LockfileManager.is_enabled()

    @patch("confluence_markdown_exporter.utils.app_data_store.get_settings")
    def test_multiple_record_page_calls(self, mock_get_settings: MagicMock) -> None:
        """Test multiple pages can be recorded sequentially."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_get_settings.return_value = self._mock_settings(Path(temp_dir))
            lockfile_path = Path(temp_dir) / LOCKFILE_FILENAME
            LockfileManager.init()

            for i in range(3):
                mock_page = MagicMock()
                mock_page.id = i + 1
                mock_page.title = f"Page {i + 1}"
                mock_page.version = MagicMock()
                mock_page.version.number = 1
                mock_page.export_path = Path(f"SPACE/Page {i + 1}.md")
                LockfileManager.record_page(mock_page)

            saved_data = json.loads(lockfile_path.read_text(encoding="utf-8"))
            assert len(saved_data["pages"]) == 3
            assert "1" in saved_data["pages"]
            assert "2" in saved_data["pages"]
            assert "3" in saved_data["pages"]


class TestLockfileFilename:
    """Test cases for lockfile constants."""

    def test_lockfile_filename(self) -> None:
        """Test lockfile filename constant."""
        assert LOCKFILE_FILENAME == ".confluence-lock.json"

    def test_lockfile_version(self) -> None:
        """Test lockfile version constant."""
        assert LOCKFILE_VERSION == 1
