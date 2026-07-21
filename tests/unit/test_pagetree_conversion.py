"""Unit tests for the content-tree / page-tree macro conversion."""

from collections.abc import Callable
from unittest.mock import MagicMock
from unittest.mock import patch

from bs4 import BeautifulSoup

from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry

BASE_URL = "https://example.atlassian.net/wiki"


def _ancestor(page_id: int) -> MagicMock:
    anc = MagicMock()
    anc.id = page_id
    return anc


def _descendant(page_id: int, title: str, ancestors: list[int]) -> MagicMock:
    desc = MagicMock()
    desc.id = page_id
    desc.title = title
    desc.ancestors = [_ancestor(a) for a in ancestors]
    return desc


def _make_page(
    editor2: str,
    descendants: list[MagicMock] | None = None,
    homepage: int | None = None,
) -> MagicMock:
    page = MagicMock(spec=Page)
    page.id = 100
    page.title = "Root Page"
    page.html = "<h1>Root Page</h1>"
    page.labels = []
    page.ancestors = []
    page.attachments = []
    page.editor2 = editor2
    page.body_storage = ""
    page.base_url = BASE_URL
    page.descendants = descendants or []
    page.space = MagicMock()
    page.space.key = "TEST"
    page.space.homepage = homepage
    return page


def _content_tree_editor2(root: str = "@self", depth: str | None = None) -> str:
    """Build a page-tree macro in the real storage format.

    The `root` value is carried in a nested `ri:page` `ri:content-title` attribute, as
    Confluence actually stores it (verified against a live page), not as element text.
    """
    depth_param = f'<ac:parameter ac:name="startDepth">{depth}</ac:parameter>' if depth else ""
    return (
        '<ac:structured-macro ac:name="content-tree" ac:macro-id="ct-1">'
        '<ac:parameter ac:name="root">'
        f'<ac:link><ri:page ri:content-title="{root}" /></ac:link>'
        "</ac:parameter>"
        f"{depth_param}"
        "</ac:structured-macro>"
    )


CT_DIV = '<div data-macro-name="content-tree" data-macro-id="ct-1"></div>'


def _linked_page(page_id: int, title: str) -> MagicMock:
    page = MagicMock(spec=Page)
    page.id = page_id
    page.title = title
    return page


def _from_id_factory(titles: dict[int, str]) -> Callable[[int, str], MagicMock]:
    def _from_id(page_id: int, _base_url: str) -> MagicMock:
        return _linked_page(page_id, titles.get(page_id, "Unknown"))

    return _from_id


def _converter(mock_settings: MagicMock, page: MagicMock) -> Page.Converter:
    PageTitleRegistry.reset()
    mock_settings.export.include_document_title = False
    mock_settings.export.page_breadcrumbs = False
    mock_settings.export.page_href = "wiki"
    return Page.Converter(page)


TITLES = {1: "Child A", 2: "Child B", 3: "Grandchild B1"}


def _el() -> BeautifulSoup:
    return BeautifulSoup(CT_DIV, "html.parser").find("div")


@patch("confluence_markdown_exporter.confluence.Page.from_id")
@patch("confluence_markdown_exporter.confluence.settings")
def test_content_tree_renders_nested_list(
    mock_settings: MagicMock, mock_from_id: MagicMock
) -> None:
    mock_from_id.side_effect = _from_id_factory(TITLES)
    descendants = [
        _descendant(1, "Child A", [100]),
        _descendant(2, "Child B", [100]),
        _descendant(3, "Grandchild B1", [100, 2]),
    ]
    converter = _converter(mock_settings, _make_page(_content_tree_editor2(), descendants))

    result = converter.convert_pagetree(_el(), "", [])

    assert result == "\n- [[Child A]]\n- [[Child B]]\n  - [[Grandchild B1]]\n\n"


