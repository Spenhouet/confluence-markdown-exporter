"""Handles storage and retrieval of application data (auth and settings) for the exporter."""

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl
from pydantic import BaseModel
from pydantic import Field
from pydantic import SecretStr
from pydantic import ValidationError
from pydantic import field_serializer
from typer import get_app_dir


def get_app_config_path() -> Path:
    """Determine the path to the app config file, creating parent directories if needed."""
    config_env = os.environ.get("CME_CONFIG_PATH")
    if config_env:
        path = Path(config_env)
    else:
        app_name = "confluence-markdown-exporter"
        config_dir = Path(get_app_dir(app_name))
        path = config_dir / "app_data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


APP_CONFIG_PATH = get_app_config_path()


class ConnectionConfig(BaseModel):
    """Configuration for the connection like retry options."""

    backoff_and_retry: bool = Field(
        default=True,
        title="Enable Retry",
        description="Enable or disable automatic retry with exponential backoff on network errors.",
    )
    backoff_factor: int = Field(
        default=2,
        title="Backoff Factor",
        description=(
            "Multiplier for exponential backoff between retries. "
            "For example, 2 means each retry waits twice as long as the previous."
        ),
    )
    max_backoff_seconds: int = Field(
        default=60,
        title="Max Backoff Seconds",
        description="Maximum number of seconds to wait between retries.",
    )
    max_backoff_retries: int = Field(
        default=5,
        title="Max Retries",
        description="Maximum number of retry attempts before giving up.",
    )
    retry_status_codes: list[int] = Field(
        default_factory=lambda: [413, 429, 502, 503, 504],
        title="Retry Status Codes",
        description="HTTP status codes that should trigger a retry.",
    )
    verify_ssl: bool = Field(
        default=True,
        title="Verify SSL",
        description=(
            "Whether to verify SSL certificates for HTTPS requests. "
            "Set to False only if you are sure about the security of your connection."
        ),
    )


class ApiDetails(BaseModel):
    """API authentication details."""

    url: AnyHttpUrl | Literal[""] = Field(
        "",
        title="Instance URL",
        description="Base URL of the Confluence or Jira instance.",
    )
    username: SecretStr = Field(
        SecretStr(""),
        title="Username (email)",
        description="Username or email for API authentication.",
    )
    api_token: SecretStr = Field(
        SecretStr(""),
        title="API Token",
        description=(
            "API token for authentication (if required). "
            "Create an Atlassian API token at "
            "https://id.atlassian.com/manage-profile/security/api-tokens. "
            "See Atlassian documentation for details."
        ),
    )
    pat: SecretStr = Field(
        SecretStr(""),
        title="Personal Access Token (PAT)",
        description=(
            "Personal Access Token for authentication. "
            "Set this if you use a PAT instead of username+API token. "
            "See your Atlassian instance documentation for how to create a PAT."
        ),
    )

    @field_serializer("username", "api_token", "pat", when_used="json")
    def dump_secret(self, v: SecretStr) -> str:
        return v.get_secret_value()


class AuthConfig(BaseModel):
    """Authentication configuration for Confluence and Jira."""

    confluence: ApiDetails = Field(
        default_factory=lambda: ApiDetails(
            url="", username=SecretStr(""), api_token=SecretStr(""), pat=SecretStr("")
        ),
        title="Confluence Account",
        description="Authentication for Confluence.",
    )
    jira: ApiDetails = Field(
        default_factory=lambda: ApiDetails(
            url="", username=SecretStr(""), api_token=SecretStr(""), pat=SecretStr("")
        ),
        title="Jira Account",
        description="Authentication for Jira.",
    )


