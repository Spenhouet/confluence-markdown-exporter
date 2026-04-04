import logging
import os
from functools import lru_cache

import questionary
import requests
from atlassian import Confluence as ConfluenceApiSdk
from atlassian import Jira as JiraApiSdk
from questionary import Style

from confluence_markdown_exporter.utils.app_data_store import ApiDetails
from confluence_markdown_exporter.utils.app_data_store import AtlassianSdkConnectionConfig
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import set_setting
from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop
from confluence_markdown_exporter.utils.type_converter import str_to_bool

DEBUG: bool = str_to_bool(os.getenv("DEBUG", "False"))

logger = logging.getLogger(__name__)


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

    def create_confluence(self, auth: ApiDetails) -> ConfluenceApiSdk:
        try:
            instance = ConfluenceApiSdk(
                url=str(auth.url),
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

    def create_jira(self, auth: ApiDetails) -> JiraApiSdk:
        try:
            instance = JiraApiSdk(
                url=str(auth.url),
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


def get_confluence_instance() -> ConfluenceApiSdk:
    """Get authenticated Confluence API client using current settings."""
    settings = get_settings()
    auth = settings.auth

    while True:
        try:
            confluence = ApiClientFactory(settings.connection_config).create_confluence(
                auth.confluence
            )
            break
        except ConnectionError as e:
            questionary.print(
                f"{e}\nRedirecting to Confluence authentication config...",
                style="fg:red bold",
            )
            main_config_menu_loop("auth.confluence")
            settings = get_settings()
            auth = settings.auth

    if DEBUG:
        confluence.session.hooks["response"] = [response_hook]

    return confluence


@lru_cache(maxsize=1)
def get_jira_instance() -> JiraApiSdk:
    """Get authenticated Jira API client using current settings with required authentication."""
    settings = get_settings()

    # Check if Jira enrichment is enabled
    if not settings.export.enable_jira_enrichment:
        msg = "Jira API client was requested eventhough Jira enrichment is disabled."
        raise RuntimeWarning(msg)

    auth = settings.auth

    while True:
        try:
            jira = ApiClientFactory(settings.connection_config).create_jira(auth.jira)
            break
        except ConnectionError:
            # Ask if user wants to use Confluence credentials for Jira
            use_confluence = questionary.confirm(
                "Jira connection failed. Use the same authentication as for Confluence?",
                default=False,
                style=Style([("question", "fg:yellow")]),
            ).ask()
            if use_confluence:
                set_setting("auth.jira", auth.confluence.model_dump())
                settings = get_settings()
                auth = settings.auth
                continue

            questionary.print(
                "Redirecting to Jira authentication config...",
                style="fg:red bold",
            )
            main_config_menu_loop("auth.jira")
            settings = get_settings()
            auth = settings.auth

    jira.session.hooks["response"].append(_jira_auth_failure_hook)

    if DEBUG:
        jira.session.hooks["response"].append(response_hook)

    return jira


def handle_jira_auth_failure() -> None:
    """Handle a Jira authentication failure: open the Jira auth config dialog."""
    questionary.print(
        "Jira authentication failed.\nRedirecting to Jira authentication config...",
        style="fg:red bold",
    )
    get_jira_instance.cache_clear()
    main_config_menu_loop("auth.jira")
