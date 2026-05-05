"""Unit tests for confluence module URL resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
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
        self.body_storage = ""
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


def _make_page(
    body: str,
    body_export: str,
    attachments: list[Attachment],
    body_storage: str = "",
) -> Page:
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
        body_storage=body_storage,
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
                self.body_storage = ""
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


class TestParseImageCaptions:
    """_parse_image_captions extracts captions from Confluence storage XML."""

    def test_cdata_caption_extracted(self) -> None:
        from confluence_markdown_exporter.confluence import _parse_image_captions

        storage = (
            '<ac:image ac:align="center">'
            '<ri:attachment ri:filename="testbild.jpeg"/>'
            "<ac:caption>"
            "<ac:plain-text-body><![CDATA[My Caption]]></ac:plain-text-body>"
            "</ac:caption>"
            "</ac:image>"
        )
        assert _parse_image_captions(storage) == {"testbild.jpeg": "My Caption"}

    def test_plain_text_caption_extracted(self) -> None:
        from confluence_markdown_exporter.confluence import _parse_image_captions

        storage = (
            "<ac:image>"
            '<ri:attachment ri:filename="photo.png"/>'
            "<ac:caption>"
            "<ac:plain-text-body>Plain Caption</ac:plain-text-body>"
            "</ac:caption>"
            "</ac:image>"
        )
        assert _parse_image_captions(storage) == {"photo.png": "Plain Caption"}

    def test_paragraph_caption_extracted(self) -> None:
        from confluence_markdown_exporter.confluence import _parse_image_captions

        storage = (
            '<ac:image ac:align="center">'
            '<ri:attachment ri:filename="screenshot.png" ri:version-at-save="1"/>'
            "<ac:caption><p>Dialog in VS Code to create a new branch</p></ac:caption>"
            "</ac:image>"
        )
        result = _parse_image_captions(storage)
        assert result == {"screenshot.png": "Dialog in VS Code to create a new branch"}

    def test_caption_with_attributes_extracted(self) -> None:
        from confluence_markdown_exporter.confluence import _parse_image_captions

        storage = (
            '<ac:image ac:align="center" ac:width="544">'
            '<ri:attachment ri:filename="TissueMap.png" ri:version-at-save="1"/>'
            '<ac:caption ac:local-id="6a5ac213-73a0">'
            "<p>Exemplary Tissue Map</p>"
            "</ac:caption>"
            "</ac:image>"
        )
        result = _parse_image_captions(storage)
        assert result == {"TissueMap.png": "Exemplary Tissue Map"}

    def test_image_without_caption_excluded(self) -> None:
        from confluence_markdown_exporter.confluence import _parse_image_captions

        storage = (
            "<ac:image>"
            '<ri:attachment ri:filename="no-caption.png"/>'
            "</ac:image>"
        )
        assert _parse_image_captions(storage) == {}

    def test_multiple_images_mixed(self) -> None:
        from confluence_markdown_exporter.confluence import _parse_image_captions

        storage = (
            "<ac:image>"
            '<ri:attachment ri:filename="a.png"/>'
            "<ac:caption><ac:plain-text-body>"
            "<![CDATA[Caption A]]></ac:plain-text-body></ac:caption>"
            "</ac:image>"
            "<ac:image>"
            '<ri:attachment ri:filename="b.png"/>'
            "</ac:image>"
            "<ac:image>"
            '<ri:attachment ri:filename="c.jpg"/>'
            "<ac:caption><ac:plain-text-body>"
            "<![CDATA[Caption C]]></ac:plain-text-body></ac:caption>"
            "</ac:image>"
        )
        result = _parse_image_captions(storage)
        assert result == {"a.png": "Caption A", "c.jpg": "Caption C"}

    def test_empty_storage_returns_empty(self) -> None:
        from confluence_markdown_exporter.confluence import _parse_image_captions

        assert _parse_image_captions("") == {}


class TestImageCaptionsInConvertImg:
    """convert_img renders captions as italics below the image when image_captions is enabled."""

    def test_caption_rendered_as_italic_below_image(self) -> None:
        att = _make_attachment("111", "abc-guid-111", title="testbild.jpeg")
        storage = (
            "<ac:image>"
            '<ri:attachment ri:filename="testbild.jpeg"/>'
            "<ac:caption>"
            "<ac:plain-text-body><![CDATA[My Caption]]></ac:plain-text-body>"
            "</ac:caption>"
            "</ac:image>"
        )
        page = _make_page(
            body='<img data-media-id="abc-guid-111" src="/download/testbild.jpeg" alt="">',
            body_export="",
            attachments=[att],
            body_storage=storage,
        )
        _att_path = "{space_name}/attachments/{attachment_file_id}{attachment_extension}"
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_href = "relative"
            s.export.attachment_path = _att_path
            s.export.page_href = "relative"
            s.export.page_path = "{space_name}/{page_title}.md"
            s.export.image_captions = True
            s.export.include_document_title = False
            s.export.page_breadcrumbs = False
            conv = Page.Converter(page)
            result = conv.convert(page.body).strip()
        assert "![](" in result  # image with empty alt
        assert "*My Caption*" in result
        lines = result.splitlines()
        img_line = next(i for i, line in enumerate(lines) if "![](" in line)
        assert lines[img_line + 1] == "*My Caption*"

    def test_caption_disabled_preserves_original_alt(self) -> None:
        att = _make_attachment("111", "abc-guid-111", title="testbild.jpeg")
        storage = (
            "<ac:image>"
            '<ri:attachment ri:filename="testbild.jpeg"/>'
            "<ac:caption>"
            "<ac:plain-text-body><![CDATA[My Caption]]></ac:plain-text-body>"
            "</ac:caption>"
            "</ac:image>"
        )
        page = _make_page(
            body='<img data-media-id="abc-guid-111" src="/download/testbild.jpeg" alt="">',
            body_export="",
            attachments=[att],
            body_storage=storage,
        )
        _att_path = "{space_name}/attachments/{attachment_file_id}{attachment_extension}"
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_href = "relative"
            s.export.attachment_path = _att_path
            s.export.page_href = "relative"
            s.export.page_path = "{space_name}/{page_title}.md"
            s.export.image_captions = False
            s.export.include_document_title = False
            s.export.page_breadcrumbs = False
            conv = Page.Converter(page)
            result = conv.convert(page.body).strip()
        assert "My Caption" not in result


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


_DETAILS_HTML = """
<div data-macro-name="details">
    <table>
        <tr><th>Author</th><td>John Doe</td></tr>
        <tr><th>Status</th><td>Active</td></tr>
    </table>
