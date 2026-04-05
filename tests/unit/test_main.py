"""Unit tests for main module."""

import pytest
import typer

from confluence_markdown_exporter.main import app
from confluence_markdown_exporter.main import version


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
        """Test that app has expected top-level commands."""
        commands = [
            callback.callback.__name__.replace("_", "-")
            for callback in app.registered_commands
            if callback.callback is not None
        ]

        expected_commands = ["pages", "pages-with-descendants", "spaces", "orgs", "version"]
        for expected_command in expected_commands:
            assert expected_command in commands

    def test_app_has_config_group(self) -> None:
        """Test that the config sub-app is registered as a command group."""
        group_names = [group.name for group in app.registered_groups]
        assert "config" in group_names
