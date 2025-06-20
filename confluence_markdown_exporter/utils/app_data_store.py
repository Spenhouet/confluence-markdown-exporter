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


class RetryConfig(BaseModel):
    """Configuration for network retry behavior."""

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


class ApiDetails(BaseModel):
    """API authentication details."""

    url: AnyHttpUrl | Literal[""] = Field(
        "", title="Instance URL", description="Base URL of the Confluence or Jira instance."
    )
    username: str = Field(
        "", title="Username (email)", description="Username or email for API authentication."
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


class AuthConfig(BaseModel):
    """Authentication configuration for Confluence and Jira."""

    confluence: ApiDetails = Field(
        default_factory=lambda: ApiDetails(
            url="", username="", api_token=SecretStr(""), pat=SecretStr("")
        ),
        title="Confluence Account",
        description="Authentication for Confluence.",
    )
    jira: ApiDetails = Field(
        default_factory=lambda: ApiDetails(
            url="", username="", api_token=SecretStr(""), pat=SecretStr("")
        ),
        title="Jira Account",
        description="Authentication for Jira.",
    )


class ExportConfig(BaseModel):
    """Export settings for markdown and attachments."""

    markdown_style: Literal["GFM", "Obsidian"] = Field(
        default="GFM",
        title="Markdown Style",
        description=(
            "Markdown style to use for export. Options: GFM or Obsidian.\n"
            "Available styles:\n"
            "  - GFM: GitHub Flavored Markdown\n"
            "  - Obsidian: Markdown style used by Obsidian.md"
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
            "  - {page_title}: The title of the Confluence page."
        ),
        examples=["{space_name}/{page_title}.md"],
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
            "  - {attachment_extension}: The file extension of the attachment, "
            "including the leading dot."
        ),
        examples=["{space_name}/attachments/{attachment_file_id}{attachment_extension}"],
    )


class ConfigModel(BaseModel):
    """Top-level application configuration model."""

    export: ExportConfig = Field(default_factory=ExportConfig, title="Export Settings")
    retry_config: RetryConfig = Field(default_factory=RetryConfig, title="Retry/Network Settings")
    auth: AuthConfig = Field(default_factory=AuthConfig, title="Authentication")


def _convert_paths_to_str(obj: object) -> object:
    """Recursively convert Path, SecretStr, and AnyHttpUrl objects to str."""
    if isinstance(obj, dict):
        return {k: _convert_paths_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_paths_to_str(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, SecretStr):
        return obj.get_secret_value()
    if isinstance(obj, AnyHttpUrl):
        return str(obj)
    return obj


def load_app_data() -> dict[str, dict]:
    """Load application data from the config file, returning a validated dict."""
    data = json.loads(APP_CONFIG_PATH.read_text()) if APP_CONFIG_PATH.exists() else {}
    try:
        return ConfigModel(**data).model_dump()
    except ValidationError:
        return ConfigModel().model_dump()


def save_app_data(data: dict[str, dict]) -> None:
    """Save application data to the config file after conversion and validation."""
    data_obj = _convert_paths_to_str(data)
    if not isinstance(data_obj, dict):
        msg = "Data must be a dict after conversion"
        raise TypeError(msg)
    APP_CONFIG_PATH.write_text(json.dumps(data_obj, indent=2))


def get_settings() -> ConfigModel:
    """Get the current application settings as a ConfigModel instance."""
    data = load_app_data()
    return ConfigModel(
        export=ExportConfig(**data.get("export", {})),
        retry_config=RetryConfig(**data.get("retry_config", {})),
        auth=AuthConfig(**data.get("auth", {})),
    )


def set_by_path(obj: dict, path: str, value: object) -> None:
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
    set_by_path(data, path, value)
    try:
        settings = ConfigModel.model_validate(data)
    except ValidationError as e:
        raise ValueError(str(e)) from e
    save_app_data(settings.model_dump())


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
        save_app_data(ConfigModel().model_dump())
        return
    data = load_app_data()
    default_value = get_default_value_by_path(path)
    set_by_path(data, path, default_value)
    save_app_data(data)
