"""Tests for ENV var override support in AppSettings."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.utils.app_data_store import AppSettings
from confluence_markdown_exporter.utils.app_data_store import ConfigModel
from confluence_markdown_exporter.utils.app_data_store import get_settings


class TestEnvVarOverrides:
    """Verify that CME_ env vars override stored config values without persisting."""

    def test_log_level_env_override(self) -> None:
        """CME_EXPORT__LOG_LEVEL overrides stored log_level."""
        with patch.dict(os.environ, {"CME_EXPORT__LOG_LEVEL": "DEBUG"}):
            settings = get_settings()
        assert settings.export.log_level == "DEBUG"

    def test_output_path_env_override(self) -> None:
        """CME_EXPORT__OUTPUT_PATH overrides stored output_path."""
        with patch.dict(os.environ, {"CME_EXPORT__OUTPUT_PATH": "/some/custom/export"}):
            settings = get_settings()
        assert settings.export.output_path == Path("/some/custom/export")

    def test_max_workers_env_override(self) -> None:
        """CME_CONNECTION_CONFIG__MAX_WORKERS overrides stored max_workers."""
        with patch.dict(os.environ, {"CME_CONNECTION_CONFIG__MAX_WORKERS": "3"}):
            settings = get_settings()
        assert settings.connection_config.max_workers == 3

    def test_verify_ssl_env_override_false(self) -> None:
        """CME_CONNECTION_CONFIG__VERIFY_SSL=false sets verify_ssl to False."""
        with patch.dict(os.environ, {"CME_CONNECTION_CONFIG__VERIFY_SSL": "false"}):
            settings = get_settings()
        assert settings.connection_config.verify_ssl is False

    def test_skip_unchanged_env_override(self) -> None:
        """CME_EXPORT__SKIP_UNCHANGED=false sets skip_unchanged to False."""
        with patch.dict(os.environ, {"CME_EXPORT__SKIP_UNCHANGED": "false"}):
            settings = get_settings()
        assert settings.export.skip_unchanged is False

    def test_attachment_export_all_env_override(self) -> None:
        """CME_EXPORT__ATTACHMENT_EXPORT_ALL=true enables attachment export all."""
        with patch.dict(os.environ, {"CME_EXPORT__ATTACHMENT_EXPORT_ALL": "true"}):
            settings = get_settings()
        assert settings.export.attachment_export_all is True

    def test_env_var_does_not_persist(self) -> None:
        """ENV var override is session-only and does not alter the JSON config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "app_data.json"
            with patch.dict(
                os.environ,
                {
                    "CME_CONFIG_PATH": str(config_path),
                    "CME_EXPORT__LOG_LEVEL": "ERROR",
                },
            ):
                settings = get_settings()
                assert settings.export.log_level == "ERROR"
                # Config file should not exist (no write triggered by get_settings)
                assert not config_path.exists() or (
                    "ERROR" not in config_path.read_text()
                )

    def test_file_config_used_without_env_override(self) -> None:
        """Without ENV var, the stored file config value is returned."""
        import confluence_markdown_exporter.utils.app_data_store as ads

        stored = ConfigModel()
        stored.export.log_level = "WARNING"  # type: ignore[assignment]

        with patch.object(ads, "APP_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = stored.model_dump_json()

            # Ensure no override is set
            env = {k: v for k, v in os.environ.items() if k != "CME_EXPORT__LOG_LEVEL"}
            with patch.dict(os.environ, env, clear=True):
                settings = get_settings()
        assert settings.export.log_level == "WARNING"

    def test_env_override_takes_precedence_over_file(self) -> None:
        """ENV var overrides a value that differs in the stored config file."""
        import confluence_markdown_exporter.utils.app_data_store as ads

        stored = ConfigModel()
        stored.export.log_level = "WARNING"  # type: ignore[assignment]

        with patch.object(ads, "APP_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = stored.model_dump_json()

            with patch.dict(os.environ, {"CME_EXPORT__LOG_LEVEL": "DEBUG"}):
                settings = get_settings()
        assert settings.export.log_level == "DEBUG"

    def test_multiple_env_overrides(self) -> None:
        """Multiple ENV vars can be overridden simultaneously."""
        with patch.dict(
            os.environ,
            {
                "CME_EXPORT__LOG_LEVEL": "ERROR",
                "CME_EXPORT__FILENAME_LENGTH": "100",
                "CME_CONNECTION_CONFIG__TIMEOUT": "60",
                "CME_CONNECTION_CONFIG__USE_V2_API": "true",
            },
        ):
            settings = get_settings()
        assert settings.export.log_level == "ERROR"
        assert settings.export.filename_length == 100
        assert settings.connection_config.timeout == 60
        assert settings.connection_config.use_v2_api is True

    def test_page_href_env_override(self) -> None:
        """CME_EXPORT__PAGE_HREF overrides page_href."""
        with patch.dict(os.environ, {"CME_EXPORT__PAGE_HREF": "absolute"}):
            settings = get_settings()
        assert settings.export.page_href == "absolute"

    def test_attachment_href_env_override(self) -> None:
        """CME_EXPORT__ATTACHMENT_HREF overrides attachment_href."""
        with patch.dict(os.environ, {"CME_EXPORT__ATTACHMENT_HREF": "absolute"}):
            settings = get_settings()
        assert settings.export.attachment_href == "absolute"

    def test_cleanup_stale_env_override(self) -> None:
        """CME_EXPORT__CLEANUP_STALE=false disables cleanup_stale."""
        with patch.dict(os.environ, {"CME_EXPORT__CLEANUP_STALE": "false"}):
            settings = get_settings()
        assert settings.export.cleanup_stale is False

    def test_backoff_and_retry_env_override(self) -> None:
        """CME_CONNECTION_CONFIG__BACKOFF_AND_RETRY=false disables retry."""
        with patch.dict(os.environ, {"CME_CONNECTION_CONFIG__BACKOFF_AND_RETRY": "false"}):
            settings = get_settings()
        assert settings.connection_config.backoff_and_retry is False

    def test_max_backoff_seconds_env_override(self) -> None:
        """CME_CONNECTION_CONFIG__MAX_BACKOFF_SECONDS overrides max_backoff_seconds."""
        with patch.dict(os.environ, {"CME_CONNECTION_CONFIG__MAX_BACKOFF_SECONDS": "120"}):
            settings = get_settings()
        assert settings.connection_config.max_backoff_seconds == 120

    def test_enable_jira_enrichment_env_override(self) -> None:
        """CME_EXPORT__ENABLE_JIRA_ENRICHMENT=false disables Jira enrichment."""
        with patch.dict(os.environ, {"CME_EXPORT__ENABLE_JIRA_ENRICHMENT": "false"}):
            settings = get_settings()
        assert settings.export.enable_jira_enrichment is False

    def test_lockfile_name_env_override(self) -> None:
        """CME_EXPORT__LOCKFILE_NAME overrides lockfile_name."""
        with patch.dict(os.environ, {"CME_EXPORT__LOCKFILE_NAME": "my-lock.json"}):
            settings = get_settings()
        assert settings.export.lockfile_name == "my-lock.json"

    def test_existence_check_batch_size_env_override(self) -> None:
        """CME_EXPORT__EXISTENCE_CHECK_BATCH_SIZE overrides the batch size."""
        with patch.dict(os.environ, {"CME_EXPORT__EXISTENCE_CHECK_BATCH_SIZE": "50"}):
            settings = get_settings()
        assert settings.export.existence_check_batch_size == 50

    def test_app_settings_is_base_settings_subclass(self) -> None:
        """AppSettings is a BaseSettings subclass."""
        from pydantic_settings import BaseSettings

        assert issubclass(AppSettings, BaseSettings)

    def test_invalid_log_level_env_var_raises(self) -> None:
        """An invalid log level value raises a validation error."""
        from pydantic import ValidationError

        with patch.dict(os.environ, {"CME_EXPORT__LOG_LEVEL": "INVALID"}), pytest.raises(
            ValidationError
        ):
            get_settings()
