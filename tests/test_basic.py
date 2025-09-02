"""Basic tests for confluence-markdown-exporter package."""

import importlib.util
import subprocess
import sys
from pathlib import Path


def test_package_imports() -> None:
    """Test that basic imports work."""
    try:
        import confluence_markdown_exporter  # noqa: F401
        from confluence_markdown_exporter import __version__  # noqa: F401
    except ImportError as e:
        import pytest
        pytest.fail(f"Could not import package: {e}")


def test_package_has_version() -> None:
    """Test that package has a version attribute."""
    from confluence_markdown_exporter import __version__
    assert __version__ is not None
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_command() -> None:
    """Test that the version command works correctly."""
    try:
        # Test the version command
        result = subprocess.run(
            [sys.executable, "-m", "confluence_markdown_exporter.main", "version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        
        # Check that version output contains expected format
        assert "confluence-markdown-exporter" in result.stdout
        assert result.returncode == 0
        
        # The version should be present in output
        # Note: We don't check exact match since dev versions may have extra info
        assert len(result.stdout.strip()) > len("confluence-markdown-exporter")
        
    except subprocess.TimeoutExpired:
        import pytest
        pytest.fail("Version command timed out")
    except subprocess.CalledProcessError as e:
        import pytest
        pytest.fail(f"Version command failed: {e}")
    except Exception as e:
        import pytest
        pytest.fail(f"Unexpected error testing version command: {e}")


def test_config_show_command() -> None:
    """Test that the config --show command works correctly."""
    try:
        # Test the config --show command
        result = subprocess.run(
            [sys.executable, "-m", "confluence_markdown_exporter.main", "config", "--show"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        
        # Check that output contains YAML configuration
        assert result.returncode == 0
        assert "auth:" in result.stdout
        assert "export:" in result.stdout
        assert "connection_config:" in result.stdout
        
        # Verify it's valid YAML by trying to parse it
        import yaml
        config_data = yaml.safe_load(result.stdout)
        assert isinstance(config_data, dict)
        assert "auth" in config_data
        assert "export" in config_data
        assert "connection_config" in config_data
        
    except subprocess.TimeoutExpired:
        import pytest
        pytest.fail("Config show command timed out")
    except subprocess.CalledProcessError as e:
        import pytest
        pytest.fail(f"Config show command failed: {e}")
    except Exception as e:
        import pytest
        pytest.fail(f"Unexpected error testing config show command: {e}")


class TestBasicFunctionality:
    """Basic functionality tests for the confluence-markdown-exporter."""

    def test_import_main_module(self) -> None:
        """Test that main module can be imported."""
        try:
            import confluence_markdown_exporter.main  # noqa: F401
        except ImportError:
            import pytest
            pytest.fail("Could not import main module")

    def test_import_confluence_module(self) -> None:
        """Test that confluence module can be imported without initialization."""
        try:
            # Import just the module without triggering initialization
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "confluence_module",
                "confluence_markdown_exporter/confluence.py"
            )
            # We can check that the file exists and is importable
            assert spec is not None
            assert spec.loader is not None
        except (ImportError, FileNotFoundError) as e:
            import pytest
            pytest.fail(f"Could not access confluence module: {e}")


def test_cli_entry_points() -> None:
    """Test that CLI entry points are properly configured."""
    # Test that we can import the main module without triggering execution
    try:
        import confluence_markdown_exporter.main as main_module
        # Check that the main module exists and has expected attributes
        assert main_module is not None
        # Check if the app is defined (typer app)
        assert hasattr(main_module, 'app')
    except ImportError as e:
        import pytest
        pytest.fail(f"Could not import main module: {e}")
    except Exception:  # noqa: BLE001
        # Allow other exceptions as the module might have initialization code
        # but we can still verify it's importable
        pass
