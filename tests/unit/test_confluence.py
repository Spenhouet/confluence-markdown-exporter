"""Unit tests for confluence module URL resolution."""

from __future__ import annotations

import types
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
        self.web_url = ""
        self.tiny_url = ""
        self.labels = []
        self.ancestors = []
        self.space = MagicMock()
        self.space.key = "TEST"
        self.version = MagicMock()
        self.version.number = 1
        self.version.when = ""
        self.version.by = MagicMock()
        self.version.by.display_name = ""

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
            s.export.attachments_export = "referenced"
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
            s.export.attachments_export = "referenced"
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
            s.export.attachments_export = "referenced"
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
            s.export.attachments_export = "referenced"
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
            s.export.attachments_export = "referenced"
            result = page._attachments_for_export()
        assert att in result

    def test_unreferenced_attachment_excluded(self) -> None:
        att = _make_attachment("77777", "xyz-guid-77", title="unused.png")
        page = _make_page(body="no references here", body_export="", attachments=[att])
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachments_export = "referenced"
            result = page._attachments_for_export()
        assert att not in result

    def test_attachments_export_all_returns_all(self) -> None:
        att1 = _make_attachment("111", "aaa")
        att2 = _make_attachment("222", "bbb", title="other.svg", media_type="image/svg+xml")
        page = _make_page(body="", body_export="", attachments=[att1, att2])
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachments_export = "all"
            result = page._attachments_for_export()
        assert result == [att1, att2]


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

    def test_referenced_default_exports_attachments(self, tmp_path: Path) -> None:
        """With attachments_export='referenced' (default), attachments are downloaded."""
        att = self._make_attachment_mock()
        page = self._make_page_mock([att])

        with (
            patch("confluence_markdown_exporter.confluence.settings") as mock_settings,
            patch(
                "confluence_markdown_exporter.confluence.LockfileManager"
            ) as mock_lockfile,
            patch("confluence_markdown_exporter.confluence.get_stats"),
        ):
            mock_settings.export.attachments_export = "referenced"
            mock_settings.export.output_path = tmp_path
            mock_lockfile.get_page_attachment_entries.return_value = {}

            result = Page.export_attachments(page)

        att.export.assert_called_once()
        assert "att-1" in result

    def test_disabled_skips_download_and_lockfile(self) -> None:
        """With attachments_export='disabled', no download and no lockfile lookup."""
        att = self._make_attachment_mock()
        page = self._make_page_mock([att])

        with (
            patch("confluence_markdown_exporter.confluence.settings") as mock_settings,
            patch(
                "confluence_markdown_exporter.confluence.LockfileManager"
            ) as mock_lockfile,
            patch("confluence_markdown_exporter.confluence.get_stats"),
        ):
            mock_settings.export.attachments_export = "disabled"

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
            mock_settings.export.attachments_export = "disabled"

            page = Page.from_json(page_data, base_url)

        assert len(page.attachments) == 1
        assert page.attachments[0].id == "att-1"


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


