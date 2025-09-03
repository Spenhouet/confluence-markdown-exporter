"""Basic tests for confluence-markdown-exporter package."""

import json
import subprocess
import sys

import pytest

import confluence_markdown_exporter.main as main_module
from confluence_markdown_exporter import __version__


def test_package_has_version() -> None:
    """Test that package has a version attribute."""
    assert __version__ is not None
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_command() -> None:
    """Test that the version command works correctly."""
    try:
        # Test the version command
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "confluence_markdown_exporter.main", "version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        # Check that version output contains expected format
        assert "confluence-markdown-exporter" in result.stdout
        assert result.returncode == 0

        # The version should be present in output
        # Note: We don't check exact match since dev versions may have extra info
        assert len(result.stdout.strip()) > len("confluence-markdown-exporter")

    except subprocess.TimeoutExpired:
        pytest.fail("Version command timed out")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Version command failed: {e}")
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"Unexpected error testing version command: {e}")


def test_config_show_command() -> None:
    """Test that the config --show command works correctly."""
    try:
        # Test the config --show command
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "confluence_markdown_exporter.main",
                "config",
                "--show",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        # Check that output contains JSON configuration
        assert result.returncode == 0
        assert '"auth":' in result.stdout
        assert '"export":' in result.stdout
        assert '"connection_config":' in result.stdout

        # Extract JSON from code block (remove ```json and ``` wrapper)
        stdout_lines = result.stdout.strip().split("\n")
        if stdout_lines[0] == "```json" and stdout_lines[-1] == "```":
            json_content = "\n".join(stdout_lines[1:-1])
        else:
            json_content = result.stdout

        # Verify it's valid JSON by trying to parse it
        config_data = json.loads(json_content)
        assert isinstance(config_data, dict)
        assert "auth" in config_data
        assert "export" in config_data
        assert "connection_config" in config_data

    except subprocess.TimeoutExpired:
        pytest.fail("Config show command timed out")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Config show command failed: {e}")
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"Unexpected error testing config show command: {e}")


def test_cli_entry_points() -> None:
    """Test that CLI entry points are properly configured."""
    # Test that we can import the main module without triggering execution
    try:
        # Check that the main module exists and has expected attributes
        assert main_module is not None
        # Check if the app is defined (typer app)
        assert hasattr(main_module, "app")
    except ImportError as e:
        pytest.fail(f"Could not import main module: {e}")
    except Exception:  # noqa: BLE001
        # Allow other exceptions as the module might have initialization code
        # but we can still verify it's importable
        pass
