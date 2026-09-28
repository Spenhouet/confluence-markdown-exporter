"""Space export scope, homepage-aware ancestors and folder export."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.confluence import Descendant
from confluence_markdown_exporter.confluence import Folder
from confluence_markdown_exporter.confluence import Space

if TYPE_CHECKING:
    from collections.abc import Iterator

BASE_URL = "https://example.atlassian.net"
MODULE = "confluence_markdown_exporter.confluence"


def _space(homepage: int | None = 100) -> Space:
    return Space(base_url=BASE_URL, key="KEY", name="Space", description="", homepage=homepage)


def _page_json(page_id: int, title: str, ancestors: list[tuple[int, str]]) -> dict:
    return {
        "id": str(page_id),
        "title": title,
        "_expandable": {"space": "/rest/api/space/KEY"},
        "ancestors": [
            {"id": str(aid), "title": atitle, "_expandable": {"space": "/rest/api/space/KEY"}}
            for aid, atitle in ancestors
        ],
        "version": {},
    }


@pytest.fixture(autouse=True)
def _space_from_key() -> Iterator[None]:
    with patch(f"{MODULE}.Space.from_key", return_value=_space()):
        yield


class TestHomepageAwareAncestors:
    def test_homepage_is_dropped_from_ancestors(self) -> None:
        d = Descendant.from_json(_page_json(3, "Child", [(100, "Home"), (2, "Parent")]), BASE_URL)
        assert [a.title for a in d.ancestors] == ["Parent"]

    def test_page_under_second_root_keeps_its_root(self) -> None:
        d = Descendant.from_json(_page_json(11, "Leaf", [(10, "Other Root")]), BASE_URL)
        assert [a.title for a in d.ancestors] == ["Other Root"]


class TestSpacePages:
    @staticmethod
    def _homepage(descendants: list[Descendant]) -> MagicMock:
        homepage = MagicMock()
        homepage.id = 100
        homepage.descendants = descendants
        return homepage

    def test_default_exports_homepage_tree_and_warns_about_the_rest(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        child = Descendant.from_json(_page_json(2, "Child", [(100, "Home")]), BASE_URL)
        client = MagicMock()
        client.get.return_value = {"totalSize": 4}
        with (
            patch(f"{MODULE}.Page.from_id", return_value=self._homepage([child])),
            patch(f"{MODULE}.get_thread_confluence", return_value=client),
            patch(f"{MODULE}.settings") as s,
        ):
            s.export.only_homepage_descendants = True
            pages = _space().pages
        assert [int(p.id) for p in pages] == [100, 2]
        assert "2 page(s) outside the homepage tree" in caplog.text

    def test_opt_out_adds_pages_outside_the_homepage_tree(self) -> None:
        child = Descendant.from_json(_page_json(2, "Child", [(100, "Home")]), BASE_URL)
        everything = [
            child,
            Descendant.from_json(_page_json(10, "Other Root", []), BASE_URL),
        ]
        with (
            patch(f"{MODULE}.Page.from_id", return_value=self._homepage([child])),
            patch(f"{MODULE}._search_pages", return_value=everything) as search,
            patch(f"{MODULE}.settings") as s,
        ):
            s.export.only_homepage_descendants = False
            pages = _space().pages
        search.assert_called_once_with('type=page AND space="KEY"', BASE_URL)
        assert [int(p.id) for p in pages] == [100, 2, 10]

    def test_opt_out_exports_space_without_homepage(self) -> None:
        root = Descendant.from_json(_page_json(10, "Root", []), BASE_URL)
        with (
            patch(f"{MODULE}._search_pages", return_value=[root]),
            patch(f"{MODULE}.settings") as s,
        ):
            s.export.only_homepage_descendants = False
            pages = _space(homepage=None).pages
        assert [int(p.id) for p in pages] == [10]


class TestFolder:
    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Iterator[None]:
        Folder.from_id.cache_clear()
        yield
        Folder.from_id.cache_clear()

    @pytest.mark.parametrize(
        "url",
        [
            f"{BASE_URL}/wiki/spaces/KEY/folder/123",
            f"{BASE_URL}/wiki/spaces/KEY/folders/123",
            f"{BASE_URL}/wiki/spaces/KEY/folder/123?atlOrigin=abc",
        ],
    )
    def test_from_url(self, url: str) -> None:
        client = MagicMock()
        client.get.return_value = {"id": "123", "type": "folder", "title": "Docs"}
        with (
            patch(f"{MODULE}.get_confluence_instance"),
            patch(f"{MODULE}.get_thread_confluence", return_value=client),
        ):
            folder = Folder.from_url(url)
        assert (folder.id, folder.title) == (123, "Docs")

    def test_from_url_rejects_other_urls(self) -> None:
        with (
            patch(f"{MODULE}.get_confluence_instance"),
            pytest.raises(ValueError, match="Could not parse folder URL"),
        ):
            Folder.from_url(f"{BASE_URL}/wiki/spaces/KEY/pages/123")

    def test_from_id_rejects_pages(self) -> None:
        client = MagicMock()
        client.get.return_value = {"id": "123", "type": "page", "title": "A page"}
        with (
            patch(f"{MODULE}.get_thread_confluence", return_value=client),
            pytest.raises(ValueError, match="not a folder"),
        ):
            Folder.from_id(123, BASE_URL)

    def test_pages_searches_descendants(self) -> None:
        folder = Folder(base_url=BASE_URL, id=123, title="Docs")
        with patch(f"{MODULE}._search_pages", return_value=[]) as search:
            assert folder.pages == []
        search.assert_called_once_with("type=page AND ancestor=123", BASE_URL)
