import logging
import os
from threading import Lock
from threading import local

import questionary
import requests
from atlassian import Confluence as ConfluenceApiSdk
from atlassian import Jira as JiraApiSdk
from questionary import Style

from confluence_markdown_exporter.utils.app_data_store import ApiDetails
from confluence_markdown_exporter.utils.app_data_store import AtlassianSdkConnectionConfig
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import set_setting_with_keys
from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop
from confluence_markdown_exporter.utils.type_converter import str_to_bool

DEBUG: bool = str_to_bool(os.getenv("DEBUG", "False"))

logger = logging.getLogger(__name__)

# URL-keyed caches for API clients
_confluence_clients: dict[str, ConfluenceApiSdk] = {}
_jira_clients: dict[str, JiraApiSdk] = {}
_clients_lock = Lock()

# Thread-local storage for per-URL Confluence clients (one per worker thread per URL)
_thread_local = local()


class JiraAuthenticationError(Exception):
    """Raised when a Jira API response indicates an authentication failure."""


def _jira_auth_failure_hook(
    response: requests.Response, *_args: object, **_kwargs: object
) -> requests.Response:
    """Raise JiraAuthenticationError when Jira signals authentication failure."""
    if response.headers.get("X-Seraph-Loginreason") == "AUTHENTICATED_FAILED":
        msg = f"Jira authentication failed for request to {response.url}"
        raise JiraAuthenticationError(msg)
    return response


def response_hook(
    response: requests.Response, *_args: object, **_kwargs: object
) -> requests.Response:
    """Log response headers when requests fail."""
    if not response.ok:
        logger.warning(
            f"Request to {response.url} failed with status {response.status_code}"
            f"Response headers: {dict(response.headers)}"
        )
    return response


class ApiClientFactory:
    """Factory for creating authenticated Confluence and Jira API clients with retry config."""

    def __init__(self, connection_config: AtlassianSdkConnectionConfig) -> None:
        # Reconstruct as the base SDK type so model_dump() only yields SDK-compatible fields,
        # even when a ConnectionConfig subclass is passed.
        self.connection_config = AtlassianSdkConnectionConfig.model_validate(
            connection_config.model_dump()
        )

    def create_confluence(self, url: str, auth: ApiDetails) -> ConfluenceApiSdk:
        try:
            instance = ConfluenceApiSdk(
                url=url,
                username=auth.username.get_secret_value() if auth.api_token else None,
                password=auth.api_token.get_secret_value() if auth.api_token else None,
                token=auth.pat.get_secret_value() if auth.pat else None,
                **self.connection_config.model_dump(),
            )
            instance.get_all_spaces(limit=1)
        except Exception as e:
            msg = f"Confluence connection failed: {e}"
            raise ConnectionError(msg) from e
        return instance

    def create_jira(self, url: str, auth: ApiDetails) -> JiraApiSdk:
        try:
            instance = JiraApiSdk(
                url=url,
                username=auth.username.get_secret_value() if auth.api_token else None,
                password=auth.api_token.get_secret_value() if auth.api_token else None,
                token=auth.pat.get_secret_value() if auth.pat else None,
                **self.connection_config.model_dump(),
            )
            instance.get_all_projects()
        except Exception as e:
            msg = f"Jira connection failed: {e}"
            raise ConnectionError(msg) from e
        return instance


def _resolve_confluence_url(url: str | None) -> str:
    """Return a Confluence URL to connect to.

    If *url* is given, use it directly.  Otherwise use the only configured
    Confluence instance, prompting the user to add one if none are configured.
    """
    if url:
        return url
    settings = get_settings()
    default = settings.auth.default_confluence_url()
    if default:
        return default
    if settings.auth.confluence:
        msg = (
            "Multiple Confluence instances are configured. "
            "Please provide a --url to select one."
        )
        raise ValueError(msg)
    # No instances configured - open config menu
    questionary.print("No Confluence instance configured.", style="fg:yellow bold")
    main_config_menu_loop("auth.confluence")
    return _resolve_confluence_url(None)


