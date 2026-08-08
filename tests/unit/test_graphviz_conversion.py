"""Unit tests for Graphviz (`graphviz` / `digraph` macro) diagram conversion."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from bs4 import Tag

from confluence_markdown_exporter.confluence import Page


def _make_page(**overrides: object) -> MagicMock:
    page = MagicMock(spec=Page)
    page.id = 12345
    page.title = "Test Page"
    page.html = "<h1>Test Page</h1>"
    page.labels = []
    page.ancestors = []
    page.attachments = []
    page.editor2 = ""
    page.body_storage = ""
    for key, value in overrides.items():
        setattr(page, key, value)
    return page


def _storage_macro(name: str, body: str, params: str = "") -> str:
    return (
        f'<ac:structured-macro ac:name="{name}">'
        f"{params}"
        f"<ac:plain-text-body><![CDATA[{body}]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )


def _el(html: str, tag: str) -> Tag:
    """Return the first `tag` in `html`, failing the test if the fixture has no such tag."""
    element = BeautifulSoup(html, "html.parser").find(tag)
    assert isinstance(element, Tag), f"fixture HTML has no <{tag}>: {html}"
    return element


class TestGraphvizMacroConversion:
    """Conversion of the `graphviz` macro, whose body is already complete DOT."""

    @pytest.fixture(autouse=True)
    def _settings(self):  # noqa: ANN202
        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.include_document_title = False
            mock_settings.export.page_breadcrumbs = False
            mock_settings.export.convert_text_highlights = False
            mock_settings.export.convert_font_colors = False
            yield mock_settings

    def test_graphviz_from_storage_is_emitted_verbatim(self) -> None:
        """A `graphviz` body is complete DOT and must not be re-wrapped."""
        page = _make_page(
            body_storage=_storage_macro("graphviz", "digraph G {\n  a -> b;\n}"),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="graphviz"></div>', "div"), "", []
        )

        assert result == "\n```dot\ndigraph G {\n  a -> b;\n}\n```\n\n"

    def test_graphviz_from_editor2_by_macro_id(self) -> None:
        """Cloud pages resolve the macro through editor2 XML by macro-id."""
        page = _make_page(
            editor2=(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<ac:structured-macro ac:name="graphviz" ac:macro-id="gv-1">'
                "<ac:plain-text-body><![CDATA[digraph G { x -> y }]]></ac:plain-text-body>"
                "</ac:structured-macro>"
            ),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="graphviz" data-macro-id="gv-1"></div>', "div"), "", []
        )

        assert "```dot" in result
        assert "digraph G { x -> y }" in result

    def test_graphviz_editor2_miss_falls_back_to_storage(self) -> None:
        """An unmatched macro-id falls through to the body.storage lookup."""
        page = _make_page(
            editor2=(
                '<ac:structured-macro ac:name="graphviz" ac:macro-id="other-id">'
                "<ac:plain-text-body><![CDATA[digraph G { wrong }]]></ac:plain-text-body>"
                "</ac:structured-macro>"
            ),
            body_storage=_storage_macro("graphviz", "digraph G { correct }"),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="graphviz" data-macro-id="missing"></div>', "div"), "", []
        )

        assert "correct" in result
        assert "wrong" not in result

    def test_undirected_graph_body_kept_as_is(self) -> None:
        """An undirected graph written into the `graphviz` macro survives untouched."""
        page = _make_page(body_storage=_storage_macro("graphviz", "graph G {\n  a -- b;\n}"))
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="graphviz"></div>', "div"), "", []
        )

        assert "graph G {\n  a -- b;\n}" in result
        assert "digraph" not in result


class TestDigraphMacroConversion:
    """Conversion of the `digraph` macro, whose body holds only DOT statements."""

    @pytest.fixture(autouse=True)
    def _settings(self):  # noqa: ANN202
        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.include_document_title = False
            mock_settings.export.convert_text_highlights = False
            mock_settings.export.convert_font_colors = False
            yield mock_settings

    def test_digraph_body_is_wrapped_in_graph_header(self) -> None:
        """The plugin-supplied `digraph G { ... }` header has to be reconstructed."""
        page = _make_page(body_storage=_storage_macro("digraph", "A -> B -> C"))
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert result == "\n```dot\ndigraph G {\nA -> B -> C\n}\n```\n\n"

    def test_digraph_name_parameter_is_used(self) -> None:
        """The `name` parameter becomes the DOT graph name."""
        page = _make_page(
            body_storage=_storage_macro(
                "digraph",
                "A -> B",
                params='<ac:parameter ac:name="name">MyGraph</ac:parameter>',
            ),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert "digraph MyGraph {" in result

    def test_digraph_name_with_spaces_is_quoted(self) -> None:
        """A graph name that is not a bare DOT ID must be quoted."""
        page = _make_page(
            body_storage=_storage_macro(
                "digraph",
                "A -> B",
                params='<ac:parameter ac:name="name">My Graph</ac:parameter>',
            ),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert 'digraph "My Graph" {' in result

    def test_digraph_attributes_parameter_is_prepended(self) -> None:
        """Graph attributes held in the `attributes` parameter are not dropped."""
        page = _make_page(
            body_storage=_storage_macro(
                "digraph",
                "A -> B",
                params='<ac:parameter ac:name="attributes">rankdir=LR;</ac:parameter>',
            ),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert result == "\n```dot\ndigraph G {\nrankdir=LR;\nA -> B\n}\n```\n\n"

    def test_digraph_body_that_already_has_header_is_not_double_wrapped(self) -> None:
        """Authors sometimes paste a full document into the `digraph` macro."""
        page = _make_page(body_storage=_storage_macro("digraph", "digraph G {\n  A -> B;\n}"))
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert result.count("digraph G {") == 1

    @pytest.mark.parametrize(
        "comment",
        ["// my graph", "# my graph", "/* my graph */", "// first\n// second"],
    )
    def test_leading_comment_does_not_defeat_the_header_check(self, comment: str) -> None:
        """A pasted document opening with a comment must not be wrapped again.

        Nesting `digraph` inside `digraph` is a DOT syntax error — only `subgraph` nests.
        """
        page = _make_page(
            body_storage=_storage_macro("digraph", f"{comment}\ndigraph G {{\n  A -> B;\n}}"),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert result.count("digraph G {") == 1

    @pytest.mark.parametrize("name", ["graph", "digraph", "node", "edge", "subgraph", "strict"])
    def test_reserved_word_graph_name_is_quoted(self, name: str) -> None:
        """`digraph graph { ... }` is a DOT syntax error, so keywords must be quoted."""
        page = _make_page(
            body_storage=_storage_macro(
                "digraph",
                "A -> B",
                params=f'<ac:parameter ac:name="name">{name}</ac:parameter>',
            ),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert f'digraph "{name}" {{' in result

    def test_comma_separated_attributes_become_statements(self) -> None:
        """A comma is not a valid statement separator at graph level."""
        page = _make_page(
            body_storage=_storage_macro(
                "digraph",
                "A -> B",
                params=('<ac:parameter ac:name="attributes">rankdir=LR, size="8,5"</ac:parameter>'),
            ),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        # The comma inside the quoted `size` value has to survive.
        assert 'rankdir=LR; size="8,5"' in result

    def test_semicolon_attributes_pass_through_unchanged(self) -> None:
        """A value that already reads as statements is left alone."""
        page = _make_page(
            body_storage=_storage_macro(
                "digraph",
                "A -> B",
                params=(
                    '<ac:parameter ac:name="attributes">rankdir=LR;\nbgcolor=white;</ac:parameter>'
                ),
            ),
        )
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert "rankdir=LR;\nbgcolor=white;\nA -> B" in result

    def test_multiline_body_is_not_reindented(self) -> None:
        """Bodies are emitted verbatim so line-continued strings stay intact."""
        body = 'A [label="first\\\nsecond"]\nA -> B'
        page = _make_page(body_storage=_storage_macro("digraph", body))
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert body in result


class TestGraphvizPositionalMatching:
    """Server / Data Center pages match macros by position, per macro name."""

    @pytest.fixture(autouse=True)
    def _settings(self):  # noqa: ANN202
        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.include_document_title = False
            mock_settings.export.convert_text_highlights = False
            mock_settings.export.convert_font_colors = False
            yield mock_settings

    def test_multiple_digraphs_match_in_order(self) -> None:
        page = _make_page(
            body_storage=(
                _storage_macro("digraph", "A -> B")
                + "<p>text between</p>"
                + _storage_macro("digraph", "C -> D")
            ),
        )
        converter = Page.Converter(page)

        first = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )
        second = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert "A -> B" in first
        assert "C -> D" in second

    def test_macro_names_have_independent_positions(self) -> None:
        """A `graphviz` macro must not consume the `digraph` macro's slot."""
        page = _make_page(
            body_storage=(
                _storage_macro("digraph", "A -> B")
                + _storage_macro("graphviz", "digraph Full { C -> D }")
            ),
        )
        converter = Page.Converter(page)

        graphviz_result = converter.convert_graphviz(
            _el('<div data-macro-name="graphviz"></div>', "div"), "", []
        )
        digraph_result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert "digraph Full { C -> D }" in graphviz_result
        assert "digraph G {\nA -> B\n}" in digraph_result

    def test_editor2_hit_still_advances_the_storage_position(self) -> None:
        """A diagram resolved through editor2 must not leave its storage slot unconsumed.

        Otherwise the next diagram falls back to slot 0 and silently renders the first
        diagram's source.
        """
        page = _make_page(
            editor2=(
                '<ac:structured-macro ac:name="digraph" ac:macro-id="first">'
                "<ac:plain-text-body><![CDATA[FROM -> EDITOR2]]></ac:plain-text-body>"
                "</ac:structured-macro>"
            ),
            body_storage=(
                _storage_macro("digraph", "FIRST -> ONE")
                + _storage_macro("digraph", "SECOND -> TWO")
            ),
        )
        converter = Page.Converter(page)

        first = converter.convert_graphviz(
            _el('<div data-macro-name="digraph" data-macro-id="first"></div>', "div"), "", []
        )
        # No macro-id, so this one has to come from storage — and from slot 1, not slot 0.
        second = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert "FROM -> EDITOR2" in first
        assert "SECOND -> TWO" in second
        assert "FIRST -> ONE" not in second

    def test_graphviz_does_not_consume_plantuml_slot(self) -> None:
        """Positional state is shared machinery — macro types must stay independent."""
        page = _make_page(
            body_storage=(
                _storage_macro("plantuml", "@startuml\nAlice -> Bob\n@enduml")
                + _storage_macro("digraph", "A -> B")
            ),
        )
        converter = Page.Converter(page)

        graphviz_result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )
        plantuml_result = converter.convert_plantuml(
            _el('<div data-macro-name="plantuml"></div>', "div"), "", []
        )

        assert "A -> B" in graphviz_result
        assert "Alice -> Bob" in plantuml_result


