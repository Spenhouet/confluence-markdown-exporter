"""Handles storage and retrieval of application data (auth and settings) for the exporter."""

import json
import os
from pathlib import Path
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import SecretStr
from pydantic import ValidationError
from pydantic import field_serializer
from pydantic import field_validator
from pydantic import model_validator
from pydantic_settings import BaseSettings
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings import SettingsConfigDict
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


class AtlassianSdkConnectionConfig(BaseModel):
    """Connection parameters forwarded directly to the Atlassian SDK client constructors.

    Only fields that are valid constructor keyword arguments for
    atlassian.Confluence (ConfluenceApiSdk) and atlassian.Jira (JiraApiSdk)
    may be added here.
    """

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
    timeout: int = Field(
        default=30,
        title="Request Timeout",
        description=(
            "Timeout in seconds for API requests. Prevents hanging on slow/unresponsive servers."
        ),
    )


class ConnectionConfig(AtlassianSdkConnectionConfig):
    """Full connection configuration, extending the Atlassian SDK config with app-level settings."""

    use_v2_api: bool = Field(
        default=False,
        title="Use Confluence v2 REST API",
        description=(
            "Enable Confluence REST API v2 endpoints where available. "
            "Supported by Atlassian Cloud and Confluence Data Center 8+. "
            "Must be disabled for older self-hosted Confluence Server instances."
        ),
    )
    max_workers: int = Field(
        default=20,
        title="Max Workers",
        description=(
            "Maximum number of parallel workers for page export. "
            "Set to 1 for serial mode (useful for debugging). "
            "Higher values improve performance but may hit API rate limits."
        ),
    )


class ApiDetails(BaseModel):
    """API authentication credentials for a single instance.

    The instance URL is used as the dict key in AuthConfig, not stored here.
    """

    username: SecretStr = Field(
        default=SecretStr(""),
        title="Username (email)",
        description="Username or email for API authentication.",
    )
    api_token: SecretStr = Field(
        default=SecretStr(""),
        title="API Token",
        description=(
            "API token for authentication (if required). "
            "Create an Atlassian API token at "
            "https://id.atlassian.com/manage-profile/security/api-tokens. "
            "See Atlassian documentation for details."
        ),
    )
    pat: SecretStr = Field(
        default=SecretStr(""),
        title="Personal Access Token (PAT)",
        description=(
            "Personal Access Token for authentication. "
            "Set this if you use a PAT instead of username+API token. "
            "See your Atlassian instance documentation for how to create a PAT."
        ),
    )
    cloud_id: str = Field(
        default="",
        title="Cloud ID",
        description=(
            "Atlassian Cloud ID for this instance. When set, API calls are routed through "
            "the Atlassian API gateway (https://api.atlassian.com/ex/confluence/{cloud_id}), "
            "which enables the use of scoped API tokens. "
            "For Atlassian Cloud instances this is fetched and stored automatically. "
            "To find your Cloud ID manually, see "
            "https://support.atlassian.com/jira/kb/retrieve-my-atlassian-sites-cloud-id/."
        ),
    )

    @field_serializer("username", "api_token", "pat", when_used="json")
    def dump_secret(self, v: SecretStr) -> str:
        return v.get_secret_value()


