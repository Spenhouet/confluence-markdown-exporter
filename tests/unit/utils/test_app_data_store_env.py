"""Tests for ENV var override support in AppSettings."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.utils.app_data_store import AppSettings
from confluence_markdown_exporter.utils.app_data_store import ConfigModel
from confluence_markdown_exporter.utils.app_data_store import ExportConfig
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import load_app_data


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

    def test_attachments_export_env_override(self) -> None:
        """CME_EXPORT__ATTACHMENTS_EXPORT overrides attachments_export."""
        with patch.dict(os.environ, {"CME_EXPORT__ATTACHMENTS_EXPORT": "all"}):
            settings = get_settings()
        assert settings.export.attachments_export == "all"

    def test_confluence_url_in_frontmatter_env_override(self) -> None:
        """CME_EXPORT__CONFLUENCE_URL_IN_FRONTMATTER overrides confluence_url_in_frontmatter."""
        with patch.dict(os.environ, {"CME_EXPORT__CONFLUENCE_URL_IN_FRONTMATTER": "both"}):
            settings = get_settings()
        assert settings.export.confluence_url_in_frontmatter == "both"

    def test_page_metadata_in_frontmatter_env_override(self) -> None:
        """CME_EXPORT__PAGE_METADATA_IN_FRONTMATTER=true sets page_metadata_in_frontmatter."""
        with patch.dict(os.environ, {"CME_EXPORT__PAGE_METADATA_IN_FRONTMATTER": "true"}):
            settings = get_settings()
        assert settings.export.page_metadata_in_frontmatter is True

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


class TestLoadAppData:
    """Tests for load_app_data robustness."""

    def test_empty_config_file_returns_defaults(self) -> None:
        """Empty config file must not raise JSONDecodeError."""
        import confluence_markdown_exporter.utils.app_data_store as ads

        with patch.object(ads, "APP_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = ""
            result = load_app_data()
        assert isinstance(result, dict)

    def test_invalid_json_config_file_returns_defaults(self) -> None:
        """Corrupt config file must not raise JSONDecodeError."""
        import confluence_markdown_exporter.utils.app_data_store as ads

        with patch.object(ads, "APP_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = "not json {"
            result = load_app_data()
        assert isinstance(result, dict)


class TestAttachmentPathMigration:
    """Test migration of attachment_path templates that omit {attachment_extension}."""

    def test_title_without_extension_gets_migrated(self) -> None:
        """{attachment_title} alone is migrated to include {attachment_extension}."""
        config = ExportConfig(attachment_path="{space_name}/{attachment_title}")
        assert config.attachment_path == "{space_name}/{attachment_title}{attachment_extension}"

    def test_title_with_other_path_segments_migrated(self) -> None:
        """Migration works regardless of surrounding path segments."""
        config = ExportConfig(attachment_path="{page_title}/{attachment_title}")
        assert config.attachment_path == "{page_title}/{attachment_title}{attachment_extension}"

    def test_title_already_has_extension_not_changed(self) -> None:
        """Template already containing {attachment_extension} is left unchanged."""
        original = "{space_name}/{attachment_title}{attachment_extension}"
        config = ExportConfig(attachment_path=original)
        assert config.attachment_path == original

    def test_no_attachment_title_not_changed(self) -> None:
        """Default template without {attachment_title} is left unchanged."""
        original = "{space_name}/attachments/{attachment_file_id}{attachment_extension}"
        config = ExportConfig(attachment_path=original)
        assert config.attachment_path == original

    def test_migration_via_env_var(self) -> None:
        """Migration also applies when the template comes from an ENV var."""
        with patch.dict(
            os.environ,
            {"CME_EXPORT__ATTACHMENT_PATH": "{space_name}/attachments/{attachment_title}"},
        ):
            settings = get_settings()
        assert settings.export.attachment_path == (
            "{space_name}/attachments/{attachment_title}{attachment_extension}"
        )


class TestAttachmentsExportMigration:
    """Migration of legacy attachment_export_all bool to attachments_export literal."""

    def test_legacy_false_maps_to_referenced(self) -> None:
        """attachment_export_all=False migrates to attachments_export='referenced'."""
        config = ExportConfig.model_validate({"attachment_export_all": False})
        assert config.attachments_export == "referenced"

    def test_legacy_true_maps_to_all(self) -> None:
        """attachment_export_all=True migrates to attachments_export='all'."""
        config = ExportConfig.model_validate({"attachment_export_all": True})
        assert config.attachments_export == "all"

    def test_new_field_takes_precedence_over_old(self) -> None:
        """When both are present, the explicit new value wins and old is dropped."""
        config = ExportConfig.model_validate(
            {"attachment_export_all": True, "attachments_export": "disabled"}
        )
        assert config.attachments_export == "disabled"
