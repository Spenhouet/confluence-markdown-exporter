"""Space discovery for `Organization.from_url` (`cme orgs`)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.confluence import Organization

if TYPE_CHECKING:
    from collections.abc import Iterator

BASE_URL = "https://example.atlassian.net"
MODULE = "confluence_markdown_exporter.confluence"


def _space(key: str, space_type: str) -> dict:
    return {"key": key, "name": key, "type": space_type, "homepage": {"id": 1}}


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    Organization.from_url.cache_clear()
    yield
    Organization.from_url.cache_clear()


def _client(spaces: list[dict], page_size: int) -> MagicMock:
    """Fake client whose `get_all_spaces` serves `spaces` in pages of `page_size`."""
    client = MagicMock()

    def get_all_spaces(
        start: int = 0,
        limit: int = 50,
        space_type: str | None = None,
        **_kwargs: object,
    ) -> dict:
        matching = [s for s in spaces if space_type in (None, s["type"])]
        return {"results": matching[start : start + min(limit, page_size)]}

    client.get_all_spaces.side_effect = get_all_spaces
    return client


def test_from_url_includes_every_non_personal_space_type() -> None:
    """Collaboration and knowledge base spaces are exported, personal ones are not."""
    spaces = [
        _space("GLOB", "global"),
        _space("COLLAB", "collaboration"),
        _space("KB", "knowledge_base"),
        _space("~me", "personal"),
    ]
    with patch(f"{MODULE}.get_thread_confluence", return_value=_client(spaces, 50)):
        org = Organization.from_url(BASE_URL)

    assert [space.key for space in org.spaces] == ["GLOB", "COLLAB", "KB"]


def test_from_url_follows_pagination() -> None:
    """Spaces beyond the first page of the space list are not dropped."""
    spaces = [_space(f"S{i}", "global") for i in range(7)]
    client = _client(spaces, page_size=3)
    with patch(f"{MODULE}.get_thread_confluence", return_value=client):
        org = Organization.from_url(BASE_URL)

    assert [space.key for space in org.spaces] == [f"S{i}" for i in range(7)]
    assert [c.kwargs["start"] for c in client.get_all_spaces.call_args_list] == [0, 3, 6, 7]
