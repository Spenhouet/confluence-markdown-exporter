"""Unit tests for main module."""

from unittest.mock import patch

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


class TestNonInteractiveAuthFailure:
    """Auth failures must not open the interactive menu in CI or wrappers."""

    @staticmethod
    def _failing_app(service: str) -> typer.Typer:
        from confluence_markdown_exporter.api_clients import AuthNotConfiguredError
        from confluence_markdown_exporter.main import _CmeTyper

        failing = _CmeTyper()

        @failing.command()
        def export() -> None:
            url = "https://example.atlassian.net"
            raise AuthNotConfiguredError(url, service)

        return failing

    @pytest.mark.parametrize(
        ("env", "value"), [("CME_NON_INTERACTIVE", "1"), ("CI", "true")]
    )
    def test_exits_with_error_instead_of_menu(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        env: str,
        value: str,
    ) -> None:
        monkeypatch.setenv(env, value)
        with (
            patch(
                "confluence_markdown_exporter.utils.config_interactive.main_config_menu_loop"
            ) as menu,
            pytest.raises(SystemExit) as exc,
        ):
            self._failing_app("Jira")([], standalone_mode=False)
        assert exc.value.code == 1
        menu.assert_not_called()
        err = capsys.readouterr().err
        assert "Jira credentials for https://example.atlassian.net" in err
        assert "export.enable_jira_enrichment=false" in err

    def test_interactive_terminal_opens_menu(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CME_NON_INTERACTIVE", raising=False)
        monkeypatch.delenv("CI", raising=False)
        with (
            patch("confluence_markdown_exporter.main._is_interactive", return_value=True),
            patch(
                "confluence_markdown_exporter.utils.config_interactive.main_config_menu_loop"
            ) as menu,
            pytest.raises(SystemExit),
        ):
            self._failing_app("Confluence")([], standalone_mode=False)
        menu.assert_called_once_with(
            "auth.confluence", new_instance_url="https://example.atlassian.net"
        )
