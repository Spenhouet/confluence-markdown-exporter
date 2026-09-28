"""Unit tests for the `plantumlcloud` macro conversion.

The "Flowchart, PlantUML Diagrams for Confluence" app uses the macro name
`plantumlcloud` on Confluence Cloud and keeps the diagram source in the macro's
`data` parameter of `body.storage`, base64-encoded and (usually) raw-deflated.
"""

import base64
import zlib
from unittest.mock import MagicMock
from unittest.mock import patch
from urllib.parse import quote

import pytest
from bs4 import BeautifulSoup

from confluence_markdown_exporter.confluence import Page

UML_A = "@startuml\nAlice -> Bob: Hello\n@enduml"
UML_B = "@startuml\nBob -> Carol: Second\n@enduml"


def encode_data(uml: str, *, compressed: bool = True) -> str:
    """Encode UML source the way the app stores it in the `data` parameter."""
    payload = quote(uml).encode()
    if compressed:
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        payload = compressor.compress(payload) + compressor.flush()
    return base64.b64encode(payload).decode()


def storage_macro(data: str, macro_id: str = "", *, compressed: bool = True) -> str:
    """Build a `plantumlcloud` structured-macro as it appears in body.storage."""
    macro_id_attr = f' ac:macro-id="{macro_id}"' if macro_id else ""
    return (
        f'<ac:structured-macro ac:name="plantumlcloud"{macro_id_attr} ac:schema-version="1">'
        '<ac:parameter ac:name="filename">diagram.svg</ac:parameter>'
        f'<ac:parameter ac:name="data">{data}</ac:parameter>'
        f'<ac:parameter ac:name="compressed">{str(compressed).lower()}</ac:parameter>'
        "</ac:structured-macro>"
    )


def view_div(macro_id: str = "") -> str:
    """Build the empty Connect placeholder the app renders into body.view."""
    macro_id_attr = f' data-macro-id="{macro_id}"' if macro_id else ""
    return (
        '<div class="ap-container conf-macro output-block" data-hasbody="false"'
        f'{macro_id_attr} data-macro-name="plantumlcloud">'
        '<div class="ap-content"> </div>'
        '<script class="ap-iframe-body-script">//<![CDATA[\n'
        'var data = {"addon_key":"com.mxgraph.confluence.plugins.plantuml"};\n'
        "//]]></script>"
        "</div>"
    )


def make_page(body_storage: str) -> MagicMock:
    page = MagicMock(spec=Page)
    page.id = 12345
    page.title = "Test Page"
    page.html = "<h1>Test Page</h1>"
    page.labels = []
    page.ancestors = []
    page.attachments = []
    page.editor2 = ""
    page.body_storage = body_storage
    return page


def element(html: str, tag: str = "div") -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser").find(tag)


