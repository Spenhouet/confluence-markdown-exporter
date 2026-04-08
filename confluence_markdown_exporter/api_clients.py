import logging
import re
import urllib.parse
from threading import Lock
from threading import local
from typing import Annotated

import requests
from atlassian import Confluence as ConfluenceApiSdk
from atlassian import Jira as JiraApiSdk
from pydantic import AfterValidator
from pydantic import BaseModel

from confluence_markdown_exporter.utils.app_data_store import ApiDetails
from confluence_markdown_exporter.utils.app_data_store import AtlassianSdkConnectionConfig
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import normalize_instance_url
from confluence_markdown_exporter.utils.app_data_store import set_setting_with_keys

logger = logging.getLogger(__name__)

# URL-keyed caches for API clients
_confluence_clients: dict[str, ConfluenceApiSdk] = {}
_jira_clients: dict[str, JiraApiSdk] = {}
_clients_lock = Lock()

# Thread-local storage for per-URL Confluence clients (one per worker thread per URL)
_thread_local = local()

_CLOUD_DOMAIN = ".atlassian.net"
_GATEWAY_PREFIX = "https://api.atlassian.com/ex"


def parse_gateway_url(url: str) -> tuple[str, str] | None:
    m = re.search(r"https://api\.atlassian\.com/ex/(confluence|jira)/([^/?#]+)", url)
    return (m.group(1).lower(), m.group(2)) if m else None


def build_gateway_url(service: str, cloud_id: str) -> str:
    return f"{_GATEWAY_PREFIX}/{service.lower()}/{cloud_id}"


def ensure_service_gateway_url(url: str, service: str | None = None) -> str:
    """Ensure the gateway URL uses the specified service.

    ``https://api.atlassian.com/ex/confluence/{cloudId}``
    becomes ``https://api.atlassian.com/ex/jira/{cloudId}``.
    Non-gateway URLs are returned as-is.
    """
    if parsed := parse_gateway_url(url):
        return build_gateway_url(service or parsed[0], parsed[1])

    return url


def _is_standard_atlassian_cloud_url(url: str) -> bool:
    """Return True if *url* looks like a standard Atlassian Cloud instance URL."""
    try:
        hostname = urllib.parse.urlparse(url).hostname or ""
        return hostname.endswith(_CLOUD_DOMAIN)
    except Exception:  # noqa: BLE001
        return False


def _try_fetch_cloud_id(base_url: str) -> str | None:
    """Try to fetch the Atlassian Cloud ID from the public tenant info endpoint.

    Returns the cloud ID string, or None if the fetch fails (e.g. for Server instances).
    """
    try:
        resp = requests.get(f"{base_url}/_edge/tenant_info", timeout=5)
        if resp.ok:
            return resp.json().get("cloudId")
    except Exception as e:  # noqa: BLE001
        logger.debug("Could not fetch Cloud ID from %s/_edge/tenant_info: %s", base_url, e)
    return None


def _get_confluence_sdk_url(base_url: str, auth: ApiDetails) -> str:
    """Return the SDK URL for Confluence, using the API gateway when a Cloud ID is configured."""
    if auth.cloud_id:
        return f"{_GATEWAY_PREFIX}/confluence/{auth.cloud_id}"
    return base_url


def _get_jira_sdk_url(base_url: str, auth: ApiDetails) -> str:
    """Return the SDK URL for Jira, using the API gateway when a Cloud ID is configured."""
    if auth.cloud_id:
        return f"{_GATEWAY_PREFIX}/jira/{auth.cloud_id}"
    return base_url


def _decode_url_part(v: str | None) -> None | str:
    if v is None or v == "":
        return None
    return urllib.parse.unquote_plus(v)


class ConfluenceRef(BaseModel):
    space_key: Annotated[str, AfterValidator(_decode_url_part)]
    page_id: int | None = None
    page_title: Annotated[str | None, AfterValidator(_decode_url_part)] = None


