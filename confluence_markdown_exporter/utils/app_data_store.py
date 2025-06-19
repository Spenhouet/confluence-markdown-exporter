"""Handles storage and retrieval of application data (auth and settings) for the exporter."""

import json
from pathlib import Path
from typing import Literal

import typer
from pydantic import AnyHttpUrl
from pydantic import BaseModel
from pydantic import Field
from pydantic import SecretStr
from pydantic import ValidationError

APP_NAME = "confluence-markdown-exporter"
APP_CONFIG_DIR = Path(typer.get_app_dir(APP_NAME))
APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = APP_CONFIG_DIR / "app_data.json"


class RetryConfig(BaseModel):
    backoff_and_retry: bool = Field(
        True,
        title="Enable Retry",
        description="Enable or disable automatic retry with exponential backoff on network errors.",
    )
    backoff_factor: int = Field(
        2,
        title="Backoff Factor",
        description=(
            "Multiplier for exponential backoff between retries. "
            "For example, 2 means each retry waits twice as long as the previous."
        ),
    )
    max_backoff_seconds: int = Field(
        60,
        title="Max Backoff Seconds",
        description="Maximum number of seconds to wait between retries.",
    )
    max_backoff_retries: int = Field(
        5,
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
        SecretStr(""), title="API Token", description="API token for authentication (if required)."
    )
    pat: SecretStr = Field(
        SecretStr(""),
        title="Personal Access Token (PAT)",
        description="Personal Access Token (if required).",
    )


class AuthConfig(BaseModel):
    confluence: ApiDetails = Field(
        default_factory=ApiDetails,
        title="Confluence Account",
        description="Authentication for Confluence.",
    )
    jira: ApiDetails = Field(
        default_factory=ApiDetails,
        title="Jira Account",
        description="Authentication for Jira.",
    )


class ConfigModel(BaseModel):
    output_directory: Path = Field(
        Path.home() / "confluence_exports",
        title="Output Directory",
        description="Directory where exported markdown and attachments will be saved.",
        examples=["/home/user/confluence_exports", "./exports"],
    )
    markdown_style: Literal["GFM", "Obsidian"] = Field(
        "GFM",
        title="Markdown Style",
        description=(
            "Markdown style to use for export. Options: GFM or Obsidian.\n"
            "Available styles:\n"
            "  - GFM: GitHub Flavored Markdown\n"
            "  - Obsidian: Markdown style used by Obsidian.md"
        ),
    )
    page_path: str = Field(
        "{space_name}/{homepage_title}/{ancestor_titles}/{page_title}.md",
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
        "{space_name}/attachments/{attachment_file_id}{attachment_extension}",
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
            "  - {attachment_extension}: The file extension of the attachment, including the leading dot."  # noqa: E501
        ),
        examples=["{space_name}/attachments/{attachment_file_id}{attachment_extension}"],
    )
    include_attachments: bool = Field(
        True,
        title="Include Attachments",
        description="Whether to download and include attachments in the export.",
        examples=[True, False],
    )
    retry_config: RetryConfig = Field(
        default_factory=RetryConfig,
        title="Retry/Network Settings",
        description="Network and retry configuration for API requests.",
        examples=[{"backoff_and_retry": True, "max_backoff_retries": 5}],
    )
    auth: AuthConfig = Field(
        default_factory=AuthConfig,
        title="Authentication",
        description="Authentication settings for Confluence and Jira.",
    )


def load_app_data() -> dict:
    if STORE_PATH.exists():
        with open(STORE_PATH, "r") as f:
            data = json.load(f)
    else:
        data = {}
    # Ensure config is valid
    try:
        data = ConfigModel(**data).dict()
    except Exception:
        data = ConfigModel().dict()
    return data


def _convert_paths_to_str(obj):
    if isinstance(obj, dict):
        return {k: _convert_paths_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_paths_to_str(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, SecretStr):
        return obj.get_secret_value()
    return obj


def save_app_data(data: dict) -> None:
    # Convert all Path objects and SecretStr to str before saving
    data = _convert_paths_to_str(data)
    with open(STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_settings() -> ConfigModel:
    return ConfigModel(**load_app_data())


def set_by_path(obj: dict, path: str, value: object) -> None:
    keys = path.split(".")
    current = obj
    for k in keys[:-1]:
        current = current.setdefault(k, {})
    current[keys[-1]] = value


def set_setting(path: str, value) -> None:
    data = load_app_data()
    set_by_path(data, path, value)
    # Validate after setting
    try:
        settings = ConfigModel.parse_obj(data)
    except ValidationError as e:
        raise ValueError(str(e))
    save_app_data(settings.dict())


def get_auth() -> dict:
    return load_app_data()["auth"]


def set_auth(auth_data: dict) -> None:
    data = load_app_data()
    data["auth"] = auth_data
    save_app_data(data)


def delete_auth() -> None:
    data = load_app_data()
    data["auth"] = AuthConfig().dict()
    save_app_data(data)


def reset_settings() -> None:
    save_app_data(ConfigModel().dict())
