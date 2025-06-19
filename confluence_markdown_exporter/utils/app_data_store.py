"""Handles storage and retrieval of application data (auth and settings) for the exporter."""

import json
from pathlib import Path
from typing import Literal

import typer
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError
from rich.console import Console

APP_NAME = "confluence-markdown-exporter"
APP_CONFIG_DIR = Path(typer.get_app_dir(APP_NAME))
APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = APP_CONFIG_DIR / "app_data.json"

console = Console()


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
    )


def load_app_data() -> dict:
    if STORE_PATH.exists():
        with open(STORE_PATH, "r") as f:
            data = json.load(f)
    else:
        data = {}
    # Ensure settings and auth keys exist
    if "settings" not in data:
        data["settings"] = ConfigModel().dict()
    else:
        # Validate and fill in any missing defaults using the model
        try:
            data["settings"] = ConfigModel(**data["settings"]).dict()
        except Exception:
            data["settings"] = ConfigModel().dict()
    if "auth" not in data:
        data["auth"] = {}
    return data


def _convert_paths_to_str(obj):
    if isinstance(obj, dict):
        return {k: _convert_paths_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_paths_to_str(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def save_app_data(data: dict) -> None:
    # Convert all Path objects to str before saving
    data = _convert_paths_to_str(data)
    with open(STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_settings() -> ConfigModel:
    return ConfigModel(**load_app_data()["settings"])


def set_setting(key: str, value) -> None:
    data = load_app_data()
    settings = ConfigModel(**data["settings"])
    if hasattr(settings, key):
        setattr(settings, key, value)
        # Validate after setting
        try:
            settings = ConfigModel.parse_obj(settings.dict())
        except ValidationError as e:
            raise ValueError(str(e))
        data["settings"] = settings.dict()
        save_app_data(data)
    else:
        raise KeyError(f"Unknown config key: {key}")


def set_nested_setting(parent_key: str, subkey: str, value) -> None:
    data = load_app_data()
    settings = ConfigModel(**data["settings"])
    parent = getattr(settings, parent_key)
    if hasattr(parent, subkey):
        setattr(parent, subkey, value)
        # Validate after setting
        try:
            settings = ConfigModel.parse_obj(settings.dict())
        except ValidationError as e:
            raise ValueError(str(e))
        data["settings"] = settings.dict()
        save_app_data(data)
    else:
        raise KeyError(f"Unknown config subkey: {parent_key}.{subkey}")


def get_auth() -> dict:
    return load_app_data()["auth"]


def set_auth(auth_data: dict) -> None:
    data = load_app_data()
    data["auth"] = auth_data
    save_app_data(data)


def delete_auth() -> None:
    data = load_app_data()
    data["auth"] = {}
    save_app_data(data)


def reset_settings() -> None:
    data = load_app_data()
    data["settings"] = ConfigModel().dict()
    save_app_data(data)
