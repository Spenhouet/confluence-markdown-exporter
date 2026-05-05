"""Unit tests for confluence module URL resolution."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from confluence_markdown_exporter.confluence import Attachment
from confluence_markdown_exporter.confluence import Page
from confluence_markdown_exporter.confluence import Space
from confluence_markdown_exporter.confluence import User
from confluence_markdown_exporter.confluence import Version


class MockPage:
    """Minimal page object for Converter tests."""

    def __init__(self) -> None:
        self.id = "test-page"
        self.title = "Test Page"
        self.html = ""
        self.labels = []
        self.ancestors = []

    def get_attachment_by_file_id(self, file_id: str) -> None:
        return None


@pytest.fixture
def converter() -> Page.Converter:
    return Page.Converter(MockPage())


class TestSquareBracketEscaping:
    """Square brackets in plain text must be escaped to avoid markdown link syntax."""

    def test_bracket_notation_escaped(self, converter: Page.Converter) -> None:
        html = "<p>test [R1] test</p>"
        result = converter.convert(html).strip()
        assert result == r"test \[R1\] test"

    def test_bracket_at_start(self, converter: Page.Converter) -> None:
        html = "<p>[R1] test</p>"
        result = converter.convert(html).strip()
        assert result == r"\[R1\] test"

    def test_bracket_at_end(self, converter: Page.Converter) -> None:
        html = "<p>test [R1]</p>"
        result = converter.convert(html).strip()
        assert result == r"test \[R1\]"

    def test_multiple_bracket_groups(self, converter: Page.Converter) -> None:
        html = "<p>[A1] and [B2]</p>"
        result = converter.convert(html).strip()
        assert result == r"\[A1\] and \[B2\]"

    def test_bracket_in_code_not_escaped(self, converter: Page.Converter) -> None:
        html = "<code>[R1]</code>"
        result = converter.convert(html).strip()
        assert result == "`[R1]`"

    def test_real_link_not_affected(self, converter: Page.Converter) -> None:
        html = '<a href="https://example.com">click here</a>'
        result = converter.convert(html).strip()
        assert result == "[click here](https://example.com)"


class TestAnchorLinkConversion:
    """Internal anchor links must use the href value for slug, not link text."""

    def test_anchor_uses_href_not_link_text(self, converter: Page.Converter) -> None:
        """Anchor slug derived from href, not display text."""
        html = '<a href="#1.-Request-Service">request service</a>'
        result = converter.convert(html).strip()
        assert result == "[request service](#1-request-service)"

    def test_anchor_plain_heading(self, converter: Page.Converter) -> None:
        """Simple heading anchor round-trips correctly."""
        html = '<a href="#My-Heading">My Heading</a>'
        result = converter.convert(html).strip()
        assert result == "[My Heading](#my-heading)"

    def test_anchor_with_numbers_and_punctuation(self, converter: Page.Converter) -> None:
        """Numbered heading anchors match GitHub markdown anchor format."""
        html = '<a href="#2.-Setup-Steps">setup steps</a>'
        result = converter.convert(html).strip()
        assert result == "[setup steps](#2-setup-steps)"

    def test_wiki_anchor_uses_link_text(self, converter: Page.Converter) -> None:
        """Wiki links use link text for slug, not href."""
        from unittest.mock import patch

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.page_href = "wiki"
            html = '<a href="#1.-Request-Service">Request Service</a>'
            result = converter.convert(html).strip()
        assert result == "[[#Request Service]]"


def _make_attachment(
    att_id: str,
    file_id: str,
    title: str = "file.png",
    media_type: str = "image/png",
) -> Attachment:
    space = Space(base_url="https://example.com", key="TS", name="Test", description="", homepage=0)
    version = Version(
        number=1,
        by=User(account_id="u1", display_name="User", username="user", public_name="", email=""),
        when="2024-01-01T00:00:00Z",
        friendly_when="Jan 1",
    )
    return Attachment(
        base_url="https://example.com",
        title=title,
        space=space,
        ancestors=[],
        version=version,
        id=att_id,
        file_size=100,
        media_type=media_type,
        media_type_description="",
        file_id=file_id,
        collection_name="",
        download_link="/download",
        comment="",
    )


def _make_page(body: str, body_export: str, attachments: list[Attachment]) -> Page:
    space = Space(base_url="https://example.com", key="TS", name="Test", description="", homepage=0)
    version = Version(
        number=1,
        by=User(account_id="u1", display_name="User", username="user", public_name="", email=""),
        when="2024-01-01T00:00:00Z",
        friendly_when="Jan 1",
    )
    return Page(
        base_url="https://example.com",
        id=1,
        title="Test Page",
        space=space,
        ancestors=[],
        version=version,
        body=body,
        body_export=body_export,
        editor2="",
        labels=[],
        attachments=attachments,
    )


class TestAttachmentsForExport:
    """_attachments_for_export selects the right attachments."""

    def test_file_id_in_body_included(self) -> None:
        att = _make_attachment("111", "abc-guid-111")
        page = _make_page(
            body='<img data-media-id="abc-guid-111" src="...">',
            body_export="",
            attachments=[att],
        )
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_export_all = False
            result = page._attachments_for_export()
        assert att in result

    def test_attachment_id_in_body_included(self) -> None:
        """SVG/MP4 referenced via data-linked-resource-id must be exported."""
        att = _make_attachment(
            "99999", "xyz-guid-99", title="image.svg", media_type="image/svg+xml"
        )
        page = _make_page(
            body='<img data-linked-resource-id="99999" src="...">',
            body_export="",
            attachments=[att],
        )
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_export_all = False
            result = page._attachments_for_export()
        assert att in result

    def test_attachment_id_in_body_export_included(self) -> None:
        """Attachment referenced only in body_export (e.g. MP4) must be exported."""
        att = _make_attachment("88888", "xyz-guid-88", title="video.mp4", media_type="video/mp4")
        page = _make_page(
            body="",
            body_export='<a data-linked-resource-id="88888" href="...">video.mp4</a>',
            attachments=[att],
        )
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_export_all = False
            result = page._attachments_for_export()
        assert att in result

    def test_title_in_body_src_url_included(self) -> None:
        """SVG referenced only by filename in src URL (no data attributes) must be exported."""
        att = _make_attachment(
            "66666", "xyz-guid-66", title="MEP-Symbol_CH-REP.svg", media_type="image/svg+xml"
        )
        page = _make_page(
            body='<img src="/download/attachments/12345/MEP-Symbol_CH-REP.svg?version=1">',
            body_export="",
            attachments=[att],
        )
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_export_all = False
            result = page._attachments_for_export()
        assert att in result

    def test_title_with_spaces_url_encoded_in_body_export_included(self) -> None:
        att = _make_attachment("55555", "xyz-guid-55", title="my video.mp4", media_type="video/mp4")
        page = _make_page(
            body="",
            body_export='<img src="/download/attachments/12345/my%20video.mp4">',
            attachments=[att],
        )
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_export_all = False
            result = page._attachments_for_export()
        assert att in result

    def test_unreferenced_attachment_excluded(self) -> None:
        att = _make_attachment("77777", "xyz-guid-77", title="unused.png")
        page = _make_page(body="no references here", body_export="", attachments=[att])
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_export_all = False
            result = page._attachments_for_export()
        assert att not in result

    def test_attachment_export_all_returns_all(self) -> None:
        att1 = _make_attachment("111", "aaa")
        att2 = _make_attachment("222", "bbb", title="other.svg", media_type="image/svg+xml")
        page = _make_page(body="", body_export="", attachments=[att1, att2])
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_export_all = True
            result = page._attachments_for_export()
        assert result == [att1, att2]


class TestTransformErrorImg:
    """transform-error SVG images must resolve via data-encoded-xml."""

    def test_transform_error_resolves_attachment_by_encoded_xml(self) -> None:
        from pathlib import Path
        from urllib.parse import quote

        class MockAttachment:
            title = "MEP-Symbol_CH-REP.svg"
            export_path = Path("TEST/attachments/guid123.svg")

        class MockPageWithSvg:
            def __init__(self) -> None:
                self.id = "test-page"
                self.title = "Test Page"
                self.html = ""
                self.labels: list = []
                self.ancestors: list = []
                self.export_path = Path("TEST/Instructions for Use.md")

            def get_attachment_by_file_id(self, _fid: str) -> None:
                return None

            def get_attachment_by_id(self, _aid: str) -> None:
                return None

            def get_attachments_by_title(self, title: str) -> list:
                if title == "MEP-Symbol_CH-REP.svg":
                    return [MockAttachment()]
                return []

        encoded = quote('<ac:image><ri:attachment ri:filename="MEP-Symbol_CH-REP.svg"/></ac:image>')
        html = (
            f'<img class="transform-error" data-encoded-xml="{encoded}" '
            f'src="https://example.com/placeholder/error" title="">'
        )

        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_href = "relative"
            s.export.page_href = "relative"
            conv = Page.Converter(MockPageWithSvg())  # type: ignore[arg-type]
            result = conv.convert(html).strip()

        assert "placeholder/error" not in result
        assert "MEP-Symbol_CH-REP.svg" in result or "guid123.svg" in result


class TestPageFromUrl:
    """Test cases for Page.from_url."""

    def test_from_url_prefers_page_id_query_parameter_for_legacy_server_url(self) -> None:
        """Legacy Server/DC viewpage.action links should resolve by pageId."""
        page_url = (
            "https://wiki.example.com/pages/viewpage.action"
            "?pageId=317425825&src=contextnavpagetreemode"
        )

        with (
            patch("confluence_markdown_exporter.confluence.get_confluence_instance"),
            patch("confluence_markdown_exporter.confluence.Page.from_id") as mock_from_id,
            patch("confluence_markdown_exporter.confluence.get_thread_confluence") as mock_client,
        ):
            mock_from_id.return_value = "page"

            result = Page.from_url(page_url)

        assert result == "page"
        mock_from_id.assert_called_once_with(317425825, "https://wiki.example.com")
        mock_client.assert_not_called()


class TestSpanHighlightConversion:
    """Background-color spans must become <mark> elements when enabled."""

    def test_background_color_rgb_converted_to_mark(self, converter: Page.Converter) -> None:
        html = '<p><span style="background-color: rgb(248,230,160);">hello</span></p>'
        result = converter.convert(html).strip()
        assert '<mark style="background: #f8e6a0;">hello</mark>' in result

    def test_multiple_channels_converted_correctly(self, converter: Page.Converter) -> None:
        html = '<p><span style="background-color: rgb(198,237,251);">text</span></p>'
        result = converter.convert(html).strip()
        assert '<mark style="background: #c6edfb;">text</mark>' in result

    def test_highlight_disabled_returns_plain_text(self, converter: Page.Converter) -> None:
        html = '<p><span style="background-color: rgb(248,230,160);">hello</span></p>'
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.convert_text_highlights = False
            s.export.convert_font_colors = True
            result = converter.convert(html).strip()
        assert "<mark" not in result
        assert "hello" in result


class TestSpanFontColorConversion:
    """Color spans must become <font> elements when enabled."""

    def test_inline_color_rgb_converted_to_font(self, converter: Page.Converter) -> None:
        html = '<p><span style="color: rgb(7,71,166);">blue text</span></p>'
        result = converter.convert(html).strip()
        assert '<font style="color: #0747a6;">blue text</font>' in result

    def test_background_color_not_matched_as_font_color(self, converter: Page.Converter) -> None:
        html = '<p><span style="background-color: rgb(248,230,160);">hi</span></p>'
        result = converter.convert(html).strip()
        assert "<font" not in result
        assert '<mark style="background: #f8e6a0;">hi</mark>' in result

    def test_data_colorid_resolved_from_style_tag(self) -> None:
        page = MockPage()
        page.html = (
            '<style>[data-colorid=abc123]{color:#ff5630} '
            'html[data-color-mode=dark] [data-colorid=abc123]{color:#cf2600}</style>'
        )
        conv = Page.Converter(page)  # type: ignore[arg-type]
        html = '<p><span data-colorid="abc123">colored</span></p>'
        result = conv.convert(html).strip()
        assert '<font style="color: #ff5630;">colored</font>' in result

    def test_data_colorid_unknown_falls_through(self, converter: Page.Converter) -> None:
        html = '<p><span data-colorid="unknown999">text</span></p>'
        result = converter.convert(html).strip()
        assert "<font" not in result
        assert "text" in result

    def test_font_color_disabled_returns_plain_text(self, converter: Page.Converter) -> None:
        html = '<p><span style="color: rgb(255,86,48);">red text</span></p>'
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.convert_text_highlights = True
            s.export.convert_font_colors = False
            result = converter.convert(html).strip()
        assert "<font" not in result
        assert "red text" in result


class TestStatusBadgeConversion:
    """Confluence status-macro lozenge spans must become <mark> elements when enabled."""

    def _badge(self, extra_class: str, label: str) -> str:
        classes = f"status-macro aui-lozenge aui-lozenge-visual-refresh {extra_class}".strip()
        return (
            f'<p><span class="{classes}" data-macro-name="status">{label}</span></p>'
        )

    def test_gray_badge(self, converter: Page.Converter) -> None:
        html = self._badge("", "IN PROGRESS")
        result = converter.convert(html).strip()
        assert '<mark style="background: #dfe1e6;">IN PROGRESS</mark>' in result

    def test_blue_badge(self, converter: Page.Converter) -> None:
        html = self._badge("aui-lozenge-complete", "DONE")
        result = converter.convert(html).strip()
        assert '<mark style="background: #cce0ff;">DONE</mark>' in result

    def test_green_badge(self, converter: Page.Converter) -> None:
        html = self._badge("aui-lozenge-success", "SUCCESS")
        result = converter.convert(html).strip()
        assert '<mark style="background: #baf3db;">SUCCESS</mark>' in result

    def test_yellow_badge(self, converter: Page.Converter) -> None:
        html = self._badge("aui-lozenge-current", "ORANGE")
        result = converter.convert(html).strip()
        assert '<mark style="background: #f8e6a0;">ORANGE</mark>' in result

    def test_red_badge(self, converter: Page.Converter) -> None:
        html = self._badge("aui-lozenge-error", "BLOCKED")
        result = converter.convert(html).strip()
        assert '<mark style="background: #ffd5d2;">BLOCKED</mark>' in result

    def test_purple_badge(self, converter: Page.Converter) -> None:
        html = self._badge("aui-lozenge-progress", "VIOLET")
        result = converter.convert(html).strip()
        assert '<mark style="background: #dfd8fd;">VIOLET</mark>' in result

    def test_badge_disabled_returns_plain_text(self, converter: Page.Converter) -> None:
        html = self._badge("aui-lozenge-error", "BLOCKED")
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.convert_status_badges = False
            s.export.convert_font_colors = True
            s.export.convert_text_highlights = True
            result = converter.convert(html).strip()
        assert "<mark" not in result
        assert "BLOCKED" in result
