from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from requests import HTTPError
from requests.exceptions import ChunkedEncodingError
from requests.exceptions import ConnectionError as RequestConnectionError
from requests.exceptions import Timeout

from confluence_markdown_exporter import confluence

BASE_URL = "https://wiki.example.com"


@pytest.mark.parametrize("error_type", [ChunkedEncodingError, RequestConnectionError, Timeout])
@pytest.mark.parametrize("later_page", [False, True])
@patch("confluence_markdown_exporter.confluence.get_thread_confluence")
@patch("confluence_markdown_exporter.confluence.time.sleep")
@patch("confluence_markdown_exporter.confluence.Descendant.from_json")
def test_search_pages_retries_current_page(
    from_json: MagicMock,
    sleep: MagicMock,
    get_client: MagicMock,
    error_type: type[Exception],
    later_page: bool,
) -> None:
    client = MagicMock()
    responses = [
        error_type("response interrupted"),
        {"results": [{"id": "123"}]},
    ]
    next_path = "/rest/api/content/search?start=250"
    if later_page:
        responses.insert(0, {"results": [{"id": "122"}], "_links": {"next": next_path}})
    client.get.side_effect = responses
    get_client.return_value = client
    from_json.side_effect = lambda data, _base_url: data["id"]

    assert confluence._search_pages("type=page AND ancestor=1", BASE_URL) == (
        ["122", "123"] if later_page else ["123"]
    )

    assert client.get.call_count == (3 if later_page else 2)
    assert client.get.call_args_list[-1] == client.get.call_args_list[-2]
    assert client.get.call_args_list[-1].args[0] == (
        next_path if later_page else "rest/api/content/search"
    )
    assert client.get.call_args_list[0].kwargs["params"] == {
        "cql": "type=page AND ancestor=1",
        "expand": "ancestors,version",
        "limit": 250,
    }
    sleep.assert_called_once_with(1)
    assert from_json.call_count == (2 if later_page else 1)


@pytest.mark.parametrize("error_type", [ChunkedEncodingError, RequestConnectionError, Timeout])
@pytest.mark.parametrize("later_page", [False, True])
@patch("confluence_markdown_exporter.confluence.get_thread_confluence")
@patch("confluence_markdown_exporter.confluence.time.sleep")
def test_search_pages_raises_after_retries_instead_of_returning_partial_results(
    sleep: MagicMock,
    get_client: MagicMock,
    error_type: type[Exception],
    later_page: bool,
) -> None:
    client = MagicMock()
    responses = [error_type("response interrupted") for _ in range(3)]
    if later_page:
        responses.insert(0, {"results": [{"id": "122"}], "_links": {"next": "/next"}})
    client.get.side_effect = responses
    get_client.return_value = client

    with pytest.raises(error_type, match="interrupted"):
        confluence._search_pages("type=page AND ancestor=1", BASE_URL)

    assert client.get.call_count == (4 if later_page else 3)
    assert client.get.call_args_list[-3:] == [client.get.call_args_list[-1]] * 3
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]


@pytest.mark.parametrize("status_code", [404, 500])
@patch("confluence_markdown_exporter.confluence.get_thread_confluence")
def test_search_pages_propagates_http_errors(get_client: MagicMock, status_code: int) -> None:
    error = HTTPError(f"HTTP {status_code}")
    error.response = MagicMock(status_code=status_code)
    client = MagicMock()
    client.get.side_effect = error
    get_client.return_value = client

    with pytest.raises(HTTPError, match=str(status_code)):
        confluence._search_pages("type=page AND ancestor=1", BASE_URL)

    client.get.assert_called_once()


@patch("confluence_markdown_exporter.confluence.get_thread_confluence")
def test_search_pages_returns_successful_empty_results(get_client: MagicMock) -> None:
    get_client.return_value.get.return_value = {"results": []}

    assert confluence._search_pages("type=page AND ancestor=1", BASE_URL) == []

    get_client.return_value.get.assert_called_once()
