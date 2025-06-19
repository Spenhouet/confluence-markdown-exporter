import os

import requests
from atlassian import Confluence as ConfluenceApiSdk
from atlassian import Jira as JiraApiSdk
from pydantic import AnyHttpUrl
from pydantic import BaseModel
from pydantic import SecretStr
from pydantic import ValidationError
from pydantic import model_validator
from rich.console import Console
from rich.prompt import Confirm
from rich.prompt import Prompt
from typing_extensions import Self

from confluence_markdown_exporter.utils.credentials_store import delete_credentials
from confluence_markdown_exporter.utils.credentials_store import load_credentials
from confluence_markdown_exporter.utils.credentials_store import save_credentials

DEBUG: bool = bool(os.getenv("DEBUG"))

console = Console()


class ApiDetails(BaseModel):
    url: AnyHttpUrl
    username: str | None = None
    api_token: SecretStr | None = None
    pat: SecretStr | None = None

    @model_validator(mode="after")
    def validate_atlassian_auth(self) -> Self:
        if (self.username is None) != (self.api_token is None):
            msg = "When username is provided, API token must also be provided."
            raise ValueError(msg)

        if self.api_token and self.pat:
            msg = (
                "Both Personal Access Token (PAT) and API token are provided. "
                "Please use only one method of authentication."
            )
            raise ValueError(msg)

        return self


class ApiSettings(BaseModel):
    confluence: ApiDetails
    jira: ApiDetails


retry_config = {
    "backoff_and_retry": True,
    "backoff_factor": 2,
    "max_backoff_seconds": 60,
    "max_backoff_retries": 5,
    "retry_status_codes": [413, 429, 502, 503, 504],
}


# --- Credential Management ---
def logout() -> None:
    delete_credentials()
    console.print("[yellow]Logged out. Credentials removed from app data store.[/yellow]")


class ApiClientFactory:
    def __init__(self, retry_config: dict) -> None:
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


# Debugging response hooks
def get_api_instances() -> tuple[ConfluenceApiSdk, JiraApiSdk]:
    while True:
        auth_data = load_credentials()
        retry_config = {
            "backoff_and_retry": True,
            "backoff_factor": 2,
            "max_backoff_seconds": 60,
            "max_backoff_retries": 5,
            "retry_status_codes": [413, 429, 502, 503, 504],
        }
        factory = ApiClientFactory(retry_config)
        if auth_data is None:
            auth_data = prompt_for_auth()
        try:
            settings = ApiSettings.model_validate(auth_data)
            confluence = factory.create_confluence(settings.confluence)
            jira = factory.create_jira(settings.jira)
        except ValidationError as e:
            console.print("[red]Authentication validation failed:[/red]")
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err["loc"])
                msg = err["msg"]
                console.print(f"[red]  {loc}: {msg}[/red]")
            delete_credentials()
            continue
        except ConnectionError as e:
            console.print(f"[red]{e}[/red]")
            delete_credentials()
            continue
        save_credentials(auth_data)
        console.print("[green]Authentication saved to app data store.[/green]")
        return confluence, jira


def prompt_for_service_auth(service_name: str) -> dict:
    console.print(f"[bold cyan]Enter {service_name} authentication:[/bold cyan]")
    url = Prompt.ask(f"{service_name} URL (e.g. https://company.atlassian.net)")
    method = Prompt.ask(
        "Authentication method",
        choices=["api_token", "pat", "none"],
        default="api_token",
    )
    if method == "api_token":
        username = Prompt.ask(f"{service_name} Username (email)")
        api_token = Prompt.ask("API Token", password=True)
        pat = None
    elif method == "pat":
        username = None
        api_token = None
        pat = Prompt.ask("Personal Access Token (PAT)", password=True)
    else:  # none
        username = None
        api_token = None
        pat = None
        console.print(
            "[yellow]Only content not requiring authentication will be accessible.[/yellow]"
        )
        if not Confirm.ask("Are you sure you want to continue without authentication?"):
            return prompt_for_service_auth(service_name)
    return {"url": url, "username": username, "api_token": api_token, "pat": pat}


def prompt_for_auth() -> dict:
    console.print("[blue]Please provide authentication details for Confluence and Jira.[/blue]")
    if Confirm.ask("[bold cyan]Do you want to use the same authentication for both?[/bold cyan]"):
        auth = prompt_for_service_auth("Atlassian")
        return {"confluence": auth, "jira": auth}
    confluence = prompt_for_service_auth("Confluence")
    jira = prompt_for_service_auth("Jira")
    return {"confluence": confluence, "jira": jira}


confluence, jira = get_api_instances()


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