class AuthConfig(BaseModel):
    """Authentication configuration for Confluence and Jira.

    Credentials are stored in dicts keyed by the instance base URL
    (e.g. ``"https://company.atlassian.net"``).  No "active" pointer is kept —
    the right instance is selected by matching the URL of the page or space
    being exported.
    """

    confluence: dict[str, ApiDetails] = Field(
        default_factory=dict,
        title="Confluence Accounts",
        description=(
            "Confluence authentication credentials keyed by instance base URL. "
            "Example key: 'https://company.atlassian.net'"
        ),
    )
    jira: dict[str, ApiDetails] = Field(
        default_factory=dict,
        title="Jira Accounts",
        description=(
            "Jira authentication credentials keyed by instance base URL. "
            "Example key: 'https://company.atlassian.net'"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate(cls, data: object) -> object:  # noqa: C901, PLR0912
        """Migrate legacy config formats to the current URL-keyed dict format.

        Also normalises all instance URL keys (strips trailing slashes) so that
        entries written with and without a trailing slash are treated as identical.
        """
        if not isinstance(data, dict):
            return data
        for service in ("confluence", "jira"):
            val = data.get(service)
            if not isinstance(val, dict):
                continue
            # Legacy v1: single ApiDetails with a 'url' field at the top level
            # e.g. {"url": "https://...", "username": "...", ...}
            if "url" in val and not _looks_like_url_keyed(val):
                url = val.pop("url", "") or ""
                # Remove stale active_* fields that were in the same dict
                val.pop("active_confluence", None)
                val.pop("active_jira", None)
                data[service] = {url.rstrip("/"): val} if url else {}
            # Legacy v2: named-key dict from the previous multi-instance refactor.
            # e.g. {"default": {"url": "https://...", ...}, "active_confluence": "default"}
            elif not _looks_like_url_keyed(val):
                migrated: dict = {}
                for k, v in val.items():
                    if k in ("active_confluence", "active_jira"):
                        continue
                    if isinstance(v, dict):
                        inner_url = v.pop("url", "") or ""
                        if inner_url:
                            migrated[inner_url.rstrip("/")] = v
                        elif v:
                            migrated[k] = v  # keep as-is if no URL
                if migrated:
                    data[service] = migrated
            else:
                # Current URL-keyed format: normalise any trailing slashes on existing keys
                normalised: dict = {}
                for k, v in val.items():
                    normalised[k.rstrip("/")] = v
                data[service] = normalised
        # Drop top-level active_* fields that were stored in auth
        data.pop("active_confluence", None)
        data.pop("active_jira", None)
        return data

    def get_instance(self, url: str) -> ApiDetails | None:
        """Return the Confluence ApiDetails whose key matches *url* (exact or host match)."""
        url = normalize_instance_url(url)
        return self.confluence.get(url) or self._match_by_host(self.confluence, url)

    def get_jira_instance(self, url: str) -> ApiDetails | None:
        """Return the Jira ApiDetails whose key matches *url* (exact or host match)."""
        url = normalize_instance_url(url)
        return self.jira.get(url) or self._match_by_host(self.jira, url)

    def default_confluence_url(self) -> str | None:
        """Return the URL of the only configured Confluence instance, or None if 0 or 2+."""
        return next(iter(self.confluence)) if len(self.confluence) == 1 else None

    def default_jira_url(self) -> str | None:
        """Return the URL of the only configured Jira instance, or None if 0 or 2+."""
        return next(iter(self.jira)) if len(self.jira) == 1 else None

    @staticmethod
    def _match_by_host(instances: dict[str, ApiDetails], url: str) -> ApiDetails | None:
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or url
        # Gateway URLs must match exactly — multiple tenants share api.atlassian.com.
        if host == "api.atlassian.com":
            return None
        for key, details in instances.items():
            key_parsed = urllib.parse.urlparse(key)
            # Skip gateway-style keys when doing hostname-only matching
            if key_parsed.hostname == "api.atlassian.com":
                continue
            if key_parsed.hostname != host or key_parsed.port != parsed.port:
                continue
            # Key stored without a context path matches any context path on the same host
            # (e.g. stored as "https://host", URL is "https://host/confluence/spaces/...")
            if not key_parsed.path.strip("/"):
                return details
            # Key stored with a context path must be a prefix of the lookup URL's path
            # (e.g. stored as "https://host/confluence", URL is "https://host/confluence/spaces/...")
            if parsed.path.startswith(key_parsed.path):
                return details
        return None


def _looks_like_url_keyed(d: dict) -> bool:
    """Return True if the dict looks like it's already keyed by URLs (not by field names)."""
    return any(k.startswith(("http://", "https://")) for k in d)


def normalize_instance_url(url: str) -> str:
    """Strip trailing slashes from an instance URL for consistent key storage."""
    return url.rstrip("/")


class ExportConfig(BaseModel):
    """Export settings for markdown and attachments."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        title="Log Level",
        description=(
            "Controls how much output the exporter prints. "
            "DEBUG shows every step, INFO shows key milestones, "
            "WARNING shows only warnings and errors, ERROR shows only errors. "
            "In CI environments (CI=true / NO_COLOR set) rich formatting is suppressed "
            "automatically."
        ),
    )
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
    page_href: Literal["absolute", "relative", "wiki"] = Field(
        default="relative",
        title="Page Href Style",
        description=(
            "How to generate page href paths. Options: absolute, relative, wiki.\n"
            "  - `relative` links are relative to the page\n"
            "  - `absolute` links start from the configured output path\n"
            "  - `wiki` generates Obsidian-style [[Page Title]] wiki links"
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
    attachment_href: Literal["absolute", "relative", "wiki"] = Field(
        default="relative",
        title="Attachment Href Style",
        description=(
            "How to generate attachment href paths. Options: absolute, relative, wiki.\n"
            "  - `relative` links are relative to the page\n"
            "  - `absolute` links start from the configured output path\n"
            "  - `wiki` generates Obsidian-style ![[Attachment Name]] wiki links"
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
            "  - {attachment_title}: The title of the attachment (without file extension).\n"
            "  - {attachment_file_id}: The file ID of the attachment.\n"
            "  - {attachment_extension}: The file extension of the attachment,\n"
            "including the leading dot."
        ),
        examples=["{space_name}/attachments/{attachment_file_id}{attachment_extension}"],
    )

    @field_validator("attachment_path", mode="before")
    @classmethod
    def _migrate_attachment_path(cls, v: object) -> object:
        """Migrate templates that used {attachment_title} as the full filename.

        Before this change, {attachment_title} included the file extension.
        Templates that relied on that (i.e. no explicit {attachment_extension})
        are silently updated so file extensions are preserved.
        """
        if (
            isinstance(v, str)
            and "{attachment_title}" in v
            and "{attachment_extension}" not in v
        ):
            return v.replace("{attachment_title}", "{attachment_title}{attachment_extension}")
        return v

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
    page_properties_as_front_matter: bool = Field(
        default=True,
        title="Page Properties as Front Matter",
        description=(
            "Whether to convert Confluence page property tables (Page Properties macro) "
            "into YAML front matter. "
            "When enabled (default), the macro's key-value table is extracted and written "
            "as YAML front matter at the top of the exported file. "
            "When disabled, the macro is converted to a regular markdown table."
        ),
    )
    filename_encoding: str = Field(
        default='"<":"_",">":"_",":":"_","\\"":"_","/":"_","\\\\":"_","|":"_","?":"_","*":"_","\\u0000":"_","[":"_","]":"_","\'":"_","’":"_","´":"_","`":"_"',  # noqa: RUF001
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
    filename_lowercase: bool = Field(
        default=False,
        title="Enforce lowercase paths",
        description=(
            "Make all paths/files lowercase.\nBy default the original casing will be retained.\n"
        ),
    )
    include_document_title: bool = Field(
        default=True,
        title="Include Document Title",
        description=(
            "Whether to include the document title in the exported markdown file. "
            "If enabled, the title will be added as a top-level heading."
        ),
    )
    enable_jira_enrichment: bool = Field(
        default=True,
        title="Enable Jira Enrichment",
        description=(
            "Whether to fetch Jira issue data to enrich Confluence pages. "
            "When enabled, Jira issue links will include the issue summary. "
            "When disabled, only the issue key and link will be included."
        ),
    )
    skip_unchanged: bool = Field(
        default=True,
        title="Skip Unchanged Pages",
        description="Skip exporting pages that have not changed since last export.",
    )
    cleanup_stale: bool = Field(
        default=True,
        title="Cleanup Stale Files",
        description=(
            "After export, delete local files for pages that have been removed "
            "from Confluence or whose export path has changed."
        ),
    )
    lockfile_name: str = Field(
        default="confluence-lock.json",
        title="Lock File Name",
        description="Name of the lock file used to track exported pages.",
    )
    existence_check_batch_size: int = Field(
        default=250,
        title="Existence Check Batch Size",
        description=(
            "Number of page IDs per batch when verifying page existence during cleanup. "
            "For self-hosted Confluence (CQL), this is internally capped at 25."
        ),
    )


class ConfigModel(BaseModel):
    """Top-level application configuration model (used for persistence only)."""

    export: ExportConfig = Field(default_factory=ExportConfig, title="Export Settings")
    connection_config: ConnectionConfig = Field(
        default_factory=ConnectionConfig, title="Connection Configuration"
    )
    auth: AuthConfig = Field(default_factory=AuthConfig, title="Authentication")


class _JsonConfigSource(PydanticBaseSettingsSource):
    """Settings source that reads from the JSON config file (lower priority than ENV vars)."""

    def get_field_value(self, field: Any, field_name: str) -> Any:  # noqa: ANN401
        return None, field_name, False

    def field_is_complex(self, field: Any) -> bool:  # noqa: ANN401
        return True

    def __call__(self) -> dict[str, Any]:
        if APP_CONFIG_PATH.exists():
            try:
                raw = json.loads(APP_CONFIG_PATH.read_text())
                return ConfigModel(**raw).model_dump()
            except Exception:  # noqa: BLE001
                return ConfigModel().model_dump()
        return ConfigModel().model_dump()


class AppSettings(BaseSettings):
    """Effective application settings: ENV vars take precedence over the config file.

    ENV vars use the prefix ``CME_`` and double-underscore (``__``) as the nested field
    delimiter, matching the dot-notation config keys but uppercased.  For example::

        CME_EXPORT__LOG_LEVEL=DEBUG
        CME_EXPORT__OUTPUT_PATH=/tmp/export
        CME_CONNECTION_CONFIG__MAX_WORKERS=5
        CME_CONNECTION_CONFIG__VERIFY_SSL=false
    """

    model_config = SettingsConfigDict(
        env_prefix="CME_",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    export: ExportConfig = Field(default_factory=ExportConfig, title="Export Settings")
    connection_config: ConnectionConfig = Field(
        default_factory=ConnectionConfig, title="Connection Configuration"
    )
    auth: AuthConfig = Field(default_factory=AuthConfig, title="Authentication")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """ENV vars override JSON file config; init values override both."""
        return (init_settings, env_settings, _JsonConfigSource(settings_cls))


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


def get_settings() -> AppSettings:
    """Get the effective application settings (ENV vars override stored config)."""
    return AppSettings()


def _set_by_path(obj: dict, path: str, value: object) -> None:
    """Set a value in a nested dict using dot notation path."""
    keys = path.split(".")
    current = obj
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


def _set_by_keys(obj: dict, keys: list[str], value: object) -> None:
    """Set a value in a nested dict using an explicit list of key components."""
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


def set_setting_with_keys(keys: list[str], value: object) -> None:
    """Set a setting by an explicit list of path components and save to config file.

    Use this instead of ``set_setting`` when any path component contains dots
    (e.g. a URL used as a dict key: ``["auth", "confluence", "https://x.y", "username"]``).
    """
    data = load_app_data()
    _set_by_keys(data, keys, value)
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
