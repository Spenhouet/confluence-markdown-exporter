"""Unit tests for main module."""

from datetime import datetime
from datetime import timezone
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import typer

from confluence_markdown_exporter.main import app
from confluence_markdown_exporter.main import check_state_file_guard
from confluence_markdown_exporter.main import config
from confluence_markdown_exporter.main import override_output_path_config
from confluence_markdown_exporter.main import status
from confluence_markdown_exporter.main import sync
from confluence_markdown_exporter.main import version
from confluence_markdown_exporter.state import STATE_FILENAME
from confluence_markdown_exporter.state import ExportState
from confluence_markdown_exporter.state import PageState
from confluence_markdown_exporter.state import ScopeEntry
from confluence_markdown_exporter.state import SyncDelta


class TestOverrideOutputPathConfig:
    """Test cases for override_output_path_config function."""

    @patch("confluence_markdown_exporter.main.set_setting")
    def test_with_path_value(self, mock_set_setting: MagicMock) -> None:
        """Test setting output path when value is provided."""
        test_path = Path("/test/output")
        override_output_path_config(test_path)

        mock_set_setting.assert_called_once_with("export.output_path", test_path)

    @patch("confluence_markdown_exporter.main.set_setting")
    def test_with_none_value(self, mock_set_setting: MagicMock) -> None:
        """Test that None value doesn't call set_setting."""
        override_output_path_config(None)

        mock_set_setting.assert_not_called()


class TestVersionCommand:
    """Test cases for version command."""

    def test_version_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that version command outputs correct format."""
        version()

        captured = capsys.readouterr()
        assert "confluence-markdown-exporter" in captured.out
        # Should contain version information
        assert len(captured.out.strip()) > len("confluence-markdown-exporter")


class TestAppConfiguration:
    """Test cases for the Typer app configuration."""

    def test_app_is_typer_instance(self) -> None:
        """Test that app is a Typer instance."""
        assert isinstance(app, typer.Typer)

    def test_app_has_commands(self) -> None:
        """Test that app has expected commands."""
        # Get all registered commands from typer app
        commands = [
            callback.callback.__name__.replace("_", "-")
            for callback in app.registered_commands
            if callback.callback is not None
        ]

        expected_commands = [
            "pages",
            "pages-with-descendants",
            "spaces",
            "all-spaces",
            "sync",
            "status",
            "config",
            "version",
        ]
        for expected_command in expected_commands:
            assert expected_command in commands

    # Note: The following command tests are more like integration tests
    # since they require complex mocking of the entire confluence module
    # and its dependencies. For full test coverage, these should be
    # implemented as integration tests with proper test fixtures.

    @patch("confluence_markdown_exporter.main.get_settings")
    def test_config_show_command(
        self,
        mock_get_settings: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test config command with show option."""
        mock_settings = MagicMock()
        mock_settings.model_dump_json.return_value = '{\n  "test": "config"\n}'
        mock_get_settings.return_value = mock_settings

        config(None, show=True)

        captured = capsys.readouterr()
        assert "```json" in captured.out
        assert '"test": "config"' in captured.out
        assert "```" in captured.out
        mock_settings.model_dump_json.assert_called_once_with(indent=2)

    @patch("confluence_markdown_exporter.main.main_config_menu_loop")
    def test_config_interactive_command(self, mock_menu_loop: MagicMock) -> None:
        """Test config command in interactive mode."""
        config(None, show=False)

        mock_menu_loop.assert_called_once_with(None)

    @patch("confluence_markdown_exporter.main.main_config_menu_loop")
    def test_config_jump_to_option(self, mock_menu_loop: MagicMock) -> None:
        """Test config command with jump_to option."""
        config("auth.confluence", show=False)

        mock_menu_loop.assert_called_once_with("auth.confluence")


