"""Handles storage and retrieval of application data (auth and settings) for the exporter."""

import json
import os
from pathlib import Path
from typing import Literal

import typer
from pydantic import AnyHttpUrl
from pydantic import BaseModel
from pydantic import Field
from pydantic import SecretStr
from pydantic import ValidationError

CME_CONFIG_PATH = os.environ.get("CME_CONFIG_PATH")
if CME_CONFIG_PATH:
    APP_CONFIG_PATH = Path(CME_CONFIG_PATH)
else:
    APP_NAME = "confluence-markdown-exporter"
    APP_CONFIG_DIR = Path(typer.get_app_dir(APP_NAME))
    APP_CONFIG_PATH = APP_CONFIG_DIR / "app_data.json"
APP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


class RetryConfig(BaseModel):
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
    export: ExportConfig = Field(
        default_factory=lambda: ExportConfig(
            markdown_style="GFM",
            page_path="{space_name}/{homepage_title}/{ancestor_titles}/{page_title}.md",
            attachment_path="{space_name}/attachments/{attachment_file_id}{attachment_extension}",
        ),
        title="Export Settings",
        description="Settings for export paths, markdown style, and attachments.",
    )
    retry_config: RetryConfig = Field(
        default_factory=lambda: RetryConfig(),
        title="Retry/Network Settings",
        description="Network and retry configuration for API requests.",
        examples=[{"backoff_and_retry": True, "max_backoff_retries": 5}],
    )
    auth: AuthConfig = Field(
        default_factory=lambda: AuthConfig(),
        title="Authentication",
        description="Authentication settings for Confluence and Jira.",
    )


def load_app_data() -> dict:
    if APP_CONFIG_PATH.exists():
        with open(APP_CONFIG_PATH, "r") as f:
            data = json.load(f)
    else:
        data = {}
    # Ensure config is valid
    try:
        data = ConfigModel(**data).model_dump()
    except ValidationError:
        data = ConfigModel().model_dump()
    return data


def _convert_paths_to_str(obj: object) -> object:
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


def save_app_data(data: dict) -> None:
    # Convert all Path objects and SecretStr to str before saving
    data_obj = _convert_paths_to_str(data)
    if not isinstance(data_obj, dict):
        msg = "Data must be a dict after conversion"
        raise TypeError(msg)
    data = data_obj  # type: ignore[assignment]
    with open(APP_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_settings() -> ConfigModel:
    return ConfigModel(**load_app_data())


def set_by_path(obj: dict, path: str, value: object) -> None:
    keys = path.split(".")
    current = obj
    for k in keys[:-1]:
        current = current.setdefault(k, {})
    current[keys[-1]] = value


def set_setting(path: str, value: object) -> None:
    data = load_app_data()
    set_by_path(data, path, value)
    # Validate after setting
    try:
        settings = ConfigModel.model_validate(data)
    except ValidationError as e:
        raise ValueError(str(e)) from e
    save_app_data(settings.model_dump())


def get_auth() -> dict:
    return load_app_data()["auth"]


def set_auth(auth_data: dict) -> None:
    data = load_app_data()
    data["auth"] = auth_data
    save_app_data(data)


def delete_auth() -> None:
    data = load_app_data()
    data["auth"] = AuthConfig().model_dump()
    save_app_data(data)


def reset_settings() -> None:
    save_app_data(ConfigModel().model_dump())