# 1) Cloud [/wiki]/spaces/{space_key}[/pages/{page_id}[/{page_title}]]
_CLOUD_URL_RE = re.compile(
    r"^(?:/ex/confluence/[^/]+)?(?:/wiki)?/spaces/"
    r"(?P<space_key>[A-Za-z0-9_-]+)"
    r"(?:/pages/(?P<page_id>\d+)(?:/(?P<page_title>[^/?#]+))?)?"
    r"(?:/(?!pages/)[^/?#]+)?/?$"
)

# 2) Server [/display]/{space_key}[/{page_title}]
_SERVER_URL_RE = re.compile(
    r"^(?:/display)?"
    r"/(?P<space_key>[A-Za-z0-9._-]+)"
    r"(?:/(?P<page_title>[^/?#]+))?/?$"
)


def parse_confluence_path(path: str) -> ConfluenceRef | None:
    """Parse only the path portion of a Confluence URL and return a ConfluenceRef dict.

    Matching order:
      1) Cloud [/wiki]/spaces/{space_key}[/pages/{page_id}[/{page_title}]]
      2) Server [/display]/{space_key}[/{page_title}]
    """
    if not path:
        return None
    if not path.startswith("/"):
        path = "/" + path
    path = path.rstrip("/")

    if m := _CLOUD_URL_RE.match(path) or _SERVER_URL_RE.match(path):
        return ConfluenceRef.model_validate(m.groupdict())

    return None


class AuthNotConfiguredError(BaseException):
    """Raised when a connection attempt fails and no valid auth is configured for the URL.

    Inherits from BaseException (not Exception) so that broad ``except Exception`` handlers
    in export loops do not accidentally swallow it — it must propagate to the app boundary.
    """

    def __init__(self, url: str, service: str = "Confluence") -> None:
        self.url = url
        self.service = service
        super().__init__(f"No valid authentication configured for {service} at {url}")


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
            "Request to %s failed with status %s. Response headers: %s",
            response.url,
            response.status_code,
            dict(response.headers),
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


def get_confluence_instance(url: str) -> ConfluenceApiSdk:
    """Get authenticated Confluence API client for *url*.

    Creates a new client if one doesn't exist for that URL yet and caches it.
    Prompts for auth config on connection failure.

    When the configured auth for *url* includes a Cloud ID, API calls are routed through
    the Atlassian API gateway (``https://api.atlassian.com/ex/confluence/{cloud_id}``),
    which enables the use of scoped API tokens.  For standard Atlassian Cloud instances
    (``.atlassian.net``) the Cloud ID is fetched and stored automatically on first connection.
    """
    url = normalize_instance_url(ensure_service_gateway_url(url, "confluence"))
    with _clients_lock:
        if url in _confluence_clients:
            logger.debug("Confluence client cache hit for %s", url)
            return _confluence_clients[url]

    settings = get_settings()

    auth = settings.auth.get_instance(url)
    if auth is None:
        raise AuthNotConfiguredError(url, "Confluence")

    logger.debug("Creating new Confluence client for %s", url)

    # Auto-fetch and store the Cloud ID for standard Atlassian Cloud instances
    if not auth.cloud_id and _is_standard_atlassian_cloud_url(url):
        cloud_id = _try_fetch_cloud_id(url)
        if cloud_id:
            logger.info("Auto-fetched Atlassian Cloud ID for %s — storing in config", url)
            set_setting_with_keys(["auth", "confluence", url, "cloud_id"], cloud_id)
            settings = get_settings()

    auth = settings.auth.get_instance(url) or ApiDetails()
    sdk_url = _get_confluence_sdk_url(url, auth)
    try:
        client = ApiClientFactory(settings.connection_config).create_confluence(sdk_url, auth)
        logger.info("Connected to Confluence at %s", sdk_url)
    except ConnectionError as e:
        logger.exception("[red bold]Confluence authentication failed for %s.[/red bold]", url)
        raise AuthNotConfiguredError(url, "Confluence") from e

    if settings.export.log_level == "DEBUG":
        client.session.hooks["response"] = [response_hook]

    with _clients_lock:
        _confluence_clients[url] = client
    return client


