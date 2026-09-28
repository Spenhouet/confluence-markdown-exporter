"""Optional config fields: empty input unsets them, the menu never offers "None"."""

from unittest.mock import patch

import pytest

from confluence_markdown_exporter.utils.app_data_store import ConfigModel
from confluence_markdown_exporter.utils.app_data_store import ConnectionConfig
from confluence_markdown_exporter.utils.app_data_store import ExportConfig
from confluence_markdown_exporter.utils.config_interactive import _prompt_for_new_value


@pytest.mark.parametrize(
    "field",
    ["page_path_if_parent", "attachment_path_if_parent", "page_href_relative_only_if_ancestor_of"],
)
def test_empty_string_unsets_export_field(field: str) -> None:
    assert getattr(ExportConfig(**{field: ""}), field) is None


def test_empty_string_unsets_ca_bundle() -> None:
    assert ConnectionConfig(ca_bundle=" ").ca_bundle is None


def test_ancestor_gate_accepts_numeric_string() -> None:
    assert (
        ExportConfig(
            page_href_relative_only_if_ancestor_of="123"
        ).page_href_relative_only_if_ancestor_of
        == 123
    )


@pytest.mark.parametrize(
    ("current", "expected_default"),
    [(None, ""), ("{page_title}/index.md", "{page_title}/index.md")],
)
def test_optional_field_prompt_default(current: object, expected_default: str) -> None:
    with patch("confluence_markdown_exporter.utils.config_interactive.questionary.text") as text:
        text.return_value.ask.return_value = ""
        _prompt_for_new_value("page_path_if_parent", current, ExportConfig)
    assert text.call_args.kwargs["default"] == expected_default
    validate = text.call_args.kwargs["validate"]
    assert validate("") is True


def test_config_get_prints_null_for_unset_optional(capsys: pytest.CaptureFixture[str]) -> None:
    from confluence_markdown_exporter.config import get

    with patch(
        "confluence_markdown_exporter.config.get_settings",
        return_value=ConfigModel(),
    ):
        get("export.page_path_if_parent")
    assert capsys.readouterr().out.strip() == "null"