@patch("confluence_markdown_exporter.confluence.Page.from_id")
@patch("confluence_markdown_exporter.confluence.settings")
def test_content_tree_depth_limits_nesting(
    mock_settings: MagicMock, mock_from_id: MagicMock
) -> None:
    mock_from_id.side_effect = _from_id_factory(TITLES)
    descendants = [
        _descendant(1, "Child A", [100]),
        _descendant(2, "Child B", [100]),
        _descendant(3, "Grandchild B1", [100, 2]),
    ]
    converter = _converter(mock_settings, _make_page(_content_tree_editor2(depth="1"), descendants))

    result = converter.convert_pagetree(_el(), "", [])

    assert result == "\n- [[Child A]]\n- [[Child B]]\n\n"
    assert "Grandchild" not in result


@patch("confluence_markdown_exporter.confluence.Page.from_id")
@patch("confluence_markdown_exporter.confluence.settings")
def test_content_tree_no_descendants_returns_empty(
    mock_settings: MagicMock, mock_from_id: MagicMock
) -> None:
    mock_from_id.side_effect = _from_id_factory(TITLES)
    converter = _converter(mock_settings, _make_page(_content_tree_editor2(), []))

    assert converter.convert_pagetree(_el(), "", []) == ""


@patch("confluence_markdown_exporter.confluence.Page.from_id")
@patch("confluence_markdown_exporter.confluence.settings")
def test_content_tree_root_home_resolves_via_homepage(
    mock_settings: MagicMock, mock_from_id: MagicMock
) -> None:
    homepage_page = _make_page("", descendants=[_descendant(1, "Child A", [200])], homepage=None)
    homepage_page.id = 200

    def _from_id(page_id: int, _base_url: str) -> MagicMock:
        if page_id == 200:
            return homepage_page
        return _linked_page(page_id, TITLES.get(page_id, "Unknown"))

    mock_from_id.side_effect = _from_id
    page = _make_page(_content_tree_editor2(root="@home"), descendants=[], homepage=200)
    converter = _converter(mock_settings, page)

    result = converter.convert_pagetree(_el(), "", [])

    assert result == "\n- [[Child A]]\n\n"


@patch("confluence_markdown_exporter.confluence.settings")
def test_content_tree_root_home_without_homepage_returns_empty(
    mock_settings: MagicMock,
) -> None:
    page = _make_page(_content_tree_editor2(root="@home"), descendants=[], homepage=None)
    converter = _converter(mock_settings, page)

    assert converter.convert_pagetree(_el(), "", []) == ""


@patch("confluence_markdown_exporter.confluence.get_thread_confluence")
@patch("confluence_markdown_exporter.confluence.settings")
def test_content_tree_unresolvable_title_root_returns_empty(
    mock_settings: MagicMock, mock_client_factory: MagicMock
) -> None:
    client = MagicMock()
    client.get.return_value = {"results": []}
    mock_client_factory.return_value = client

    page = _make_page(_content_tree_editor2(root="Missing Page"), descendants=[])
    converter = _converter(mock_settings, page)

    assert converter.convert_pagetree(_el(), "", []) == ""


@patch("confluence_markdown_exporter.confluence.Page.from_id")
@patch("confluence_markdown_exporter.confluence.settings")
def test_content_tree_dispatched_via_convert_div(
    mock_settings: MagicMock, mock_from_id: MagicMock
) -> None:
    mock_from_id.side_effect = _from_id_factory(TITLES)
    descendants = [_descendant(1, "Child A", [100])]
    converter = _converter(mock_settings, _make_page(_content_tree_editor2(), descendants))

    result = converter.convert_div(_el(), "", [])

    assert result == "\n- [[Child A]]\n\n"


@patch("confluence_markdown_exporter.confluence.Page.from_id")
@patch("confluence_markdown_exporter.confluence.settings")
def test_content_tree_plaintext_root_falls_back_to_text(
    mock_settings: MagicMock, mock_from_id: MagicMock
) -> None:
    # Some macro variants store `root` as plain element text instead of an ri:page link.
    mock_from_id.side_effect = _from_id_factory(TITLES)
    editor2 = (
        '<ac:structured-macro ac:name="content-tree" ac:macro-id="ct-1">'
        '<ac:parameter ac:name="root">@self</ac:parameter>'
        "</ac:structured-macro>"
    )
    descendants = [_descendant(1, "Child A", [100])]
    converter = _converter(mock_settings, _make_page(editor2, descendants))

    result = converter.convert_pagetree(_el(), "", [])

    assert result == "\n- [[Child A]]\n\n"