</div>
"""


class TestPagePropertiesFormat:
    """Page Properties macro renders according to page_properties_format setting."""

    def _converter(self) -> Page.Converter:
        return Page.Converter(MockPage())

    def test_frontmatter_removes_table(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_format = "frontmatter"
            result = converter.convert(_DETAILS_HTML)
        assert "Author" not in result
        assert "author" in converter.page_properties
        assert converter.page_properties["author"] == "John Doe"

    def test_table_keeps_table_no_properties(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_format = "table"
            result = converter.convert(_DETAILS_HTML)
        assert "Author" in result
        assert converter.page_properties == {}

    def test_frontmatter_and_table_keeps_both(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_format = "frontmatter_and_table"
            result = converter.convert(_DETAILS_HTML)
        assert "Author" in result
        assert "author" in converter.page_properties
        assert converter.page_properties["author"] == "John Doe"

    def test_dataview_inline_field(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_format = "dataview-inline-field"
            result = converter.convert(_DETAILS_HTML)
        assert "Author:: John Doe" in result
        assert "Status:: Active" in result
        assert "|" not in result
        assert converter.page_properties == {}

    def test_meta_bind_view_fields(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_format = "meta-bind-view-fields"
            result = converter.convert(_DETAILS_HTML)
        assert "| Author | `VIEW[{author}][text]` |" in result
        assert "| Status | `VIEW[{status}][text]` |" in result
        assert "author" in converter.page_properties
        assert "status" in converter.page_properties

    def test_duplicate_keys_get_numeric_suffix(self) -> None:
        html = """
        <div data-macro-name="details">
            <table>
                <tr><th>Status</th><td>Draft</td></tr>
                <tr><th>Status</th><td>Review</td></tr>
                <tr><th>Status</th><td>Final</td></tr>
            </table>
        </div>
        """
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_format = "frontmatter"
            converter.convert(html)
        assert converter.page_properties["status"] == "Draft"
        assert converter.page_properties["status_2"] == "Review"
        assert converter.page_properties["status_3"] == "Final"

    def test_duplicate_keys_in_inline_fields(self) -> None:
        html = """
        <div data-macro-name="details">
            <table>
                <tr><th>Tag</th><td>foo</td></tr>
                <tr><th>Tag</th><td>bar</td></tr>
            </table>
        </div>
        """
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_format = "dataview-inline-field"
            result = converter.convert(html)
        assert "Tag:: foo" in result
        assert "Tag 2:: bar" in result


class TestPagePropertiesMigration:
    """Legacy page_properties_as_front_matter bool migrates to page_properties_format."""

    def test_old_true_maps_to_frontmatter(self) -> None:
        from confluence_markdown_exporter.utils.app_data_store import ExportConfig

        config = ExportConfig.model_validate({"page_properties_as_front_matter": True})
        assert config.page_properties_format == "frontmatter"

    def test_old_false_maps_to_table(self) -> None:
        from confluence_markdown_exporter.utils.app_data_store import ExportConfig

        config = ExportConfig.model_validate({"page_properties_as_front_matter": False})
        assert config.page_properties_format == "table"

    def test_new_field_takes_precedence_over_old(self) -> None:
        from confluence_markdown_exporter.utils.app_data_store import ExportConfig

        config = ExportConfig.model_validate(
            {"page_properties_as_front_matter": True, "page_properties_format": "table"}
        )
        assert config.page_properties_format == "table"

    def test_default_is_frontmatter_and_table(self) -> None:
        from confluence_markdown_exporter.utils.app_data_store import ExportConfig

        config = ExportConfig()
        assert config.page_properties_format == "frontmatter_and_table"


class TestPagePropertiesReportDataview:
    """Page Properties Report macro can be exported as a Dataview DQL query."""

    _REPORT_HTML = (
        '<table class="aui metadata-summary-macro null"'
        ' data-cql=\'label = "tool-validation" and parent = "42"\''
        ' data-current-content-id="42"'
        ' data-current-space-key="TS"'
        ' data-first-column-heading="Title"'
        ' data-headings="Tool Version,Approved for Use"'
        ' data-sort-by="Title"'
        ' data-reverse-sort="false">'
        "</table>"
    )

    _BODY_EXPORT = (
        '<table class="aui metadata-summary-macro null"'
        ' data-cql=\'label = "tool-validation" and parent = "42"\''
        ">"
        "<tr><th>Title</th><th>Tool Version</th><th>Approved for Use</th></tr>"
        "<tr><td>Page A</td><td>1.0</td><td>Yes</td></tr>"
        "</table>"
    )

    class _MockPageWithExport:
        def __init__(self, body_export: str = "") -> None:
            from pathlib import Path

            self.id = 42
            self.title = "Test Page"
            self.html = ""
            self.labels: list = []
            self.ancestors: list = []
            self.body_export = body_export
            self.export_path = Path("Test Space/Test Page/Test Page.md")

        def get_attachment_by_file_id(self, file_id: str) -> None:
            return None

    def test_dataview_output_contains_table_clause(self) -> None:
        page = self._MockPageWithExport(body_export=self._BODY_EXPORT)
        converter = Page.Converter(page)
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_report_format = "dataview"
            result = converter.convert(self._REPORT_HTML)
        assert "```dataview" in result
        expected_cols = 'tool_version AS "Tool Version", approved_for_use AS "Approved for Use"'
        assert f"TABLE {expected_cols}" in result

    def test_dataview_output_contains_from_clause(self) -> None:
        page = self._MockPageWithExport(body_export=self._BODY_EXPORT)
        converter = Page.Converter(page)
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_report_format = "dataview"
            result = converter.convert(self._REPORT_HTML)
        assert 'FROM "Test Space/Test Page"' in result

    def test_dataview_output_contains_label_in_from_clause(self) -> None:
        page = self._MockPageWithExport(body_export=self._BODY_EXPORT)
        converter = Page.Converter(page)
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_report_format = "dataview"
            result = converter.convert(self._REPORT_HTML)
        assert "#tool-validation" in result

    def test_dataview_output_contains_sort_clause(self) -> None:
        page = self._MockPageWithExport(body_export=self._BODY_EXPORT)
        converter = Page.Converter(page)
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_report_format = "dataview"
            result = converter.convert(self._REPORT_HTML)
        assert "SORT title ASC" in result

    def test_frozen_table_when_format_is_frozen(self) -> None:
        page = self._MockPageWithExport(body_export=self._BODY_EXPORT)
        converter = Page.Converter(page)
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_report_format = "frozen"
            result = converter.convert(self._REPORT_HTML)
        assert "```dataview" not in result
        assert "Page A" in result


class TestAttachmentsExportFlag:
    """Tests for the export.attachments_export setting."""

    def _make_attachment_mock(self, att_id: str = "att-1", version: int = 3) -> MagicMock:
        att = MagicMock()
        att.id = att_id
        att.version.number = version
        att.export_path = Path(f"attachments/{att_id}.bin")
        return att

    def _make_page_mock(self, attachments: list) -> MagicMock:
        page = MagicMock()
        page.id = 42
        page._attachments_for_export.return_value = attachments
        return page

    def test_default_true_exports_attachments(self, tmp_path: Path) -> None:
        """With attachments_export=True (default), attachments are downloaded."""
        att = self._make_attachment_mock()
        page = self._make_page_mock([att])

        with (
            patch("confluence_markdown_exporter.confluence.settings") as mock_settings,
            patch(
                "confluence_markdown_exporter.confluence.LockfileManager"
            ) as mock_lockfile,
            patch("confluence_markdown_exporter.confluence.get_stats"),
        ):
            mock_settings.export.attachments_export = True
            mock_settings.export.output_path = tmp_path
            mock_lockfile.get_page_attachment_entries.return_value = {}

            result = Page.export_attachments(page)

        att.export.assert_called_once()
        assert "att-1" in result

    def test_disabled_skips_download_and_lockfile(self) -> None:
        """With attachments_export=False, no download and no lockfile lookup."""
        att = self._make_attachment_mock()
        page = self._make_page_mock([att])

        with (
            patch("confluence_markdown_exporter.confluence.settings") as mock_settings,
            patch(
                "confluence_markdown_exporter.confluence.LockfileManager"
            ) as mock_lockfile,
            patch("confluence_markdown_exporter.confluence.get_stats"),
        ):
            mock_settings.export.attachments_export = False

            result = Page.export_attachments(page)

        assert result == {}
        att.export.assert_not_called()
        mock_lockfile.get_page_attachment_entries.assert_not_called()

    def test_metadata_still_populated_when_disabled(self) -> None:
        """Page.from_json populates Page.attachments even when downloads are disabled.

        Guards against future scope creep that would gate metadata loading on
        the same flag — body image and file links must keep resolving.
        """
        base_url = "https://example.atlassian.net"
        fake_space = Space(
            base_url=base_url, key="K", name="Space", description="", homepage=None
        )
        fake_user = User(
            account_id="", username="", display_name="", public_name="", email=""
        )
        fake_version = Version(number=1, by=fake_user, when="", friendly_when="")
        fake_attachment = Attachment(
            base_url=base_url,
            id="att-1",
            title="file.png",
            space=fake_space,
            ancestors=[],
            version=fake_version,
            file_size=10,
            media_type="image/png",
            media_type_description="",
            file_id="file-id-1",
            collection_name="",
            download_link="",
            comment="",
        )
        page_data = {
            "id": 42,
            "title": "Test",
            "_expandable": {"space": "/rest/api/space/K"},
            "body": {
                "view": {"value": ""},
                "export_view": {"value": ""},
                "editor2": {"value": ""},
            },
            "metadata": {"labels": {"results": []}},
            "ancestors": [],
            "version": {},
        }

        with (
            patch(
                "confluence_markdown_exporter.confluence.Attachment.from_page_id",
                return_value=[fake_attachment],
            ),
            patch(
                "confluence_markdown_exporter.confluence.Space.from_key",
                return_value=fake_space,
            ),
            patch("confluence_markdown_exporter.confluence.settings") as mock_settings,
        ):
            mock_settings.export.attachments_export = False

            page = Page.from_json(page_data, base_url)

        assert len(page.attachments) == 1
        assert page.attachments[0].id == "att-1"