class ExportConfig(BaseModel):
    """Export settings for markdown and attachments."""

    output_path: Path = Field(
        default=Path(),
        title="Output Path",
        description=("Directory where exported pages and attachments will be saved."),
        examples=[
            "`.`: Output will be saved relative to the current working directory.",
            (
                "`./confluence_export`: Output will be saved in a folder `confluence_export` "
                "relative to the current working directory."
            ),
            "`/path/to/export`: Output will be saved in the specified absolute path.",
        ],
    )
    page_href: Literal["absolute", "relative"] = Field(
        default="relative",
        title="Page Href Style",
        description=(
            "How to generate page href paths. Options: absolute, relative.\n"
            "  - `relative` links are relative to the page"
            "  - `absolute` links start from the configured output path"
        ),
    )
    page_path: str = Field(
        default="{space_name}/{homepage_title}/{ancestor_titles}/{page_title}.md",
        title="Page Path Template",
        description=(
            "Template for exported page file paths.\n"
            "Available variables:\n"
            "  - {space_key}: The key of the Confluence space.\n"
            "  - {space_name}: The name of the Confluence space.\n"
            "  - {homepage_id}: The ID of the homepage of the Confluence space.\n"
            "  - {homepage_title}: The title of the homepage of the Confluence space.\n"
            "  - {ancestor_ids}: A slash-separated list of ancestor page IDs.\n"
            "  - {ancestor_titles}: A slash-separated list of ancestor page titles.\n"
            "  - {page_id}: The unique ID of the Confluence page.\n"
            "  - {page_title}: The title of the Confluence page.\n"
        ),
        examples=["{space_name}/{page_title}.md"],
    )
    attachment_href: Literal["absolute", "relative"] = Field(
        default="relative",
        title="Attachment Href Style",
        description=(
            "How to generate attachment href paths. Options: absolute, relative.\n"
            "  - `relative` links are relative to the page"
            "  - `absolute` links start from the configured output path"
        ),
    )
    attachment_path: str = Field(
        default="{space_name}/attachments/{attachment_file_id}{attachment_extension}",
        title="Attachment Path Template",
        description=(
            "Template for exported attachment file paths.\n"
            "Available variables:\n"
            "  - {space_key}: The key of the Confluence space.\n"
            "  - {space_name}: The name of the Confluence space.\n"
            "  - {homepage_id}: The ID of the homepage of the Confluence space.\n"
            "  - {homepage_title}: The title of the homepage of the Confluence space.\n"
            "  - {ancestor_ids}: A slash-separated list of ancestor page IDs.\n"
            "  - {ancestor_titles}: A slash-separated list of ancestor page titles.\n"
            "  - {attachment_id}: The unique ID of the attachment.\n"
            "  - {attachment_title}: The title of the attachment.\n"
            "  - {attachment_file_id}: The file ID of the attachment.\n"
            "  - {attachment_extension}: The file extension of the attachment,\n"
            "including the leading dot."
        ),
        examples=["{space_name}/attachments/{attachment_file_id}{attachment_extension}"],
    )
    attachment_export_all: bool = Field(
        default=False,
        title="Attachment Export All",
        description=(
            "Whether to export all attachments or only the ones whose ID "
            "is referred in the page."
            "\nNote: large and multiple attachments will take more time"
        ),
    )
    page_breadcrumbs: bool = Field(
        default=True,
        title="Page Breadcrumbs",
        description="Whether to include breadcrumb links at the top of the page.",
    )
    filename_encoding: str = Field(
        default='"<":"_",">":"_",":":"_","\\"":"_","/":"_","\\\\":"_","|":"_","?":"_","*":"_","\\u0000":"_","[":"_","]":"_"',
        title="Filename Encoding",
        description=(
            "List character-to-replacement pairs, separated by commas. "
            'Each pair is written as "character":"replacement". '
            "Leave empty to disable all character replacements."
        ),
        examples=[
            '" ":"-","-":"%2D"',  # Replace spaces with dash and dashes with %2D
            '"=":" equals "',  # Replace equals sign with " equals "
        ],
    )
    filename_length: int = Field(
        default=255,
        title="Filename Length",
        description="Maximum length of the filename.",
    )
    include_document_title: bool = Field(
        default=True,
        title="Include Document Title",
        description=(
            "Whether to include the document title in the exported markdown file. "
            "If enabled, the title will be added as a top-level heading."
        ),
    )


class ConfigModel(BaseModel):
    """Top-level application configuration model."""

    export: ExportConfig = Field(default_factory=ExportConfig, title="Export Settings")
    connection_config: ConnectionConfig = Field(
        default_factory=ConnectionConfig, title="Connection Configuration"
    )
    auth: AuthConfig = Field(default_factory=AuthConfig, title="Authentication")


def load_app_data() -> dict[str, dict]:
    """Load application data from the config file, returning a validated dict."""
    data = json.loads(APP_CONFIG_PATH.read_text()) if APP_CONFIG_PATH.exists() else {}
    try:
        return ConfigModel(**data).model_dump()
    except ValidationError:
        return ConfigModel().model_dump()


def save_app_data(config_model: ConfigModel) -> None:
    """Save application data to the config file using Pydantic serialization."""
    # Use Pydantic's model_dump_json which properly handles SecretStr serialization
    json_str = config_model.model_dump_json(indent=2)
    APP_CONFIG_PATH.write_text(json_str)


def get_settings() -> ConfigModel:
    """Get the current application settings as a ConfigModel instance."""
    data = load_app_data()
    return ConfigModel(
        export=ExportConfig(**data.get("export", {})),
        connection_config=ConnectionConfig(**data.get("connection_config", {})),
        auth=AuthConfig(**data.get("auth", {})),
    )


def _set_by_path(obj: dict, path: str, value: object) -> None:
    """Set a value in a nested dict using dot notation path."""
    keys = path.split(".")
    current = obj
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


def set_setting(path: str, value: object) -> None:
    """Set a setting by dot-path and save to config file."""
    data = load_app_data()
    _set_by_path(data, path, value)
    try:
        settings = ConfigModel.model_validate(data)
    except ValidationError as e:
        raise ValueError(str(e)) from e
    save_app_data(settings)


def get_default_value_by_path(path: str | None = None) -> object:
    """Get the default value for a given config path, or the whole config if path is None."""
    model = ConfigModel()
    if not path:
        return model.model_dump()
    keys = path.split(".")
    current = model
    for k in keys:
        if hasattr(current, k):
            current = getattr(current, k)
        elif isinstance(current, dict) and k in current:
            current = current[k]
        else:
            msg = f"Invalid config path: {path}"
            raise KeyError(msg)
    if isinstance(current, BaseModel):
        return current.model_dump()
    return current


def reset_to_defaults(path: str | None = None) -> None:
    """Reset the whole config, a section, or a single option to its default value.

    If path is None, reset the entire config. Otherwise, reset the specified path.
    """
    if path is None:
        save_app_data(ConfigModel())
        return
    data = load_app_data()
    default_value = get_default_value_by_path(path)
    _set_by_path(data, path, default_value)
    settings = ConfigModel.model_validate(data)
    save_app_data(settings)