class TestCellHighlightConversion:
    """Confluence `data-highlight-colour` on <td>/<th> must become <mark> wrappers."""

    def test_td_hex_attribute_wraps_in_mark(self, converter: Page.Converter) -> None:
        html = (
            '<table><tbody><tr>'
            '<td data-highlight-colour="#fff0b3"><p>2</p></td>'
            '</tr></tbody></table>'
        )
        result = converter.convert(html)
        assert '<mark style="background: #fff0b3;">2</mark>' in result

    def test_th_hex_attribute_wraps_in_mark(self, converter: Page.Converter) -> None:
        html = (
            '<table><tbody><tr>'
            '<th data-highlight-colour="#ffd5d2"><p><strong>P / S</strong></p></th>'
            '</tr></tbody></table>'
        )
        result = converter.convert(html)
        assert '<mark style="background: #ffd5d2;">**P / S**</mark>' in result

    def test_default_header_gray_not_wrapped(self, converter: Page.Converter) -> None:
        """Confluence's default <th> background (#f4f5f7) is not user-chosen — skip."""
        html = (
            '<table><tbody><tr>'
            '<th data-highlight-colour="#f4f5f7"><p><strong>P / S</strong></p></th>'
            '<td data-highlight-colour="#f4f5f7"><p><strong>P5</strong></p></td>'
            '</tr></tbody></table>'
        )
        result = converter.convert(html)
        assert "<mark" not in result

    def test_transparent_attribute_not_wrapped(self, converter: Page.Converter) -> None:
        html = (
            '<table><tbody><tr>'
            '<td data-highlight-colour="transparent"><p>plain</p></td>'
            '</tr></tbody></table>'
        )
        result = converter.convert(html)
        assert "<mark" not in result
        assert "plain" in result

    def test_missing_attribute_not_wrapped(self, converter: Page.Converter) -> None:
        html = (
            '<table><tbody><tr><td><p>plain</p></td></tr></tbody></table>'
        )
        result = converter.convert(html)
        assert "<mark" not in result
        assert "plain" in result

    def test_invalid_hex_not_wrapped(self, converter: Page.Converter) -> None:
        html = (
            '<table><tbody><tr>'
            '<td data-highlight-colour="not-a-color"><p>x</p></td>'
            '</tr></tbody></table>'
        )
        result = converter.convert(html)
        assert "<mark" not in result

    def test_empty_cell_with_highlight_renders_nbsp(self, converter: Page.Converter) -> None:
        html = (
            '<table><tbody><tr>'
            '<td data-highlight-colour="#ff8f73"></td>'
            '</tr></tbody></table>'
        )
        result = converter.convert(html)
        assert '<mark style="background: #ff8f73;">&nbsp;</mark>' in result

    def test_setting_disabled_returns_plain_text(self, converter: Page.Converter) -> None:
        html = (
            '<table><tbody><tr>'
            '<td data-highlight-colour="#fff0b3"><p>2</p></td>'
            '</tr></tbody></table>'
        )
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.convert_text_highlights = False
            s.export.convert_font_colors = True
            s.export.convert_status_badges = True
            result = converter.convert(html)
        assert "<mark" not in result
        assert "2" in result


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
        assert "| **Author** | `VIEW[{author}][text(renderMarkdown)]` |" in result
        assert "| **Status** | `VIEW[{status}][text(renderMarkdown)]` |" in result
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


