"""Unit tests for `plantumlcloud` diagrams that body.view renders as bare placeholders.

Confluence Cloud stopped rendering the PlantUML app's macros with any macro
attributes. body.view now carries only an attribute-less text `<div>`:

- the classic Connect macro (`ac:structured-macro ac:name="plantumlcloud"`) renders
  as `<div>PlantUML Diagram</div>`;
- the Forge version of the app (an `ac:adf-extension` whose extension key ends with
  `/static/plantumlcloud`) renders as `<div>We don't have a way to export this
  macro.</div>`.

The diagram source is still in body.storage. The placeholders are matched to it by
the `local-id` of the neighbouring element, which both representations carry.
"""

import base64
import logging
import zlib
from unittest.mock import MagicMock
from unittest.mock import patch
from urllib.parse import quote

import pytest

from confluence_markdown_exporter.confluence import Page

UML_A = "@startuml\nAlice -> Bob: Hello\n@enduml"
UML_B = "@startuml\nBob -> Carol: Second\n@enduml"
UML_C = "@startjson\n{}\n@endjson"
UML_OLD = "@startuml\nStale -> Revision: Old\n@enduml"

CLASSIC_TEXT = "PlantUML Diagram"
FORGE_TEXT = "We don't have a way to export this macro."
PLANTUML_KEY = "85516c62-app/2c435852-env/static/plantumlcloud"
DRAWIO_KEY = "1afdce52-app/92d899e8-env/static/drawio"
MARKER = "<!-- PlantUML diagram (source not found) -->"


def encode_data(uml: str, *, compressed: bool = True) -> str:
    payload = quote(uml).encode()
    if compressed:
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        payload = compressor.compress(payload) + compressor.flush()
    return base64.b64encode(payload).decode()


def classic_macro(uml: str, macro_id: str) -> str:
    """A classic `plantumlcloud` macro as it appears in body.storage."""
    return (
        f'<ac:structured-macro ac:name="plantumlcloud" ac:schema-version="1" '
        f'data-layout="default" ac:local-id="local-{macro_id}" ac:macro-id="{macro_id}">'
        '<ac:parameter ac:name="filename">diagram.svg</ac:parameter>'
        f'<ac:parameter ac:name="data">{encode_data(uml)}</ac:parameter>'
        '<ac:parameter ac:name="compressed">true</ac:parameter>'
        "</ac:structured-macro>"
    )


def _forge_node(key: str, local_id: str, guest: str, macro_params: str) -> str:
    return (
        '<ac:adf-node type="extension">'
        f'<ac:adf-attribute key="extension-key">{key}</ac:adf-attribute>'
        '<ac:adf-attribute key="extension-type">com.atlassian.ecosystem</ac:adf-attribute>'
        '<ac:adf-attribute key="parameters">'
        '<ac:adf-parameter key="extension-title">PlantUML Diagram</ac:adf-parameter>'
        f'<ac:adf-parameter key="local-id">{local_id}</ac:adf-parameter>'
        f'<ac:adf-parameter key="guest-params">{guest}</ac:adf-parameter>'
        f'<ac:adf-parameter key="macro-params">{macro_params}</ac:adf-parameter>'
        "</ac:adf-attribute>"
        f'<ac:adf-attribute key="local-id">node-{local_id}</ac:adf-attribute>'
        "</ac:adf-node>"
    )


def forge_extension(
    uml: str | None,
    local_id: str,
    *,
    key: str = PLANTUML_KEY,
    macro_params_uml: str | None = UML_OLD,
    compressed: str | None = "true",
) -> str:
    """A Forge extension as it appears in body.storage, with its `adf-fallback` copy."""
    guest = '<ac:adf-parameter key="name">Diagram</ac:adf-parameter>'
    if uml is not None:
        guest += f'<ac:adf-parameter key="data">{encode_data(uml)}</ac:adf-parameter>'
    guest += '<ac:adf-parameter key="revision" type="integer">3</ac:adf-parameter>'
    if compressed is not None:
        guest += (
            f'<ac:adf-parameter key="compressed" type="boolean">{compressed}</ac:adf-parameter>'
        )
    macro_params = ""
    if macro_params_uml is not None:
        macro_params = (
            '<ac:adf-parameter key="data"><ac:adf-parameter key="value">'
            f"{encode_data(macro_params_uml)}</ac:adf-parameter></ac:adf-parameter>"
            '<ac:adf-parameter key="compressed">'
            '<ac:adf-parameter key="value">true</ac:adf-parameter></ac:adf-parameter>'
        )
    node = _forge_node(key, local_id, guest, macro_params)
    return f"<ac:adf-extension>{node}<ac:adf-fallback>{node}</ac:adf-fallback></ac:adf-extension>"