class TestPlantUMLCloudConversion:
    """Test cases for the `plantumlcloud` macro."""

    @pytest.fixture(autouse=True)
    def _settings(self):  # noqa: ANN202
        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.include_document_title = False
            mock_settings.export.page_breadcrumbs = False
            yield mock_settings

    def test_compressed_macro_matched_by_macro_id(self) -> None:
        """Compressed source is decoded into a fenced plantuml code block."""
        page = make_page(storage_macro(encode_data(UML_A), "macro-1"))
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "```plantuml" in result
        assert "Alice -> Bob: Hello" in result
        assert result.strip().endswith("```")

    def test_uncompressed_macro(self) -> None:
        """Base64-only payloads (compressed=false) are decoded as well."""
        page = make_page(
            storage_macro(encode_data(UML_A, compressed=False), "macro-1", compressed=False)
        )
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "```plantuml" in result
        assert "Alice -> Bob: Hello" in result

    def test_macro_id_selects_the_right_diagram(self) -> None:
        """With several diagrams on the page, each macro-id resolves its own source."""
        page = make_page(
            storage_macro(encode_data(UML_A), "macro-1")
            + "<p>Some text between diagrams</p>"
            + storage_macro(encode_data(UML_B), "macro-2")
        )
        converter = Page.Converter(page)

        # Convert the second diagram first to prove the lookup is not positional.
        second = converter.convert_plantumlcloud(element(view_div("macro-2")), "", [])
        first = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "Bob -> Carol: Second" in second
        assert "Alice -> Bob: Hello" in first

    def test_positional_fallback_without_macro_id(self) -> None:
        """Without a usable macro-id, diagrams are matched by position."""
        page = make_page(storage_macro(encode_data(UML_A)) + storage_macro(encode_data(UML_B)))
        converter = Page.Converter(page)

        first = converter.convert_plantumlcloud(element(view_div()), "", [])
        second = converter.convert_plantumlcloud(element(view_div()), "", [])

        assert "Alice -> Bob: Hello" in first
        assert "Bob -> Carol: Second" in second

    def test_positional_cursor_advances_on_macro_id_match(self) -> None:
        """A macro-id match must not leave the positional cursor behind.

        Otherwise a following macro without a macro-id would re-resolve the
        already consumed diagram instead of advancing to the next one.
        """
        page = make_page(
            storage_macro(encode_data(UML_A), "macro-1") + storage_macro(encode_data(UML_B))
        )
        converter = Page.Converter(page)

        first = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])
        second = converter.convert_plantumlcloud(element(view_div()), "", [])

        assert "Alice -> Bob: Hello" in first
        assert "Bob -> Carol: Second" in second

    def test_cursor_is_not_rewound_by_a_later_macro_id_match(self) -> None:
        """A macro-id match must not move the positional cursor backwards.

        Resolving an earlier diagram by id in the middle of a positional run would
        otherwise replay diagrams already emitted and drop the ones still pending.
        """
        page = make_page(
            storage_macro(encode_data("@startuml\nFIRST\n@enduml"), "m1")
            + storage_macro(encode_data("@startuml\nSECOND\n@enduml"))
            + storage_macro(encode_data("@startuml\nTHIRD\n@enduml"))
        )
        converter = Page.Converter(page)

        results = [
            converter.convert_plantumlcloud(element(view_div(macro_id)), "", [])
            for macro_id in ("", "", "m1", "")
        ]

        assert "FIRST" in results[0]
        assert "SECOND" in results[1]
        assert "FIRST" in results[2]
        assert "THIRD" in results[3]

    def test_more_placeholders_than_stored_macros_emits_comment(self) -> None:
        """Running past the end of body.storage produces a marker, not a repeat."""
        page = make_page(storage_macro(encode_data(UML_A)))
        converter = Page.Converter(page)

        first = converter.convert_plantumlcloud(element(view_div()), "", [])
        second = converter.convert_plantumlcloud(element(view_div()), "", [])

        assert "Alice -> Bob: Hello" in first
        assert "<!-- PlantUML diagram" in second

    @pytest.mark.parametrize(
        "body_storage",
        [
            pytest.param(
                '<ac:structured-macro ac:name="plantumlcloud" ac:macro-id="macro-1">'
                '<ac:parameter ac:name="filename">diagram.svg</ac:parameter>'
                "</ac:structured-macro>",
                id="no-data-parameter",
            ),
            pytest.param(storage_macro("", "macro-1"), id="empty-data-parameter"),
            pytest.param(
                storage_macro(base64.b64encode(b"   \n  ").decode(), "macro-1", compressed=False),
                id="whitespace-only-payload",
            ),
        ],
    )
    def test_malformed_macro_emits_comment(self, body_storage: str) -> None:
        """A macro that carries no usable source produces a marker, never an exception."""
        converter = Page.Converter(make_page(body_storage))

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "<!-- PlantUML diagram" in result

    def test_foreign_macro_id_emits_comment(self) -> None:
        """A macro-id unknown to body.storage must not resolve to another diagram.

        An include macro expands the transcluded page's view HTML into this page, so
        its placeholders carry macro-ids that only the other page's storage knows.
        Falling back to position would export an unrelated diagram.
        """
        page = make_page(storage_macro(encode_data(UML_A), "macro-1"))
        converter = Page.Converter(page)

        foreign = converter.convert_plantumlcloud(element(view_div("foreign-9")), "", [])
        own = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "<!-- PlantUML diagram" in foreign
        assert "Alice -> Bob: Hello" not in foreign
        assert "Alice -> Bob: Hello" in own

    def test_unknown_macro_id_falls_back_when_storage_has_no_ids(self) -> None:
        """Positional matching still applies when storage carries no macro-ids at all."""
        page = make_page(storage_macro(encode_data(UML_A)))
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("some-id")), "", [])

        assert "Alice -> Bob: Hello" in result

    def test_unknown_macro_id_falls_back_when_storage_ids_are_partial(self) -> None:
        """A page mixing identified and unidentified macros must not lose a diagram.

        The foreign-macro guard may only suppress the fallback when every stored macro
        is identifiable, otherwise an unidentified diagram becomes unreachable.
        """
        page = make_page(
            storage_macro(encode_data(UML_A)) + storage_macro(encode_data(UML_B), "m2")
        )
        converter = Page.Converter(page)

        first = converter.convert_plantumlcloud(element(view_div("generated-1")), "", [])
        second = converter.convert_plantumlcloud(element(view_div("m2")), "", [])

        assert "Alice -> Bob: Hello" in first
        assert "Bob -> Carol: Second" in second

    def test_absent_compressed_parameter_means_uncompressed(self) -> None:
        """A macro without a `compressed` parameter is read as plain base64."""
        payload = base64.b64encode(UML_A.encode()).decode()
        page = make_page(
            '<ac:structured-macro ac:name="plantumlcloud" ac:macro-id="macro-1">'
            f'<ac:parameter ac:name="data">{payload}</ac:parameter>'
            "</ac:structured-macro>"
        )
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "Alice -> Bob: Hello" in result

    def test_nested_parameters_are_ignored(self) -> None:
        """Only the macro's own parameters count, not those of a macro nested in its body."""
        page = make_page(
            '<ac:structured-macro ac:name="plantumlcloud" ac:macro-id="macro-1">'
            f'<ac:parameter ac:name="data">{encode_data(UML_A)}</ac:parameter>'
            '<ac:parameter ac:name="compressed">true</ac:parameter>'
            "<ac:rich-text-body>"
            '<ac:structured-macro ac:name="expand">'
            '<ac:parameter ac:name="data">bogus-nested-payload</ac:parameter>'
            '<ac:parameter ac:name="compressed">false</ac:parameter>'
            "</ac:structured-macro>"
            "</ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "Alice -> Bob: Hello" in result
        assert "bogus" not in result

    def test_line_wrapped_base64_is_decoded(self) -> None:
        """Whitespace inside the base64 value must not break decoding.

        Emitting the undecoded parameter as if it were diagram source would put a
        base64 blob into the export.
        """
        data = encode_data(UML_A)
        wrapped = f"{data[:20]}\n{data[20:]}"
        page = make_page(storage_macro(wrapped, "macro-1"))
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "Alice -> Bob: Hello" in result
        assert data[:20] not in result

    def test_literal_percent_is_preserved(self) -> None:
        """A literal `%` in the source survives: `%date%` is a PlantUML built-in."""
        uml = "@startuml\ntitle %date% 100%\nAlice -> Bob: Hello\n@enduml"
        payload = base64.b64encode(uml.encode()).decode()
        page = make_page(storage_macro(payload, "macro-1", compressed=False))
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "title %date% 100%" in result

    def test_percent_encoded_uncompressed_payload_is_decoded(self) -> None:
        """An uncompressed but percent-encoded payload is still decoded."""
        payload = base64.b64encode(quote(UML_A).encode()).decode()
        page = make_page(storage_macro(payload, "macro-1", compressed=False))
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "Alice -> Bob: Hello" in result
        assert "%40startuml" not in result

    def test_corrupt_data_emits_comment(self) -> None:
        """Undecodable payloads produce a comment instead of raising."""
        page = make_page(storage_macro(base64.b64encode(b"not deflated").decode(), "macro-1"))
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "<!-- PlantUML diagram" in result
        assert "source not found" in result

    def test_truncated_payload_emits_comment(self) -> None:
        """A truncated deflate stream inflates without error; it must not be exported.

        Half a diagram rendered as if it were whole is worse than a visible marker.
        """
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        full = compressor.compress(quote(UML_A).encode()) + compressor.flush()
        truncated = base64.b64encode(full[: len(full) // 2]).decode()
        page = make_page(storage_macro(truncated, "macro-1"))
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "<!-- PlantUML diagram" in result
        assert "@startuml" not in result

    def test_oversized_payload_emits_comment(self) -> None:
        """A highly compressible payload is not inflated without bound."""
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        bomb = compressor.compress(b"A" * (8 * 1024 * 1024)) + compressor.flush()
        page = make_page(storage_macro(base64.b64encode(bomb).decode(), "macro-1"))
        converter = Page.Converter(page)

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "<!-- PlantUML diagram" in result
        assert "source not found" in result

    def test_missing_storage_emits_comment(self) -> None:
        """An empty body.storage produces a comment instead of silent omission."""
        converter = Page.Converter(make_page(""))

        result = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])

        assert "<!-- PlantUML diagram" in result

    def test_convert_div_dispatches_plantumlcloud(self) -> None:
        """End-to-end: the placeholder div converts to a code block, script is dropped."""
        page = make_page(storage_macro(encode_data(UML_A), "macro-1"))
        converter = Page.Converter(page)

        result = converter.convert(view_div("macro-1"))

        assert "```plantuml" in result
        assert "Alice -> Bob: Hello" in result
        assert "addon_key" not in result
        assert "var data" not in result

    def test_both_macro_flavours_on_one_page(self) -> None:
        """Server `plantuml` and Cloud `plantumlcloud` macros stay independent.

        Both flavours share the body.storage macro cache, so a page holding one of
        each must resolve both without cross-talk.
        """
        server_uml = "@startuml\nCarol -> Dave: Server\n@enduml"
        page = make_page(
            '<ac:structured-macro ac:name="plantuml">'
            f"<ac:plain-text-body><![CDATA[{server_uml}]]></ac:plain-text-body>"
            "</ac:structured-macro>" + storage_macro(encode_data(UML_A), "macro-1")
        )
        converter = Page.Converter(page)

        cloud = converter.convert_plantumlcloud(element(view_div("macro-1")), "", [])
        server = converter.convert_plantuml(
            element('<span data-macro-name="plantuml"></span>', "span"), "", []
        )

        assert "Alice -> Bob: Hello" in cloud
        assert "Carol -> Dave: Server" not in cloud
        assert "Carol -> Dave: Server" in server
        assert "Alice -> Bob: Hello" not in server