class TestGraphvizDispatch:
    """The converter reaches `convert_graphviz` from both div and span macro output."""

    @pytest.fixture(autouse=True)
    def _settings(self):  # noqa: ANN202
        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.include_document_title = False
            mock_settings.export.page_breadcrumbs = False
            mock_settings.export.convert_text_highlights = False
            mock_settings.export.convert_font_colors = False
            mock_settings.export.convert_status_badges = False
            yield mock_settings

    def test_full_page_conversion(self) -> None:
        """Both macros resolve, in order, through the whole conversion pipeline."""
        page = _make_page(
            body_storage=(
                _storage_macro(
                    "digraph",
                    "A -> B",
                    params='<ac:parameter ac:name="attributes">rankdir=LR;</ac:parameter>',
                )
                + _storage_macro("graphviz", "digraph Full {\n  X -> Y;\n}")
            ),
        )
        html = (
            "<p>Before</p>"
            '<div class="conf-macro output-block" data-hasbody="true" data-macro-name="digraph">'
            '<img src="/download/attachments/1/graph.png" alt="digraph"/></div>'
            "<p>Between</p>"
            '<div class="conf-macro output-block" data-hasbody="true" data-macro-name="graphviz">'
            '<img src="/download/attachments/1/graph2.png"/></div>'
        )
        page.html = html

        result = Page.Converter(page).convert(html)

        assert "digraph G {\nrankdir=LR;\nA -> B\n}" in result
        assert "digraph Full {\n  X -> Y;\n}" in result
        # The rendered preview images the macros produce are replaced, not kept alongside.
        assert "graph.png" not in result
        assert "graph2.png" not in result

    @pytest.mark.parametrize("macro_name", ["graphviz", "digraph"])
    def test_convert_div_dispatches(self, macro_name: str) -> None:
        page = _make_page(body_storage=_storage_macro(macro_name, "digraph G { A -> B }"))
        converter = Page.Converter(page)

        html = (
            f'<div class="conf-macro output-block" data-hasbody="true" '
            f'data-macro-name="{macro_name}"><img src="graph.png"/></div>'
        )
        result = converter.convert_div(_el(html, "div"), "", [])

        assert "```dot" in result
        assert "A -> B" in result

    @pytest.mark.parametrize("macro_name", ["graphviz", "digraph"])
    def test_convert_span_dispatches(self, macro_name: str) -> None:
        page = _make_page(body_storage=_storage_macro(macro_name, "digraph G { A -> B }"))
        converter = Page.Converter(page)

        html = (
            f'<span class="conf-macro output-inline" data-hasbody="true" '
            f'data-macro-name="{macro_name}"><img src="graph.png"/></span>'
        )
        result = converter.convert_span(_el(html, "span"), "", [])

        assert "```dot" in result
        assert "A -> B" in result

    def test_missing_source_emits_comment(self) -> None:
        converter = Page.Converter(_make_page())

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert "<!-- Graphviz diagram" in result
        assert "source not found" in result

    def test_empty_body_emits_comment(self) -> None:
        page = _make_page(body_storage=_storage_macro("digraph", ""))
        converter = Page.Converter(page)

        result = converter.convert_graphviz(
            _el('<div data-macro-name="digraph"></div>', "div"), "", []
        )

        assert "source not found" in result