def _resolve_jira_url(url: str | None) -> str:
    """Return a Jira URL to connect to (same logic as _resolve_confluence_url)."""
    if url:
        return url
    settings = get_settings()
    default = settings.auth.default_jira_url()
    if default:
        return default
    if settings.auth.jira:
        msg = (
            "Multiple Jira instances are configured. "
            "Please provide a --url to select one."
        )
        raise ValueError(msg)
    questionary.print("No Jira instance configured.", style="fg:yellow bold")
    main_config_menu_loop("auth.jira")
    return _resolve_jira_url(None)


def get_confluence_instance(url: str | None = None) -> ConfluenceApiSdk:
    """Get authenticated Confluence API client for *url*.

    Creates a new client if one doesn't exist for that URL yet and caches it.
    Prompts for auth config on connection failure.
    """
    resolved_url = _resolve_confluence_url(url)

    with _clients_lock:
        if resolved_url in _confluence_clients:
            return _confluence_clients[resolved_url]

    settings = get_settings()

    while True:
        auth = settings.auth.get_instance(resolved_url) or ApiDetails()
        try:
            client = ApiClientFactory(settings.connection_config).create_confluence(
                resolved_url, auth
            )
            break
        except ConnectionError as e:
            questionary.print(
                f"{e}\nRedirecting to Confluence authentication config...",
                style="fg:red bold",
            )
            main_config_menu_loop("auth.confluence")
            settings = get_settings()

    if DEBUG:
        client.session.hooks["response"] = [response_hook]

    with _clients_lock:
        _confluence_clients[resolved_url] = client
    return client


def get_thread_confluence(base_url: str) -> ConfluenceApiSdk:
    """Get or create a thread-local Confluence client for *base_url*.

    The atlassian-python-api Confluence client uses requests.Session, which is
    NOT thread-safe.  Each worker thread keeps its own dict of clients keyed by
    base URL so that multi-instance exports are also thread-safe.
    """
    if not hasattr(_thread_local, "clients"):
        _thread_local.clients = {}
    if base_url not in _thread_local.clients:
        _thread_local.clients[base_url] = get_confluence_instance(base_url)
    return _thread_local.clients[base_url]


def get_jira_instance(url: str | None = None) -> JiraApiSdk:
    """Get authenticated Jira API client for *url*.

    Creates a new client if one doesn't exist for that URL yet and caches it.
    """
    settings = get_settings()

    if not settings.export.enable_jira_enrichment:
        msg = "Jira API client was requested eventhough Jira enrichment is disabled."
        raise RuntimeWarning(msg)

    resolved_url = _resolve_jira_url(url)

    with _clients_lock:
        if resolved_url in _jira_clients:
            return _jira_clients[resolved_url]

    while True:
        auth = settings.auth.get_jira_instance(resolved_url) or ApiDetails()
        try:
            client = ApiClientFactory(settings.connection_config).create_jira(
                resolved_url, auth
            )
            break
        except ConnectionError:
            use_confluence = questionary.confirm(
                "Jira connection failed. Use the same authentication as for Confluence?",
                default=False,
                style=Style([("question", "fg:yellow")]),
            ).ask()
            if use_confluence:
                confluence_auth = settings.auth.get_instance(resolved_url) or ApiDetails()
                set_setting_with_keys(
                    ["auth", "jira", resolved_url], confluence_auth.model_dump()
                )
                settings = get_settings()
                continue

            questionary.print(
                "Redirecting to Jira authentication config...",
                style="fg:red bold",
            )
            main_config_menu_loop("auth.jira")
            settings = get_settings()

    client.session.hooks["response"].append(_jira_auth_failure_hook)

    if DEBUG:
        client.session.hooks["response"].append(response_hook)

    with _clients_lock:
        _jira_clients[resolved_url] = client
    return client


def invalidate_confluence_client(url: str) -> None:
    """Remove a cached Confluence client so the next call creates a fresh one."""
    with _clients_lock:
        _confluence_clients.pop(url, None)


def invalidate_jira_client(url: str) -> None:
    """Remove a cached Jira client so the next call creates a fresh one."""
    with _clients_lock:
        _jira_clients.pop(url, None)


def handle_jira_auth_failure(url: str) -> None:
    """Handle a Jira authentication failure: open the Jira auth config dialog."""
    questionary.print(
        "Jira authentication failed.\nRedirecting to Jira authentication config...",
        style="fg:red bold",
    )
    invalidate_jira_client(url)
    main_config_menu_loop("auth.jira")
