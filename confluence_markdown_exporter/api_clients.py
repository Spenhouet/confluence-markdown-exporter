import os
from typing import Any

import requests
from atlassian import Confluence as ConfluenceApiSdk
from atlassian import Jira as JiraApiSdk
from pydantic import BaseModel
from pydantic import model_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from typing_extensions import Self

DEBUG: bool = bool(os.getenv("DEBUG"))


class ApiDetails(BaseModel):
    url: str
    username: str | None = None
    api_token: str | None = None
    pat: str | None = None

    @model_validator(mode="after")
    def validate_atlassian_auth(self) -> Self:
        if (self.username and self.api_token) or self.pat:
            return self

        msg = (
            "Either Personal Access Token (PAT) or basis authentication via username and API token "
            "must be provided via environment variables. See README.md for more information."
        )
        raise ValueError(msg)


class ApiSettings(BaseSettings):
    atlassian: ApiDetails
    confluence: ApiDetails
    jira: ApiDetails

    @model_validator(mode="before")
    @classmethod
    def fallback_authentication(cls, data: dict[str, Any]) -> dict[str, Any]:
        if "atlassian" not in data and "confluence" in data:
            data["atlassian"] = data["confluence"]
        if "atlassian" not in data and "jira" in data:
            data["atlassian"] = data["jira"]
        if "confluence" not in data and "atlassian" in data:
            data["confluence"] = data["atlassian"]
        if "jira" not in data and "atlassian" in data:
            data["jira"] = data["atlassian"]
        return data

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_nested_delimiter="_", env_nested_max_split=1
    )


api_settings = ApiSettings()  # type: ignore reportCallIssue as the parameters are read via env file

retry_config = {
    "backoff_and_retry": True,
    "backoff_factor": 2,
    "max_backoff_seconds": 60,
    "max_backoff_retries": 5,
    "retry_status_codes": [413, 429, 502, 503, 504],
}

confluence = ConfluenceApiSdk(
    url=api_settings.confluence.url,
    username=api_settings.confluence.username,
    password=api_settings.confluence.api_token,
    token=api_settings.confluence.pat,
    **retry_config,
)

jira = JiraApiSdk(
    url=api_settings.jira.url,
    username=api_settings.jira.username,
    password=api_settings.jira.api_token,
    token=api_settings.jira.pat,
    **retry_config,
)


def response_hook(
    response: requests.Response, *args: object, **kwargs: object
) -> requests.Response:
    """Log response headers when requests fail."""
    if not response.ok:
        print(f"Request to {response.url} failed with status {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
    return response


if DEBUG:
    confluence.session.hooks["response"] = [response_hook]
    jira.session.hooks["response"] = [response_hook]