class TestCheckStateFileGuard:
    """Test cases for state file guard behavior in export commands."""

    def test_state_file_exists_without_append_raises_system_exit(
        self, tmp_path: Path
    ) -> None:
        """When .cme-state.json exists and --append is False, raise SystemExit."""
        state = ExportState(
            confluence_url="https://example.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        with pytest.raises(SystemExit):
            check_state_file_guard(
                output_path=tmp_path,
                append=False,
                command="pages",
                args=["456"],
                confluence_url="https://example.atlassian.net/",
            )

    def test_state_file_exists_without_append_prints_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When state file exists and --append is False, print recommendation to use sync."""
        state = ExportState(
            confluence_url="https://example.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        with pytest.raises(SystemExit):
            check_state_file_guard(
                output_path=tmp_path,
                append=False,
                command="pages",
                args=["456"],
                confluence_url="https://example.atlassian.net/",
            )

        captured = capsys.readouterr()
        assert "sync" in captured.err.lower() or "sync" in captured.out.lower()

    def test_state_file_exists_with_append_returns_state(
        self, tmp_path: Path
    ) -> None:
        """When state file exists and --append is True, load and return state."""
        state = ExportState(
            confluence_url="https://example.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        result = check_state_file_guard(
            output_path=tmp_path,
            append=True,
            command="spaces",
            args=["DEV"],
            confluence_url="https://example.atlassian.net/",
        )

        assert result is not None
        assert len(result.scopes) == 2
        assert result.scopes[0] == ScopeEntry(command="pages", args=["123"])
        assert result.scopes[1] == ScopeEntry(command="spaces", args=["DEV"])

    def test_append_with_duplicate_scope_does_not_add(
        self, tmp_path: Path
    ) -> None:
        """When --append and scope already exists, do not duplicate it."""
        state = ExportState(
            confluence_url="https://example.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        result = check_state_file_guard(
            output_path=tmp_path,
            append=True,
            command="pages",
            args=["123"],
            confluence_url="https://example.atlassian.net/",
        )

        assert result is not None
        assert len(result.scopes) == 1

    def test_no_state_file_creates_new_state(
        self, tmp_path: Path
    ) -> None:
        """When no state file exists, create new ExportState with scope."""
        result = check_state_file_guard(
            output_path=tmp_path,
            append=False,
            command="pages",
            args=["123", "456"],
            confluence_url="https://example.atlassian.net/",
        )

        assert result is not None
        assert result.confluence_url == "https://example.atlassian.net/"
        assert len(result.scopes) == 1
        assert result.scopes[0].command == "pages"
        assert result.scopes[0].args == ["123", "456"]
        assert result.pages == {}

    def test_new_state_contains_correct_confluence_url(
        self, tmp_path: Path
    ) -> None:
        """State file should contain the correct confluence_url from settings."""
        result = check_state_file_guard(
            output_path=tmp_path,
            append=False,
            command="spaces",
            args=["TEAM"],
            confluence_url="https://mycompany.atlassian.net/",
        )

        assert result is not None
        assert result.confluence_url == "https://mycompany.atlassian.net/"

    def test_append_validates_confluence_url_mismatch(
        self, tmp_path: Path
    ) -> None:
        """When appending, mismatched confluence URL should raise ValueError."""
        state = ExportState(
            confluence_url="https://old.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        with pytest.raises(ValueError, match="mismatch"):
            check_state_file_guard(
                output_path=tmp_path,
                append=True,
                command="pages",
                args=["456"],
                confluence_url="https://new.atlassian.net/",
            )


class TestSyncCommand:
    """Test cases for the sync CLI command."""

    def test_sync_no_state_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Sync with no state file exits with error message."""
        with pytest.raises(SystemExit):
            sync(output_path=tmp_path, force=False, dry_run=False)

        captured = capsys.readouterr()
        assert "no" in captured.err.lower() or "state" in captured.err.lower()

    @patch("confluence_markdown_exporter.main.get_settings")
    def test_sync_url_mismatch(
        self,
        mock_get_settings: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Sync with mismatched confluence_url exits with error."""
        # Create state with one URL
        state = ExportState(
            confluence_url="https://old.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        # Configure settings to return a different URL
        mock_settings = MagicMock()
        mock_settings.auth.confluence.url = "https://new.atlassian.net/"
        mock_settings.export.output_path = tmp_path
        mock_get_settings.return_value = mock_settings

        with pytest.raises((SystemExit, ValueError)):
            sync(output_path=tmp_path, force=False, dry_run=False)

    @patch("confluence_markdown_exporter.sync.execute_sync")
    @patch("confluence_markdown_exporter.sync.format_sync_report")
    @patch("confluence_markdown_exporter.main.compute_delta")
    @patch("confluence_markdown_exporter.sync.replay_scopes")
    @patch("confluence_markdown_exporter.main.get_settings")
    def test_sync_dry_run(
        self,
        mock_get_settings: MagicMock,
        mock_replay: MagicMock,
        mock_delta: MagicMock,
        mock_report: MagicMock,
        mock_execute: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Sync --dry-run prints report without modifying files."""
        # Set up state file
        state = ExportState(
            confluence_url="https://example.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        # Configure mocks
        mock_settings = MagicMock()
        mock_settings.auth.confluence.url = "https://example.atlassian.net/"
        mock_settings.export.output_path = tmp_path
        mock_get_settings.return_value = mock_settings

        mock_replay.return_value = {"123": 2}
        mock_delta.return_value = SyncDelta(modified=["123"])
        mock_report.return_value = "  mod:  page.md\n0 new, 1 modified, 0 deleted, 0 unchanged"

        sync(output_path=tmp_path, force=False, dry_run=True)

        # Report should be printed
        captured = capsys.readouterr()
        assert "mod:" in captured.out

        # execute_sync should NOT be called in dry-run mode
        mock_execute.assert_not_called()

    @patch("confluence_markdown_exporter.sync.execute_sync")
    @patch("confluence_markdown_exporter.sync.format_sync_report")
    @patch("confluence_markdown_exporter.main.compute_delta")
    @patch("confluence_markdown_exporter.sync.replay_scopes")
    @patch("confluence_markdown_exporter.main.get_settings")
    def test_sync_force(
        self,
        mock_get_settings: MagicMock,
        mock_replay: MagicMock,
        mock_delta: MagicMock,
        mock_report: MagicMock,
        mock_execute: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Sync --force sets min_export_timestamp before running."""
        # Set up state file
        state = ExportState(
            confluence_url="https://example.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        # Configure mocks
        mock_settings = MagicMock()
        mock_settings.auth.confluence.url = "https://example.atlassian.net/"
        mock_settings.export.output_path = tmp_path
        mock_get_settings.return_value = mock_settings

        mock_replay.return_value = {"123": 1}
        mock_delta.return_value = SyncDelta(stale=["123"])
        mock_report.return_value = "  stale:  page.md\n0 new, 0 modified, 0 deleted, 0 unchanged"

        before = datetime.now(tz=timezone.utc)
        sync(output_path=tmp_path, force=True, dry_run=False)

        # compute_delta should have been called with a state that has min_export_timestamp set
        call_args = mock_delta.call_args
        state_arg = call_args[0][0]
        assert state_arg.min_export_timestamp is not None
        assert state_arg.min_export_timestamp >= before

    @patch("confluence_markdown_exporter.main.save_state")
    @patch("confluence_markdown_exporter.sync.execute_sync")
    @patch("confluence_markdown_exporter.sync.format_sync_report")
    @patch("confluence_markdown_exporter.main.compute_delta")
    @patch("confluence_markdown_exporter.sync.replay_scopes")
    @patch("confluence_markdown_exporter.main.get_settings")
    def test_sync_url_mismatch_without_force_raises(
        self,
        mock_get_settings: MagicMock,
        mock_replay: MagicMock,
        mock_delta: MagicMock,
        mock_report: MagicMock,
        mock_execute: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Sync without --force raises ValueError on URL mismatch."""
        state = ExportState(
            confluence_url="https://old.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        mock_settings = MagicMock()
        mock_settings.auth.confluence.url = "https://new.atlassian.net/"
        mock_settings.export.output_path = tmp_path
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="--force"):
            sync(output_path=tmp_path, force=False, dry_run=False)

    @patch("confluence_markdown_exporter.main.save_state")
    @patch("confluence_markdown_exporter.sync.execute_sync")
    @patch("confluence_markdown_exporter.sync.format_sync_report")
    @patch("confluence_markdown_exporter.main.compute_delta")
    @patch("confluence_markdown_exporter.sync.replay_scopes")
    @patch("confluence_markdown_exporter.main.get_settings")
    def test_sync_force_updates_mismatched_url(
        self,
        mock_get_settings: MagicMock,
        mock_replay: MagicMock,
        mock_delta: MagicMock,
        mock_report: MagicMock,
        mock_execute: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Sync --force updates the stored URL when it differs from config."""
        state = ExportState(
            confluence_url="https://old.atlassian.net/",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        mock_settings = MagicMock()
        mock_settings.auth.confluence.url = "https://new.atlassian.net/"
        mock_settings.export.output_path = tmp_path
        mock_get_settings.return_value = mock_settings

        mock_replay.return_value = {"123": 1}
        mock_delta.return_value = SyncDelta(stale=["123"])
        mock_report.return_value = "report"

        sync(output_path=tmp_path, force=True, dry_run=False)

        # The state saved should have the new URL
        saved_state = mock_save.call_args[0][1]
        assert saved_state.confluence_url == "https://new.atlassian.net/"


class TestStatusCommand:
    """Test cases for the status CLI command."""

    def test_status_no_state_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Status with no state file prints 'No previous export found'."""
        status(output_path=tmp_path)

        captured = capsys.readouterr()
        assert "no previous export" in captured.out.lower() or "no state" in captured.out.lower()

    def test_status_shows_scopes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Status with valid state prints scopes and page count."""
        state = ExportState(
            confluence_url="https://example.atlassian.net/",
            scopes=[
                ScopeEntry(command="pages", args=["123", "456"]),
                ScopeEntry(command="spaces", args=["DEV"]),
            ],
            pages={
                "123": PageState(
                    version=3,
                    last_exported=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    output_path="page1.md",
                    status="active",
                ),
                "456": PageState(
                    version=1,
                    last_exported=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    output_path="page2.md",
                    status="active",
                ),
                "789": PageState(
                    version=2,
                    last_exported=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    output_path="page3.md",
                    status="deleted",
                ),
            },
        )
        state_file = tmp_path / STATE_FILENAME
        state_file.write_text(state.model_dump_json(indent=2))

        status(output_path=tmp_path)

        captured = capsys.readouterr()
        output = captured.out.lower()
        # Should display scope information
        assert "pages" in output
        assert "spaces" in output
        # Should display page counts
        assert "2" in captured.out  # 2 active pages
        assert "1" in captured.out  # 1 deleted page