class TestConfluenceUrlInFrontmatter:
    """Confluence page URLs render to YAML front matter according to the setting."""

    _WEBUI = "https://example.atlassian.net/wiki/spaces/TEST/pages/123/Test+Page"
    _TINYUI = "https://example.atlassian.net/wiki/x/AbCdEf"

    def _converter(self, *, with_urls: bool = True) -> Page.Converter:
        page = MockPage()
        if with_urls:
            page.web_url = self._WEBUI
            page.tiny_url = self._TINYUI
        return Page.Converter(page)

    def test_get_web_url_combines_base_and_webui(self) -> None:
        from confluence_markdown_exporter.confluence import _get_web_url

        data = {
            "_links": {
                "base": "https://example.atlassian.net/wiki",
                "webui": "/spaces/TEST/pages/123/Test+Page",
            }
        }
        assert _get_web_url(data) == self._WEBUI

    def test_get_tiny_url_combines_base_and_tinyui(self) -> None:
        from confluence_markdown_exporter.confluence import _get_tiny_url

        data = {
            "_links": {
                "base": "https://example.atlassian.net/wiki",
                "tinyui": "/x/AbCdEf",
            }
        }
        assert _get_tiny_url(data) == self._TINYUI

    def test_helpers_strip_redundant_separators(self) -> None:
        from confluence_markdown_exporter.confluence import _get_web_url

        data = {
            "_links": {
                "base": "https://example.atlassian.net/wiki/",
                "webui": "/spaces/TEST/pages/123/Test+Page",
            }
        }
        assert _get_web_url(data) == self._WEBUI

    def test_helpers_return_empty_when_links_missing(self) -> None:
        from confluence_markdown_exporter.confluence import _get_tiny_url
        from confluence_markdown_exporter.confluence import _get_web_url

        assert _get_web_url({}) == ""
        assert _get_tiny_url({}) == ""

    def test_helpers_return_empty_when_links_not_dict(self) -> None:
        from confluence_markdown_exporter.confluence import _get_tiny_url
        from confluence_markdown_exporter.confluence import _get_web_url

        assert _get_web_url({"_links": "broken"}) == ""
        assert _get_tiny_url({"_links": None}) == ""

    def test_helpers_return_empty_when_base_or_rel_missing(self) -> None:
        from confluence_markdown_exporter.confluence import _get_web_url

        assert _get_web_url({"_links": {"base": "https://example.com"}}) == ""
        assert _get_web_url({"_links": {"webui": "/spaces/TEST"}}) == ""

    def test_frontmatter_contains_webui_url_when_mode_webui(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "webui"
            result = converter.front_matter
        assert f"confluence_webui_url: {self._WEBUI}" in result
        assert "confluence_tinyui_url" not in result

    def test_frontmatter_contains_tinyui_url_when_mode_tinyui(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "tinyui"
            result = converter.front_matter
        assert f"confluence_tinyui_url: {self._TINYUI}" in result
        assert "confluence_webui_url" not in result

    def test_frontmatter_contains_both_when_mode_both(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "both"
            result = converter.front_matter
        assert f"confluence_webui_url: {self._WEBUI}" in result
        assert f"confluence_tinyui_url: {self._TINYUI}" in result

    def test_frontmatter_omits_urls_when_mode_none(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "none"
            result = converter.front_matter
        assert "confluence_webui_url" not in result
        assert "confluence_tinyui_url" not in result

    def test_frontmatter_skips_when_url_value_is_empty(self) -> None:
        converter = self._converter(with_urls=False)
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "both"
            result = converter.front_matter
        assert "confluence_webui_url" not in result
        assert "confluence_tinyui_url" not in result

    def test_macro_value_takes_precedence_over_extracted_url(self) -> None:
        converter = self._converter()
        converter.page_properties["confluence_webui_url"] = "manual-override"
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "webui"
            result = converter.front_matter
        assert "confluence_webui_url: manual-override" in result
        assert self._WEBUI not in result


class TestPageMetadataInFrontmatter:
    """Page metadata fields render to YAML front matter according to the setting."""

    def _make_page(self, *, display_name: str = "Alex Johnson") -> MockPage:
        page = MockPage()
        page.id = 123
        space = MagicMock()
        space.key = "TEAM"
        page.space = space
        version = MagicMock()
        version.when = "2026-04-12T10:34:00.000+02:00"
        version.number = 7
        version.by = MagicMock()
        version.by.display_name = display_name
        page.version = version
        return page

    def _converter(self, **kwargs: object) -> Page.Converter:
        return Page.Converter(self._make_page(**kwargs))

    def test_default_disabled_writes_no_metadata(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "none"
            s.export.page_metadata_in_frontmatter = False
            result = converter.front_matter
        assert "confluence_page_id" not in result
        assert "confluence_space_key" not in result
        assert "confluence_last_modified" not in result
        assert "confluence_last_modified_by" not in result
        assert "confluence_version" not in result

    def test_enabled_writes_all_five_keys(self) -> None:
        converter = self._converter()
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "none"
            s.export.page_metadata_in_frontmatter = True
            result = converter.front_matter
        assert "confluence_page_id: '123'" in result
        assert "confluence_space_key: TEAM" in result
        assert "confluence_last_modified: '2026-04-12T10:34:00.000+02:00'" in result
        assert "confluence_last_modified_by: Alex Johnson" in result
        assert "confluence_version: 7" in result
        assert "confluence_version: '7'" not in result

    def test_macro_precedence_for_page_id(self) -> None:
        converter = self._converter()
        converter.page_properties["confluence_page_id"] = "macro-override"
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "none"
            s.export.page_metadata_in_frontmatter = True
            result = converter.front_matter
        assert "confluence_page_id: macro-override" in result
        assert "confluence_page_id: '123'" not in result

    def test_empty_display_name_skipped(self) -> None:
        converter = self._converter(display_name="")
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.confluence_url_in_frontmatter = "none"
            s.export.page_metadata_in_frontmatter = True
            result = converter.front_matter
        assert "confluence_last_modified_by" not in result
        assert "confluence_page_id: '123'" in result
        assert "confluence_space_key: TEAM" in result
        assert "confluence_last_modified" in result
        assert "confluence_version: 7" in result


class TestInlineCommentsFrontMatter:
    """Pin the YAML front matter keys written into *.comments.md sidecars."""

    def test_front_matter_uses_confluence_prefix(self) -> None:
        page = MockPage()
        page.id = 123
        page.title = "My Page"
        page.space = MagicMock()
        page.space.key = "TEAM"
        page.base_url = "https://example.atlassian.net"
        page.export_path = Path("TEAM/My Page.md")
        page._marked_texts = {"ref-1": "marked excerpt"}
        page._COMMENT_TITLE_MAX_LEN = Page._COMMENT_TITLE_MAX_LEN.default
        page._fetch_inline_comments = lambda: [
            {
                "id": "c1",
                "extensions": {"inlineProperties": {"markerRef": "ref-1"}},
                "history": {
                    "createdBy": {"displayName": "Alice"},
                    "createdDate": "2026-04-01T10:00:00Z",
                },
                "body": {"view": {"value": "<p>nice</p>"}},
            }
        ]
        page._fetch_page_comments = list
        page._fetch_comment_replies = lambda _cid: []
        page._render_inline_comments = types.MethodType(Page._render_inline_comments, page)
        page._render_page_comments = types.MethodType(Page._render_page_comments, page)

        with (
            patch("confluence_markdown_exporter.confluence.save_file") as mock_save,
            patch("confluence_markdown_exporter.confluence.settings") as s,
        ):
            s.export.output_path = Path("out")
            s.export.comments_export = "inline"
            Page.export_comments_sidecar(page)

        assert mock_save.called
        content = mock_save.call_args[0][1]

        # New keys with correct YAML form
        assert "confluence_page_id: '123'" in content
        assert 'confluence_page_title: "My Page"' in content
        assert (
            'confluence_webui_url: "https://example.atlassian.net'
            '/wiki/spaces/TEAM/pages/123"' in content
        )

        # Regression guard: old keys must not reappear
        assert "\npage_id:" not in content
        assert "\npage_title:" not in content
        assert "\nsource:" not in content


def _make_comments_page(
    *,
    inline_comments: list[dict] | None = None,
    page_comments: list[dict] | None = None,
    replies: dict[str, list[dict]] | None = None,
    marked_texts: dict[str, str] | None = None,
) -> MockPage:
    page = MockPage()
    page.id = 123
    page.title = "My Page"
    page.space = MagicMock()
    page.space.key = "TEAM"
    page.base_url = "https://example.atlassian.net"
    page.export_path = Path("TEAM/My Page.md")
    page._marked_texts = marked_texts or {}
    page._COMMENT_TITLE_MAX_LEN = Page._COMMENT_TITLE_MAX_LEN.default
    page._fetch_inline_comments = lambda: list(inline_comments or [])
    page._fetch_page_comments = lambda: list(page_comments or [])
    replies_map = replies or {}
    page._fetch_comment_replies = lambda cid: list(replies_map.get(cid, []))
    page._render_inline_comments = types.MethodType(Page._render_inline_comments, page)
    page._render_page_comments = types.MethodType(Page._render_page_comments, page)
    return page


def _run_export_capturing_save(page: MockPage, mode: str) -> MagicMock:
    with (
        patch("confluence_markdown_exporter.confluence.save_file") as mock_save,
        patch("confluence_markdown_exporter.confluence.settings") as s,
    ):
        s.export.output_path = Path("out")
        s.export.comments_export = mode
        Page.export_comments_sidecar(page)
    return mock_save


def _inline_comment(
    ref: str = "ref-1",
    body: str = "<p>nice</p>",
    cid: str = "c1",
    author: str = "Alice",
) -> dict:
    return {
        "id": cid,
        "extensions": {"inlineProperties": {"markerRef": ref}},
        "history": {
            "createdBy": {"displayName": author},
            "createdDate": "2026-04-01T10:00:00Z",
        },
        "body": {"view": {"value": body}},
    }


def _page_comment(
    cid: str = "p1",
    body: str = "<p>discussion body</p>",
    author: str = "Bob",
    *,
    resolved: bool = False,
) -> dict:
    return {
        "id": cid,
        "extensions": {"resolution": {"status": "resolved" if resolved else "open"}},
        "history": {
            "createdBy": {"displayName": author},
            "createdDate": "2026-04-02T11:00:00Z",
        },
        "body": {"view": {"value": body}},
    }


class TestPageCommentsSidecarBody:
    """Sidecar rendering for page-level (footer) and combined comments."""

    def test_only_footer_writes_only_page_section(self) -> None:
        page = _make_comments_page(page_comments=[_page_comment()])
        save = _run_export_capturing_save(page, "footer")
        assert save.called
        content = save.call_args[0][1]
        assert "## Page comments" in content
        assert "## Inline comments" not in content
        assert "discussion body" in content
        assert "**Bob** · 2026-04-02" in content

    def test_all_writes_both_sections_inline_first(self) -> None:
        page = _make_comments_page(
            inline_comments=[_inline_comment()],
            page_comments=[_page_comment()],
            marked_texts={"ref-1": "marked excerpt"},
        )
        save = _run_export_capturing_save(page, "all")
        assert save.called
        content = save.call_args[0][1]
        assert "## Inline comments" in content
        assert "## Page comments" in content
        assert content.index("## Inline comments") < content.index("## Page comments")

    def test_none_writes_no_file(self) -> None:
        page = _make_comments_page(
            inline_comments=[_inline_comment()],
            page_comments=[_page_comment()],
        )
        save = _run_export_capturing_save(page, "none")
        assert save.called is False

    def test_inline_only_omits_page_section(self) -> None:
        page = _make_comments_page(
            inline_comments=[_inline_comment()],
            page_comments=[_page_comment()],
            marked_texts={"ref-1": "marked excerpt"},
        )
        save = _run_export_capturing_save(page, "inline")
        assert save.called
        content = save.call_args[0][1]
        assert "## Inline comments" in content
        assert "## Page comments" not in content

    def test_page_comment_title_falls_back_to_comment_id(self) -> None:
        page = _make_comments_page(
            page_comments=[_page_comment(cid="abcdef1234567", body="")],
        )
        save = _run_export_capturing_save(page, "footer")
        assert save.called
        content = save.call_args[0][1]
        assert "### Comment abcdef12" in content

    def test_page_comment_replies_render_under_parent(self) -> None:
        replies = {
            "p1": [
                {
                    "id": "r1",
                    "history": {
                        "createdBy": {"displayName": "Carol"},
                        "createdDate": "2026-04-03T11:00:00Z",
                    },
                    "body": {"view": {"value": "<p>reply one</p>"}},
                },
                {
                    "id": "r2",
                    "history": {
                        "createdBy": {"displayName": "Dave"},
                        "createdDate": "2026-04-03T12:00:00Z",
                    },
                    "body": {"view": {"value": "<p>reply two</p>"}},
                },
            ]
        }
        page = _make_comments_page(
            page_comments=[_page_comment(cid="p1", body="<p>parent body</p>", author="Bob")],
            replies=replies,
        )
        save = _run_export_capturing_save(page, "footer")
        assert save.called
        content = save.call_args[0][1]
        assert content.index("Bob") < content.index("Carol") < content.index("Dave")
        assert "reply one" in content
        assert "reply two" in content

    def test_fetch_page_comments_filters_resolved(self) -> None:
        page = MockPage()
        page.id = 123
        page.base_url = "https://example.atlassian.net"

        client = MagicMock()
        client.get_page_comments.return_value = {
            "results": [
                _page_comment(cid="open1", body="<p>open one</p>"),
                _page_comment(cid="resolved1", body="<p>resolved one</p>", resolved=True),
                _page_comment(cid="open2", body="<p>open two</p>"),
            ],
            "_links": {},
        }

        with patch(
            "confluence_markdown_exporter.confluence.get_thread_confluence",
            return_value=client,
        ):
            results = Page._fetch_page_comments(page)

        ids = [c["id"] for c in results]
        assert ids == ["open1", "open2"]


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

    def test_dataview_from_clause_with_current_content_ancestor(self) -> None:
        html = (
            '<table class="aui metadata-summary-macro null"'
            " data-cql='label = \"tool\" and ancestor = currentContent()'"
            ' data-current-content-id="99"'
            ' data-current-space-key="TS"'
            ' data-first-column-heading="Name"'
            ' data-headings="Vendor"'
            ' data-sort-by="Name"'
            ' data-reverse-sort="false">'
            "</table>"
        )
        page = self._MockPageWithExport(body_export="")
        converter = Page.Converter(page)
        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.page_properties_report_format = "dataview"
            result = converter.convert(html)
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


class TestAttachmentTemplateVars:
    """`attachment_file_id` falls back to the content id when fileId is empty."""

    def test_cloud_style_keeps_file_id(self) -> None:
        """Cloud attachments expose the GUID fileId verbatim."""
        attachment = _make_attachment("content-456", "cloud-guid-123")
        assert attachment._template_vars["attachment_file_id"] == "cloud-guid-123"

    def test_dc_style_falls_back_to_content_id(self) -> None:
        """Data Center / Server attachments fall back to the content id."""
        attachment = _make_attachment("content-456", "")
        assert attachment._template_vars["attachment_file_id"] == "content-456"

    def test_two_dc_attachments_get_distinct_paths(self) -> None:
        """Two DC attachments with the same extension must not collide."""
        att1 = _make_attachment("123", "")
        att2 = _make_attachment("124", "")

        with patch("confluence_markdown_exporter.confluence.settings") as mock_settings:
            mock_settings.export.attachment_path = (
                "{space_name}/attachments/{attachment_file_id}{attachment_extension}"
            )
            path1 = att1.export_path
            path2 = att2.export_path

        assert path1 != path2


class TestWikiLinkDisambiguation:
    """Wiki page links use a vault-relative path when titles collide across spaces."""

    def _make_target_page(self, page_id: int, title: str, space_key: str) -> Page:
        space = Space(
            base_url="https://example.com",
            key=space_key,
            name=space_key,
            description="",
            homepage=0,
        )
        version = Version(
            number=1,
            by=User(
                account_id="u1",
                display_name="User",
                username="user",
                public_name="",
                email="",
            ),
            when="2024-01-01T00:00:00Z",
            friendly_when="Jan 1",
        )
        return Page(
            base_url="https://example.com",
            id=page_id,
            title=title,
            space=space,
            ancestors=[],
            version=version,
            body="",
            body_export="",
            editor2="",
            body_storage="",
            labels=[],
            attachments=[],
        )

    def test_unique_title_emits_short_wiki_link(self) -> None:
        from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry

        PageTitleRegistry.reset()
        target = self._make_target_page(101, "Unique Page", "ALPHA")
        PageTitleRegistry.register(target.id, target.title)

        source = _make_page(body="", body_export="", attachments=[])

        with (
            patch("confluence_markdown_exporter.confluence.Page.from_id", return_value=target),
            patch("confluence_markdown_exporter.confluence.settings") as s,
        ):
            s.export.page_href = "wiki"
            s.export.page_path = "{space_name}/{page_title}.md"
            conv = Page.Converter(source)
            html = '<a data-linked-resource-type="page" data-linked-resource-id="101">x</a>'
            result = conv.convert(html).strip()

        PageTitleRegistry.reset()
        assert result == "[[Unique Page]]"

    def test_colliding_title_emits_path_qualified_wiki_link(self) -> None:
        from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry

        PageTitleRegistry.reset()
        target_alpha = self._make_target_page(201, "Shared Title", "ALPHA")
        target_beta = self._make_target_page(202, "Shared Title", "BETA")
        PageTitleRegistry.register(target_alpha.id, target_alpha.title)
        PageTitleRegistry.register(target_beta.id, target_beta.title)

        source = _make_page(body="", body_export="", attachments=[])

        with (
            patch(
                "confluence_markdown_exporter.confluence.Page.from_id",
                return_value=target_alpha,
            ),
            patch("confluence_markdown_exporter.confluence.settings") as s,
        ):
            s.export.page_href = "wiki"
            s.export.page_path = "{space_name}/{page_title}.md"
            conv = Page.Converter(source)
            html = '<a data-linked-resource-type="page" data-linked-resource-id="201">x</a>'
            result = conv.convert(html).strip()

        PageTitleRegistry.reset()
        assert result == "[[ALPHA/Shared Title|Shared Title]]"

    def test_relative_link_unaffected(self) -> None:
        from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry

        PageTitleRegistry.reset()
        target_alpha = self._make_target_page(201, "Shared Title", "ALPHA")
        target_beta = self._make_target_page(202, "Shared Title", "BETA")
        PageTitleRegistry.register(target_alpha.id, target_alpha.title)
        PageTitleRegistry.register(target_beta.id, target_beta.title)

        source = _make_page(body="", body_export="", attachments=[])

        with (
            patch(
                "confluence_markdown_exporter.confluence.Page.from_id",
                return_value=target_alpha,
            ),
            patch("confluence_markdown_exporter.confluence.settings") as s,
        ):
            s.export.page_href = "relative"
            s.export.page_path = "{space_name}/{page_title}.md"
            conv = Page.Converter(source)
            html = '<a data-linked-resource-type="page" data-linked-resource-id="201">x</a>'
            result = conv.convert(html).strip()

        PageTitleRegistry.reset()
        assert "Shared%20Title.md" in result
        assert result.startswith("[Shared Title](")


class TestAbsoluteUrlPageLinks:
    """Absolute Confluence URLs in href must resolve to page links, not pass through."""

    def _make_target_page(self, page_id: int, title: str, space_key: str) -> Page:
        space = Space(
            base_url="https://example.com",
            key=space_key,
            name=space_key,
            description="",
            homepage=0,
        )
        version = Version(
            number=1,
            by=User(
                account_id="u1",
                display_name="User",
                username="user",
                public_name="",
                email="",
            ),
            when="2024-01-01T00:00:00Z",
            friendly_when="Jan 1",
        )
        return Page(
            base_url="https://example.com",
            id=page_id,
            title=title,
            space=space,
            ancestors=[],
            version=version,
            body="",
            body_export="",
            editor2="",
            body_storage="",
            labels=[],
            attachments=[],
        )

    def test_absolute_url_same_host_resolves_page(self) -> None:
        from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry

        PageTitleRegistry.reset()
        target = self._make_target_page(1437663233, "Linked Page", "STRUCT")

        source = _make_page(body="", body_export="", attachments=[])

        with (
            patch(
                "confluence_markdown_exporter.confluence.Page.from_id",
                return_value=target,
            ),
            patch("confluence_markdown_exporter.confluence.settings") as s,
        ):
            s.export.page_href = "wiki"
            s.export.page_path = "{space_name}/{page_title}.md"
            conv = Page.Converter(source)
            html = (
                '<a href="https://example.com/wiki/spaces/STRUCT/pages/1437663233">'
                "https://example.com/wiki/spaces/STRUCT/pages/1437663233</a>"
            )
            result = conv.convert(html).strip()

        PageTitleRegistry.reset()
        assert result == "[[Linked Page]]"

    def test_absolute_url_different_host_left_alone(self) -> None:
        source = _make_page(body="", body_export="", attachments=[])
        conv = Page.Converter(source)
        html = (
            '<a href="https://other.atlassian.net/wiki/spaces/X/pages/9/T">'
            "https://other.atlassian.net/wiki/spaces/X/pages/9/T</a>"
        )
        result = conv.convert(html).strip()
        assert result == "<https://other.atlassian.net/wiki/spaces/X/pages/9/T>"

    def test_legacy_pageid_query_resolves_page(self) -> None:
        from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry

        PageTitleRegistry.reset()
        target = self._make_target_page(555, "Legacy Page", "OLD")

        source = _make_page(body="", body_export="", attachments=[])

        with (
            patch(
                "confluence_markdown_exporter.confluence.Page.from_id",
                return_value=target,
            ),
            patch("confluence_markdown_exporter.confluence.settings") as s,
        ):
            s.export.page_href = "wiki"
            s.export.page_path = "{space_name}/{page_title}.md"
            conv = Page.Converter(source)
            html = '<a href="https://example.com/pages/viewpage.action?pageId=555">x</a>'
            result = conv.convert(html).strip()

        PageTitleRegistry.reset()
        assert result == "[[Legacy Page]]"
