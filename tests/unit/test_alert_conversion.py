"""Test Confluence alert/panel macro conversion."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from confluence_markdown_exporter.confluence import Page


def _make_converter(editor2: str = "") -> Page.Converter:
    from confluence_markdown_exporter.confluence import Page

    class MockPage:
        def __init__(self) -> None:
            self.id = "test-page"
            self.title = "Test Page"
            self.html = ""
            self.labels = []
            self.ancestors = []
            self.editor2 = editor2

        def get_attachment_by_file_id(self, file_id: str) -> None:
            return None

    return Page.Converter(MockPage())


@pytest.fixture
def converter() -> Page.Converter:
    return _make_converter()


class TestAlertOutsideTable:
    def test_panel_renders_as_note_alert(self, converter: Page.Converter) -> None:
        html = '<div data-macro-name="panel"><p>body text</p></div>'
        out = converter.convert(html)
        assert "> [!NOTE]" in out
        assert "body text" in out

    def test_warning_renders_as_caution_alert(self, converter: Page.Converter) -> None:
        html = '<div data-macro-name="warning"><p>danger</p></div>'
        out = converter.convert(html)
        assert "> [!CAUTION]" in out


class TestAlertInsideTableCell:
    def test_panel_in_td_emits_emoji_no_blockquote(self, converter: Page.Converter) -> None:
        html = (
            "<table><tr><td>"
            '<div data-macro-name="panel"><p>Klinische Abteilung</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "[!NOTE]" not in out
        assert ">" not in out.replace("</td>", "")
        assert "\U0001f4dd Klinische Abteilung" in out

    def test_info_in_td_emits_important_emoji(self, converter: Page.Converter) -> None:
        html = (
            "<table><tr><td>"
            '<div data-macro-name="info"><p>info text</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "[!IMPORTANT]" not in out
        assert "❗ info text" in out

    def test_warning_in_td_emits_caution_emoji(self, converter: Page.Converter) -> None:
        html = (
            "<table><tr><td>"
            '<div data-macro-name="warning"><p>danger</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "[!CAUTION]" not in out
        assert "\U0001f6d1 danger" in out

    def test_tip_in_td_emits_tip_emoji(self, converter: Page.Converter) -> None:
        html = (
            "<table><tr><td>"
            '<div data-macro-name="tip"><p>helpful</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "[!TIP]" not in out
        assert "\U0001f4a1 helpful" in out

    def test_note_in_td_emits_warning_emoji(self, converter: Page.Converter) -> None:
        html = (
            "<table><tr><td>"
            '<div data-macro-name="note"><p>watch out</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "[!WARNING]" not in out
        assert "⚠️ watch out" in out

    def test_panel_in_th_emits_emoji_no_blockquote(self, converter: Page.Converter) -> None:
        html = (
            "<table><tr><th>"
            '<div data-macro-name="panel"><p>header note</p></div>'
            "</th></tr></table>"
        )
        out = converter.convert(html)
        assert "[!NOTE]" not in out
        assert "\U0001f4dd header note" in out


class TestCustomPanelEmoji:
    def test_custom_panel_icon_text_used_in_table_cell(self) -> None:
        editor2 = (
            '<ac:structured-macro ac:name="panel" ac:macro-id="abc-1">'
            '<ac:parameter ac:name="panelIconId">1f6e0</ac:parameter>'
            '<ac:parameter ac:name="panelIcon">:tools:</ac:parameter>'
            '<ac:parameter ac:name="panelIconText">\U0001f6e0️</ac:parameter>'
            "<ac:rich-text-body><p>Klinische Abteilung</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        converter = _make_converter(editor2)
        html = (
            "<table><tr><td>"
            '<div data-macro-name="panel" data-macro-id="abc-1"><p>Klinische Abteilung</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "\U0001f6e0️ Klinische Abteilung" in out
        assert "\U0001f4dd" not in out

    def test_custom_panel_icon_id_decoded_when_no_text(self) -> None:
        editor2 = (
            '<ac:structured-macro ac:name="panel" ac:macro-id="abc-2">'
            '<ac:parameter ac:name="panelIconId">1f6e0</ac:parameter>'
            "<ac:rich-text-body><p>x</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        converter = _make_converter(editor2)
        html = (
            "<table><tr><td>"
            '<div data-macro-name="panel" data-macro-id="abc-2"><p>x</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "\U0001f6e0 x" in out

    def test_panel_without_custom_icon_falls_back_to_default(self) -> None:
        editor2 = (
            '<ac:structured-macro ac:name="panel" ac:macro-id="plain-1">'
            "<ac:rich-text-body><p>plain</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        converter = _make_converter(editor2)
        html = (
            "<table><tr><td>"
            '<div data-macro-name="panel" data-macro-id="plain-1"><p>plain</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "\U0001f4dd plain" in out

    def test_unknown_macro_id_falls_back_to_default(self) -> None:
        converter = _make_converter("")
        html = (
            "<table><tr><td>"
            '<div data-macro-name="panel" data-macro-id="missing"><p>y</p></div>'
            "</td></tr></table>"
        )
        out = converter.convert(html)
        assert "\U0001f4dd y" in out
