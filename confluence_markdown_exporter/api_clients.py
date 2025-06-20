import os
from typing import Any

import questionary
import requests
from atlassian import Confluence as ConfluenceApiSdk
from atlassian import Jira as JiraApiSdk
from questionary import Style

from confluence_markdown_exporter.utils.app_data_store import ApiDetails
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import set_setting
from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop

DEBUG: bool = bool(os.getenv("DEBUG"))


def response_hook(
    response: requests.Response, *args: object, **kwargs: object
) -> requests.Response:
    """Log response headers when requests fail."""
    if not response.ok:
        print(f"Request to {response.url} failed with status {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
    return response


class ApiClientFactory:
    """Factory for creating authenticated Confluence and Jira API clients with retry config."""

    def __init__(self, retry_config: dict[str, Any]) -> None:
        self.retry_config = retry_config

    def create_confluence(self, auth: ApiDetails) -> ConfluenceApiSdk:
        try:
            instance = ConfluenceApiSdk(
                url=str(auth.url),
                username=auth.username,
                password=auth.api_token.get_secret_value() if auth.api_token else None,
                token=auth.pat.get_secret_value() if auth.pat else None,
                **self.retry_config,
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
                username=auth.username,
                password=auth.api_token.get_secret_value() if auth.api_token else None,
                token=auth.pat.get_secret_value() if auth.pat else None,
                **self.retry_config,
            )
            instance.get_all_projects()
        except Exception as e:
            msg = f"Jira connection failed: {e}"
            raise ConnectionError(msg) from e
        return instance


def get_api_instances() -> tuple[ConfluenceApiSdk, JiraApiSdk]:
    """Get authenticated Confluence and Jira API clients using current settings."""
    settings = get_settings()
    auth = settings.auth
    retry_config = settings.retry_config.model_dump()
    while True:
        try:
            confluence = ApiClientFactory(retry_config).create_confluence(auth.confluence)
            break
        except ConnectionError:
            questionary.print(
                "Confluence connection failed: Redirecting to Confluence authentication config...",
                style="fg:red bold",
            )
            main_config_menu_loop("auth.confluence")
            settings = get_settings()
            auth = settings.auth
    # Retry loop for jira
    while True:
        try:
            jira = ApiClientFactory(retry_config).create_jira(auth.jira)
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

    if DEBUG:
        confluence.session.hooks["response"] = [response_hook]
        jira.session.hooks["response"] = [response_hook]

    return confluence, jira
