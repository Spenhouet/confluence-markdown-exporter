"""Unit tests for main module."""

from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import typer

from confluence_markdown_exporter.main import app
from confluence_markdown_exporter.main import config
from confluence_markdown_exporter.main import override_output_path_config
from confluence_markdown_exporter.main import version


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
