"""Unit tests for the `viewpdf` (PDF/file preview) macro conversion."""

from pathlib import Path
from unittest.mock import patch

from confluence_markdown_exporter.confluence import Page


class MockAttachment:
    def __init__(self, title: str) -> None:
        self.title = title
        self.export_path = Path(f"TEST/attachments/{title}")


class MockPage:
    def __init__(self, attachments: list[MockAttachment]) -> None:
        self.id = "test-page"
        self.title = "Test Page"
        self.html = ""
        self.body_storage = ""
        self.labels: list = []
        self.ancestors: list = []
        self.export_path = Path("TEST/Test Page.md")
        self._attachments = attachments

    def get_attachment_by_id(self, attachment_id: str) -> MockAttachment | None:
        for a in self._attachments:
            if getattr(a, "id", None) == attachment_id:
                return a
        return None

    def get_attachment_by_file_id(self, _file_id: str) -> None:
        return None

    def get_attachments_by_title(self, title: str) -> list[MockAttachment]:
        return [a for a in self._attachments if a.title == title]


def _viewpdf_div(*, attachment_id: str = "", attachment: str = "") -> str:
    return (
        '<div class="vf-slide-viewer-macro conf-macro output-block" '
        f'data-attachment="{attachment}" data-attachment-id="{attachment_id}" '
        'data-macro-name="viewpdf">'
        '<div class="vf-slide-viewer"></div>'
        "</div>"
    )


class TestConvertViewpdf:
    def test_resolves_attachment_by_id(self) -> None:
        attachment = MockAttachment("Some Document.pdf")
        attachment.id = "att132887794"
        page = MockPage([attachment])
        html = _viewpdf_div(attachment_id="att132887794", attachment="Some+Document.pdf")

        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_href = "relative"
            result = Page.Converter(page).convert(html).strip()  # type: ignore[arg-type]

        assert "Some Document.pdf" in result

    def test_falls_back_to_url_encoded_filename(self) -> None:
        attachment = MockAttachment("Some Document.pdf")
        page = MockPage([attachment])
        # No attachment matches the (unknown) id, so the handler must fall back
        # to the `data-attachment` filename, which is URL-encoded with `+` for spaces.
        html = _viewpdf_div(attachment_id="att-unknown", attachment="Some+Document.pdf")

        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_href = "relative"
            result = Page.Converter(page).convert(html).strip()  # type: ignore[arg-type]

        assert "Some Document.pdf" in result

    def test_missing_attachment_returns_comment(self) -> None:
        page = MockPage([])
        html = _viewpdf_div(attachment_id="att-unknown", attachment="Missing.pdf")

        with patch("confluence_markdown_exporter.confluence.settings") as s:
            s.export.attachment_href = "relative"
            result = Page.Converter(page).convert(html).strip()  # type: ignore[arg-type]

        assert "not found" in result