class TestDotCodeBlockDetection:
    """Auto-detection of DOT source in plain `<pre>` code blocks."""

    @pytest.fixture(autouse=True)
    def _settings(self):  # noqa: ANN202
        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.include_document_title = False
            yield mock_settings

    @pytest.mark.parametrize(
        "text",
        [
            "digraph G {\n  A -> B;\n}",
            "digraph {\n  A -> B;\n}",
            "strict digraph G {\n  A -> B;\n}",
            "graph G {\n  A -- B;\n}",
            "  DiGraph Foo {\n  A -> B;\n}",
            "digraph{A->B}",
            'digraph "my graph" {\n  A -> B;\n}',
        ],
    )
    def test_dot_source_gets_dot_fence(self, text: str) -> None:
        converter = Page.Converter(_make_page())

        result = converter.convert_pre(_el("<pre></pre>", "pre"), text, [])

        assert "```dot" in result

    @pytest.mark.parametrize(
        "text",
        [
            "// a comment\ndigraph G {\n  A -> B;\n}",
            "/* a comment */\ndigraph G {\n  A -> B;\n}",
            "# a comment\ndigraph G {\n  A -> B;\n}",
        ],
    )
    def test_leading_comments_are_skipped(self, text: str) -> None:
        converter = Page.Converter(_make_page())

        result = converter.convert_pre(_el("<pre></pre>", "pre"), text, [])

        assert "```dot" in result

    @pytest.mark.parametrize(
        "text",
        [
            "graph TD\n  A-->B",
            "graph LR;\n  A-->B",
            "flowchart TD\n  A-->B",
        ],
    )
    def test_mermaid_flowchart_is_not_detected_as_dot(self, text: str) -> None:
        """Mermaid's `graph TD` has no brace on the header line — it must not match."""
        converter = Page.Converter(_make_page())

        result = converter.convert_pre(_el("<pre></pre>", "pre"), text, [])

        assert "```dot" not in result

    @pytest.mark.parametrize(
        "text",
        [
            "graph = {\n    'a': ['b'],\n}",
            "digraph = {}",
            "graph: Dict[str, int] = {}",
            "const graph = { a: 1 };",
            "subgraph cluster_0 {\n}",
        ],
    )
    def test_code_declaring_a_graph_variable_is_not_detected_as_dot(self, text: str) -> None:
        """DOT allows only an optional ID between the keyword and the brace.

        A wider gap would swallow ordinary code that happens to assign a variable
        named `graph` or `digraph`.
        """
        converter = Page.Converter(_make_page())

        result = converter.convert_pre(_el("<pre></pre>", "pre"), text, [])

        assert "```dot" not in result

    def test_declared_language_wins_over_dot_detection(self) -> None:
        """A declared brush language is stronger evidence than a `graph` keyword."""
        converter = Page.Converter(_make_page())

        html = '<pre data-syntaxhighlighter-params="brush: java; gutter: false"></pre>'
        result = converter.convert_pre(_el(html, "pre"), "graph G {\n  int x = 1;\n}", [])

        assert "```java" in result
        assert "```dot" not in result

    def test_startuml_still_wins(self) -> None:
        converter = Page.Converter(_make_page())

        result = converter.convert_pre(
            _el("<pre></pre>", "pre"), "@startuml\ndigraph G {}\n@enduml", []
        )

        assert "```plantuml" in result
        assert "```dot" not in result

    def test_unrelated_code_keeps_empty_language(self) -> None:
        converter = Page.Converter(_make_page())

        result = converter.convert_pre(_el("<pre></pre>", "pre"), "print('hello')", [])

        assert "```dot" not in result
        assert result.startswith("\n\n```\n")