def get_thread_confluence(base_url: str) -> ConfluenceApiSdk:
    """Get or create a thread-local Confluence client for *base_url*.

    The atlassian-python-api Confluence client uses requests.Session, which is
    NOT thread-safe.  Each worker thread keeps its own dict of clients keyed by
    base URL so that multi-instance exports are also thread-safe.
    """
    base_url = normalize_instance_url(base_url)
    if not hasattr(_thread_local, "clients"):
        _thread_local.clients = {}
    if base_url not in _thread_local.clients:
        logger.debug("Initializing thread-local Confluence client for %s", base_url)
        _thread_local.clients[base_url] = get_confluence_instance(base_url)
    return _thread_local.clients[base_url]


def get_jira_instance(url: str) -> JiraApiSdk:
    """Get authenticated Jira API client for *url*.

    Creates a new client if one doesn't exist for that URL yet and caches it.

    When the input is a Confluence gateway URL (``/ex/confluence/{cloudId}``), it is
    automatically converted to the Jira gateway URL (``/ex/jira/{cloudId}``) before
    auth lookup and SDK connection.  This handles the common case where the caller
    derives the Jira URL from a Confluence page's ``base_url``.

    When the configured auth for *url* includes a Cloud ID, API calls are routed through
    the Atlassian API gateway (``https://api.atlassian.com/ex/jira/{cloud_id}``).
    For standard Atlassian Cloud instances the Cloud ID is fetched and stored automatically.
    """
    # Always work with the Jira gateway URL, even if the caller passed the Confluence one.
    url = normalize_instance_url(ensure_service_gateway_url(url, "jira"))
    settings = get_settings()

    if not settings.export.enable_jira_enrichment:
        msg = "Jira API client was requested eventhough Jira enrichment is disabled."
        raise RuntimeWarning(msg)

    with _clients_lock:
        if url in _jira_clients:
            logger.debug("Jira client cache hit for %s", url)
            return _jira_clients[url]

    auth = settings.auth.get_jira_instance(url)
    if auth is None:
        raise AuthNotConfiguredError(url, "Jira")

    logger.debug("Creating new Jira client for %s", url)

    # Auto-fetch and store the Cloud ID for standard Atlassian Cloud instances
    if not auth.cloud_id and _is_standard_atlassian_cloud_url(url):
        cloud_id = _try_fetch_cloud_id(url)
        if cloud_id:
            logger.info("Auto-fetched Atlassian Cloud ID for %s — storing in config", url)
            set_setting_with_keys(["auth", "jira", url, "cloud_id"], cloud_id)
            settings = get_settings()

    auth = settings.auth.get_jira_instance(url) or auth
    sdk_url = _get_jira_sdk_url(url, auth)
    try:
        client = ApiClientFactory(settings.connection_config).create_jira(sdk_url, auth)
        logger.info("Connected to Jira at %s", sdk_url)
    except ConnectionError as e:
        logger.exception("[red bold]Jira authentication failed for %s.[/red bold]", url)
        raise AuthNotConfiguredError(url, "Jira") from e

    client.session.hooks["response"].append(_jira_auth_failure_hook)

    if settings.export.log_level == "DEBUG":
        client.session.hooks["response"].append(response_hook)

    with _clients_lock:
        _jira_clients[url] = client
    return client


def invalidate_confluence_client(url: str) -> None:
    """Remove a cached Confluence client so the next call creates a fresh one."""
    with _clients_lock:
        _confluence_clients.pop(normalize_instance_url(url), None)


def invalidate_jira_client(url: str) -> None:
    """Remove a cached Jira client so the next call creates a fresh one."""
    with _clients_lock:
        _jira_clients.pop(normalize_instance_url(url), None)


def handle_jira_auth_failure(url: str) -> None:
    """Handle a Jira authentication failure by invalidating the cached client and raising."""
    invalidate_jira_client(url)
    raise AuthNotConfiguredError(url, "Jira")
