"""Space export scope, homepage-aware ancestors and folder export."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pytest
from requests import HTTPError

from confluence_markdown_exporter.confluence import Descendant
from confluence_markdown_exporter.confluence import Folder
from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.confluence import Space
from confluence_markdown_exporter.confluence import _add_databases
from confluence_markdown_exporter.confluence import _link_target

if TYPE_CHECKING:
    from collections.abc import Callable
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


def _search(results: dict[str, list[Descendant]]) -> Callable[[str, str], list[Descendant]]:
    """Fake `_search_pages` that answers by the CQL content type."""

    def search(cql: str, _base_url: str) -> list[Descendant]:
        return results.get(cql.removeprefix("type=").split(" ", 1)[0], [])

    return search


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
            patch(f"{MODULE}._search_pages", side_effect=_search({"page": everything})) as search,
            patch(f"{MODULE}.settings") as s,
        ):
            s.export.only_homepage_descendants = False
            pages = _space().pages
        assert search.call_args_list == [
            call('type=page AND space="KEY"', BASE_URL),
            call('type=database AND space="KEY"', BASE_URL),
        ]
        assert [int(p.id) for p in pages] == [100, 2, 10]

    def test_opt_out_exports_space_without_homepage(self) -> None:
        root = Descendant.from_json(_page_json(10, "Root", []), BASE_URL)
        with (
            patch(f"{MODULE}._search_pages", side_effect=_search({"page": [root]})),
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
        assert search.call_args_list == [
            call("type=page AND ancestor=123", BASE_URL),
            call("type=database AND ancestor=123", BASE_URL),
        ]


class TestLinkTarget:
    """Link targets are fetched without bodies or attachments (issue #298)."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Iterator[None]:
        _link_target.cache_clear()
        yield
        _link_target.cache_clear()

    def test_fetches_only_ancestors_and_version(self) -> None:
        data = _page_json(5, "Target", [(100, "Home"), (2, "Parent")])
        data["_links"] = {"base": f"{BASE_URL}/wiki", "webui": "/spaces/KEY/pages/5/Target"}
        client = MagicMock()
        client.get_page_by_id.return_value = data
        with patch(f"{MODULE}.get_thread_confluence", return_value=client):
            target = _link_target(5, BASE_URL)
        client.get_page_by_id.assert_called_once_with(5, expand="ancestors,version")
        assert target is not None
        assert target.title == "Target"
        assert target.web_url == f"{BASE_URL}/wiki/spaces/KEY/pages/5/Target"
        assert [a.title for a in target.ancestors] == ["Parent"]

    def test_unreadable_page_returns_none(self) -> None:
        client = MagicMock()
        client.get_page_by_id.side_effect = ValueError("Expecting value: line 1 column 1")
        with patch(f"{MODULE}.get_thread_confluence", return_value=client):
            assert _link_target(5, BASE_URL) is None


@pytest.fixture
def path_settings() -> Iterator[MagicMock]:
    """Settings with a simple page path; the space homepage resolves to "Home"."""
    home = MagicMock(id=100, descendants=[], export_path="Home.md")
    home.title = "Home"
    with (
        patch(f"{MODULE}.Page.from_id", return_value=home),
        patch(f"{MODULE}.settings") as s,
    ):
        s.export.page_path = "{ancestor_titles}/{page_title}.md"
        s.export.page_path_if_parent = None
        yield s


@pytest.mark.usefixtures("path_settings")
class TestDatabases:
    """Confluence Cloud databases are exported as placeholder pages (issue #120)."""

    def test_homepage_tree_adds_databases_after_skipped_pages_warning(
        self, path_settings: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        child = Descendant.from_json(_page_json(2, "Child", [(100, "Home")]), BASE_URL)
        database = Descendant.from_json(_page_json(3, "Tasks", [(100, "Home")]), BASE_URL)
        Page.from_id(100, BASE_URL).descendants = [child]
        client = MagicMock()
        client.get.return_value = {"totalSize": 3}
        with (
            patch(f"{MODULE}.get_thread_confluence", return_value=client),
            patch(
                f"{MODULE}._search_pages", side_effect=_search({"database": [database]})
            ) as search,
        ):
            path_settings.export.only_homepage_descendants = True
            pages = _space().pages
        search.assert_called_once_with("type=database AND ancestor=100", BASE_URL)
        assert [int(p.id) for p in pages] == [100, 2, 3]
        # 3 pages in the space, 2 in the homepage tree: the database must not hide the third
        assert "1 page(s) outside the homepage tree" in caplog.text

    def test_folder_adds_databases(self) -> None:
        page = Descendant.from_json(_page_json(2, "Page", [(123, "Docs")]), BASE_URL)
        database = Descendant.from_json(_page_json(3, "Tasks", [(123, "Docs")]), BASE_URL)
        folder = Folder(base_url=BASE_URL, id=123, title="Docs")
        results = {"page": [page], "database": [database]}
        with patch(f"{MODULE}._search_pages", side_effect=_search(results)):
            assert [int(p.id) for p in folder.pages] == [2, 3]

    def test_page_with_descendants_adds_databases(self) -> None:
        root = MagicMock(id=100, base_url=BASE_URL, descendants=[], export_path="Home.md")
        database = Descendant.from_json(_page_json(3, "Tasks", [(100, "Home")]), BASE_URL)
        with (
            patch(
                f"{MODULE}._search_pages", side_effect=_search({"database": [database]})
            ) as search,
            patch(f"{MODULE}.export_pages") as export,
        ):
            Page.export_with_descendants(root)
        search.assert_called_once_with("type=database AND ancestor=100", BASE_URL)
        assert export.call_args.args[0] == [root, database]

    def test_database_with_same_path_as_a_page_is_skipped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        page = Descendant.from_json(_page_json(2, "Tasks", [(123, "Docs")]), BASE_URL)
        database = Descendant.from_json(_page_json(3, "Tasks", [(123, "Docs")]), BASE_URL)
        folder = Folder(base_url=BASE_URL, id=123, title="Docs")
        results = {"page": [page], "database": [database]}
        with patch(f"{MODULE}._search_pages", side_effect=_search(results)):
            assert [int(p.id) for p in folder.pages] == [2]
        assert "Skipping Confluence database 'Tasks'" in caplog.text

    def test_database_with_same_path_as_another_database_is_skipped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        first = Descendant.from_json(_page_json(3, "Tasks", [(123, "Docs")]), BASE_URL)
        second = Descendant.from_json(_page_json(4, "Tasks", [(123, "Docs")]), BASE_URL)
        folder = Folder(base_url=BASE_URL, id=123, title="Docs")
        with patch(f"{MODULE}._search_pages", side_effect=_search({"database": [first, second]})):
            assert [int(p.id) for p in folder.pages] == [3]
        assert "Skipping Confluence database 'Tasks' (id 4)" in caplog.text

    @pytest.mark.parametrize(
        "response",
        [
            HTTPError("400 Bad Request", response=MagicMock(status_code=400)),
            HTTPError("500 Server Error", response=MagicMock(status_code=500)),
            {"statusCode": 400, "message": "Unknown content type: database"},
        ],
        ids=["http-400", "http-500", "error-payload"],
    )
    def test_rejected_database_query_adds_nothing_quietly(
        self, response: object, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Server/DC has no databases; a rejected query must not affect pages or warn."""
        page = Descendant.from_json(_page_json(2, "Page", [(123, "Docs")]), BASE_URL)
        client = MagicMock()
        if isinstance(response, Exception):
            client.get.side_effect = response
        else:
            client.get.return_value = response
        with patch(f"{MODULE}.get_thread_confluence", return_value=client):
            pages = _add_databases([page], "ancestor=123", BASE_URL)
        assert pages == [page]
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestDatabasePlaceholder:
    WEB_URL = f"{BASE_URL}/wiki/spaces/KEY/database/3"

    def _database(self, title: str = "Tasks & <Ideas>") -> Page:
        data = {
            **_page_json(3, title, []),
            "type": "database",
            "body": {"view": {"value": ""}, "export_view": {"value": ""}},
            "_links": {"base": f"{BASE_URL}/wiki", "webui": "/spaces/KEY/database/3"},
        }
        with patch(f"{MODULE}.Attachment.from_page_id", return_value=[]):
            return Page.from_json(data, BASE_URL)

    def test_body_links_to_the_database(self) -> None:
        page = self._database()
        assert "Tasks &amp; &lt;Ideas&gt;" in page.body
        assert f'href="{self.WEB_URL}"' in page.body

    def test_placeholder_replaces_every_html_body(self) -> None:
        """The placeholder wins even if the API returns HTML for the database."""
        data = {
            **_page_json(3, "Tasks", []),
            "type": "database",
            "body": {"view": {"value": "<p>view</p>"}, "export_view": {"value": "<p>export</p>"}},
            "_links": {"base": f"{BASE_URL}/wiki", "webui": "/spaces/KEY/database/3"},
        }
        page = Page.from_json(data, BASE_URL)
        assert page.body == page.body_export
        assert f'href="{self.WEB_URL}"' in page.body

    def test_markdown_keeps_the_link_as_is(self) -> None:
        markdown = self._database("Tasks").markdown
        assert f"[Open Tasks in Confluence]({self.WEB_URL})" in markdown

    def test_from_id_loads_a_database_without_attachments(self) -> None:
        """Databases are read through v1 content, also when the v2 API is enabled."""
        data = {
            **_page_json(3, "Tasks", []),
            "type": "database",
            "_links": {"base": f"{BASE_URL}/wiki", "webui": "/spaces/KEY/database/3"},
        }
        client = MagicMock()
        client.get_page_by_id.return_value = data
        Page.from_id.cache_clear()
        try:
            with (
                patch(f"{MODULE}.get_thread_confluence", return_value=client),
                patch(f"{MODULE}.Attachment.from_page_id") as attachments,
                patch(f"{MODULE}.settings") as s,
            ):
                s.connection_config.use_v2_api = True
                page = Page.from_id(3, BASE_URL)
        finally:
            Page.from_id.cache_clear()
        attachments.assert_not_called()
        assert page.type == "database"
        assert page.attachments == []
        assert f'href="{self.WEB_URL}"' in page.body

    def test_export_warns_and_skips_comments(
        self, path_settings: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        page = self._database("Tasks")
        path_settings.export.log_level = "INFO"
        path_settings.export.comments_export = "all"
        with (
            patch.object(Page, "export_attachments", return_value={}),
            patch.object(Page, "export_markdown"),
            patch.object(Page, "export_comments_sidecar") as comments,
        ):
            page.export()
        comments.assert_not_called()
        assert "'Tasks' is a Confluence database" in caplog.text