def placeholder(text: str) -> str:
    return f"<div>{text}</div>"


def make_page(body_storage: str, html: str) -> MagicMock:
    page = MagicMock(spec=Page)
    page.id = 12345
    page.title = "Test Page"
    page.html = html
    page.labels = []
    page.ancestors = []
    page.attachments = []
    page.editor2 = ""
    page.body_storage = body_storage
    return page


def render(body_storage: str, html: str) -> str:
    """Run the full page conversion and return the Markdown."""
    return Page.Converter(make_page(body_storage, html)).markdown


class TestPlantUMLCloudPlaceholders:
    @pytest.fixture(autouse=True)
    def _settings(self):  # noqa: ANN202
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.include_document_title = False
            s.export.page_breadcrumbs = False
            s.export.page_metadata_in_frontmatter = False
            s.export.confluence_url_in_frontmatter = "none"
            yield s

    def test_classic_placeholder_resolved_by_local_id_anchor(self) -> None:
        storage = '<p local-id="p1" />' + classic_macro(UML_A, "m1")
        html = '<p local-id="p1"></p>' + placeholder(CLASSIC_TEXT)

        result = render(storage, html)

        assert "```plantuml\n" + UML_A + "\n```" in result
        assert CLASSIC_TEXT not in result

    def test_anchors_select_the_right_diagram(self) -> None:
        storage = (
            '<h5 local-id="h1">First</h5>'
            + classic_macro(UML_A, "m1")
            + '<h5 local-id="h2">Second</h5>'
            + classic_macro(UML_B, "m2")
        )
        html = (
            '<h5 local-id="h1">First</h5>'
            + placeholder(CLASSIC_TEXT)
            + '<h5 local-id="h2">Second</h5>'
            + placeholder(CLASSIC_TEXT)
        )

        result = render(storage, html)

        assert result.index("First") < result.index("Alice -> Bob")
        assert result.index("Second") < result.index("Bob -> Carol")
        assert result.index("Alice -> Bob") < result.index("Second")

    def test_placeholder_inside_expand_is_not_double_counted(self) -> None:
        """An expand converts its content twice; both diagrams must still be correct."""
        storage = (
            '<ac:structured-macro ac:name="expand"><ac:rich-text-body>'
            '<p local-id="p1" />' + classic_macro(UML_A, "m1") + "</ac:rich-text-body>"
            "</ac:structured-macro>"
            '<p local-id="p2" />' + classic_macro(UML_B, "m2")
        )
        html = (
            '<div class="expand-container"><div class="expand-control">'
            '<span class="expand-control-text">More</span></div>'
            '<div class="expand-content"><p local-id="p1"></p>'
            + placeholder(CLASSIC_TEXT)
            + "</div></div>"
            '<p local-id="p2"></p>' + placeholder(CLASSIC_TEXT)
        )

        result = render(storage, html)

        assert result.count("Alice -> Bob") == 1
        assert result.count("Bob -> Carol") == 1
        assert result.index("Alice -> Bob") < result.index("</details>")
        assert result.index("</details>") < result.index("Bob -> Carol")
        assert MARKER not in result

    def test_forge_placeholder_uses_guest_params(self) -> None:
        """`guest-params` holds the current revision; `macro-params` can be stale."""
        storage = '<p local-id="p1" />' + forge_extension(UML_C, "f1", macro_params_uml=UML_OLD)
        html = '<p local-id="p1"></p>' + placeholder(FORGE_TEXT)

        result = render(storage, html)

        assert "```plantuml\n" + UML_C + "\n```" in result
        assert "Stale -> Revision" not in result
        assert FORGE_TEXT not in result

    def test_forge_falls_back_to_macro_params_without_guest_data(self) -> None:
        storage = '<p local-id="p1" />' + forge_extension(None, "f1", macro_params_uml=UML_B)
        html = '<p local-id="p1"></p>' + placeholder(FORGE_TEXT)

        result = render(storage, html)

        assert "Bob -> Carol: Second" in result

    def test_forge_without_compressed_flag_is_uncompressed(self) -> None:
        raw = base64.b64encode(UML_A.encode()).decode()
        storage = '<p local-id="p1" />' + forge_extension(UML_A, "f1", compressed=None).replace(
            encode_data(UML_A), raw
        )
        html = '<p local-id="p1"></p>' + placeholder(FORGE_TEXT)

        result = render(storage, html)

        assert "Alice -> Bob: Hello" in result

    def test_mixed_page_keeps_every_diagram_in_place(self) -> None:
        """Forge draw.io (rendered as an image), Forge PlantUML and a classic macro."""
        storage = (
            '<p local-id="p0" />'
            + forge_extension(None, "d1", key=DRAWIO_KEY, macro_params_uml=None)
            + '<p local-id="p1" />'
            + forge_extension(UML_A, "f1")
            + forge_extension(UML_B, "f2")
            + classic_macro(UML_C, "m1")
        )
        html = (
            '<p local-id="p0"></p><img src="diagram.drawio.png"/>'
            '<p local-id="p1"></p>'
            + placeholder(FORGE_TEXT)
            + placeholder(FORGE_TEXT)
            + placeholder(CLASSIC_TEXT)
        )

        result = render(storage, html)

        assert result.index("Alice -> Bob") < result.index("Bob -> Carol")
        assert result.index("Bob -> Carol") < result.index("@startjson")
        assert FORGE_TEXT not in result
        assert CLASSIC_TEXT not in result

    def test_unanchored_placeholders_pair_by_order_when_counts_match(self) -> None:
        storage = classic_macro(UML_A, "m1") + classic_macro(UML_B, "m2")
        html = (
            "<table><tr><td>" + placeholder(CLASSIC_TEXT) + "</td>"
            "<td>" + placeholder(CLASSIC_TEXT) + "</td></tr></table>"
        )

        result = render(storage, html)

        assert result.index("Alice -> Bob") < result.index("Bob -> Carol")

    def test_extra_unanchored_placeholder_gets_marker_not_a_wrong_diagram(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        storage = '<p local-id="p1" />' + classic_macro(UML_A, "m1")
        html = placeholder(CLASSIC_TEXT) + '<p local-id="p1"></p>' + placeholder(CLASSIC_TEXT)

        with caplog.at_level(logging.WARNING):
            result = render(storage, html)

        assert result.count("Alice -> Bob") == 1
        assert result.index(MARKER) < result.index("Alice -> Bob")
        assert CLASSIC_TEXT not in result
        assert "Test Page" in caplog.text

    def test_included_placeholder_does_not_take_a_storage_slot(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A transcluded placeholder belongs to another page: left alone, no warning."""
        storage = classic_macro(UML_A, "m1")
        html = (
            '<div class="conf-macro output-block" data-macro-name="include">'
            + placeholder(CLASSIC_TEXT)
            + "</div>"
            + placeholder(CLASSIC_TEXT)
        )

        with caplog.at_level(logging.WARNING):
            result = render(storage, html)

        assert result.count("Alice -> Bob") == 1
        assert result.index(CLASSIC_TEXT) < result.index("Alice -> Bob")
        assert MARKER not in result
        assert not caplog.records

    def test_included_placeholder_is_not_matched_by_anchor(self) -> None:
        storage = '<p local-id="p1" />' + classic_macro(UML_A, "m1")
        html = (
            '<div class="conf-macro output-block" data-macro-name="include">'
            '<p local-id="p1"></p>' + placeholder(CLASSIC_TEXT) + "</div>"
        )

        result = render(storage, html)

        assert "Alice -> Bob" not in result
        assert CLASSIC_TEXT in result

    def test_forge_is_not_paired_by_order_next_to_other_forge_apps(self) -> None:
        """The only Forge placeholder belongs to another app; the PlantUML one has none."""
        storage = forge_extension(UML_A, "f1") + forge_extension(
            None, "x1", key="other-app/env/static/kanban", macro_params_uml=None
        )
        html = placeholder(FORGE_TEXT)

        result = render(storage, html)

        assert "Alice -> Bob" not in result
        assert FORGE_TEXT in result

    def test_other_forge_app_between_anchor_and_plantuml(self) -> None:
        """Every Forge extension counts toward the anchor offset on both sides."""
        storage = (
            '<p local-id="p1" />'
            + forge_extension(None, "x1", key="other-app/env/static/kanban", macro_params_uml=None)
            + forge_extension(UML_A, "f1")
            + classic_macro(UML_C, "m9")
        )
        html = '<p local-id="p1"></p>' + placeholder(FORGE_TEXT) + placeholder(FORGE_TEXT)

        result = render(storage, html)

        assert result.index(FORGE_TEXT) < result.index("Alice -> Bob")
        assert result.count(FORGE_TEXT) == 1

    def test_legacy_div_before_placeholder_keeps_the_anchor(self) -> None:
        """An old-style macro div counts toward the offset in body.view too."""
        storage = (
            classic_macro(UML_C, "m3")
            + '<p local-id="p1" />'
            + classic_macro(UML_B, "m1")
            + classic_macro(UML_A, "m2")
        )
        html = (
            '<p local-id="p1"></p>'
            '<div class="ap-container" data-macro-name="plantumlcloud" data-macro-id="m1" '
            'data-local-id="local-m1"></div>' + placeholder(CLASSIC_TEXT)
        )

        result = render(storage, html)

        assert result.index("Bob -> Carol") < result.index("Alice -> Bob")
        assert MARKER not in result

    def test_id_less_legacy_div_blocks_classic_matching(self) -> None:
        """An ID-less old-style div resolves by cursor; anchoring would duplicate it."""
        storage = '<p local-id="p1" />' + classic_macro(UML_A, "m1")
        html = (
            '<div class="ap-container" data-macro-name="plantumlcloud"></div>'
            '<p local-id="p1"></p>' + placeholder(CLASSIC_TEXT)
        )

        result = render(storage, html)

        assert result.count("Alice -> Bob") == 1
        assert result.index("Alice -> Bob") < result.index(MARKER)

    def test_repeated_legacy_id_does_not_hide_unused_diagrams(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        storage = classic_macro(UML_A, "m1") + classic_macro(UML_B, "m2")
        legacy = (
            '<div class="ap-container" data-macro-name="plantumlcloud" data-macro-id="m1"></div>'
        )

        with caplog.at_level(logging.WARNING):
            render(storage, legacy + legacy)

        assert "1 PlantUML diagram" in caplog.text

    def test_unchanged_html_is_returned_verbatim(self) -> None:
        html = "<p>Line one<br>Line two &amp; more</p>"
        converter = Page.Converter(make_page(classic_macro(UML_A, "m1"), html))

        assert converter._resolve_plantumlcloud_placeholders(html) == html

    def test_first_child_placeholders_anchor_on_their_parent(self) -> None:
        storage = (
            classic_macro(UML_C, "m0")
            + '<table><tbody><tr><td local-id="c1">'
            + classic_macro(UML_A, "m1")
            + '</td><td local-id="c2">'
            + classic_macro(UML_B, "m2")
            + "</td></tr></tbody></table>"
        )
        html = (
            '<table><tr><td local-id="c1">' + placeholder(CLASSIC_TEXT) + "</td>"
            '<td local-id="c2">' + placeholder(CLASSIC_TEXT) + "</td></tr></table>"
        )

        result = render(storage, html)

        assert result.index("Alice -> Bob") < result.index("Bob -> Carol")
        assert MARKER not in result

    def test_repeated_markdown_calls_do_not_accumulate(self) -> None:
        storage = '<p local-id="p1" />' + classic_macro(UML_A, "m1")
        converter = Page.Converter(
            make_page(storage, '<p local-id="p1"></p>' + placeholder(CLASSIC_TEXT))
        )

        first = converter.markdown
        second = converter.markdown

        assert first == second
        assert len(converter._resolved_plantumlcloud) == 1

    def test_placeholders_sharing_an_anchor_are_ambiguous(self) -> None:
        storage = '<p local-id="p1" />' + classic_macro(UML_A, "m1")
        html = (
            '<section><p local-id="p1"></p>' + placeholder(CLASSIC_TEXT) + "</section>"
            '<section><p local-id="p1"></p>' + placeholder(CLASSIC_TEXT) + "</section>"
        )

        result = render(storage, html)

        assert "Alice -> Bob" not in result
        assert result.count(MARKER) == 2

    def test_classic_placeholder_without_storage_gets_marker(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            result = render("", placeholder(CLASSIC_TEXT))

        assert MARKER in result
        assert CLASSIC_TEXT not in result
        assert caplog.records

    def test_other_forge_placeholder_is_left_alone(self) -> None:
        storage = '<p local-id="p1" />' + forge_extension(None, "x1", key=DRAWIO_KEY)
        html = '<p local-id="p1"></p>' + placeholder(FORGE_TEXT)

        result = render(storage, html)

        assert FORGE_TEXT in result
        assert MARKER not in result

    def test_forge_plantuml_resolves_next_to_another_forge_app(self) -> None:
        """Both render the same text; only the PlantUML one is replaced."""
        storage = (
            '<p local-id="p1" />'
            + forge_extension(None, "x1", key="other-app/env/static/kanban", macro_params_uml=None)
            + '<p local-id="p2" />'
            + forge_extension(UML_A, "f1")
        )
        html = (
            '<p local-id="p1"></p>'
            + placeholder(FORGE_TEXT)
            + '<p local-id="p2"></p>'
            + placeholder(FORGE_TEXT)
        )

        result = render(storage, html)

        assert result.index(FORGE_TEXT) < result.index("Alice -> Bob")
        assert result.count(FORGE_TEXT) == 1
        assert MARKER not in result

    def test_placeholders_in_column_layout_are_not_double_counted(self) -> None:
        """A column layout converts its cells twice; both diagrams must still be correct."""
        storage = (
            '<ac:layout><ac:layout-section ac:type="two_equal">'
            '<ac:layout-cell><p local-id="p1" />' + classic_macro(UML_A, "m1") + "</ac:layout-cell>"
            '<ac:layout-cell><p local-id="p2" />' + classic_macro(UML_B, "m2") + "</ac:layout-cell>"
            "</ac:layout-section></ac:layout>"
        )
        html = (
            '<div class="columnLayout two-equal" data-layout="two-equal">'
            '<div class="cell normal" data-type="normal"><div class="innerCell">'
            '<p local-id="p1"></p>' + placeholder(CLASSIC_TEXT) + "</div></div>"
            '<div class="cell normal" data-type="normal"><div class="innerCell">'
            '<p local-id="p2"></p>' + placeholder(CLASSIC_TEXT) + "</div></div>"
            "</div>"
        )

        result = render(storage, html)

        assert result.count("Alice -> Bob") == 1
        assert result.count("Bob -> Carol") == 1
        assert result.index("Alice -> Bob") < result.index("Bob -> Carol")
        assert MARKER not in result

    def test_unused_storage_diagram_is_reported(self, caplog: pytest.LogCaptureFixture) -> None:
        storage = '<p local-id="p1" />' + classic_macro(UML_A, "m1")

        with caplog.at_level(logging.WARNING):
            render(storage, '<p local-id="p1"></p>')

        assert "PlantUML" in caplog.text
        assert "Test Page" in caplog.text

    def test_legacy_iframe_rendering_is_unchanged(self, caplog: pytest.LogCaptureFixture) -> None:
        """The old placeholder with a macro id still resolves, without new warnings."""
        storage = classic_macro(UML_A, "m1")
        html = '<div class="ap-container" data-macro-name="plantumlcloud" data-macro-id="m1"></div>'

        with caplog.at_level(logging.WARNING):
            result = render(storage, html)

        assert "Alice -> Bob: Hello" in result
        assert not caplog.records
