"""Tests for PageTitleRegistry collision detection."""

from __future__ import annotations

import pytest

from confluence_markdown_exporter.utils.page_registry import PageTitleRegistry


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    PageTitleRegistry.reset()
    yield
    PageTitleRegistry.reset()


def test_unique_title_not_ambiguous() -> None:
    PageTitleRegistry.register(1, "Shared Title")
    assert PageTitleRegistry.is_ambiguous("Shared Title") is False


def test_two_pages_same_title_ambiguous() -> None:
    PageTitleRegistry.register(1, "Shared Title")
    PageTitleRegistry.register(2, "Shared Title")
    assert PageTitleRegistry.is_ambiguous("Shared Title") is True


def test_unknown_title_not_ambiguous() -> None:
    assert PageTitleRegistry.is_ambiguous("Never Seen") is False


def test_re_register_same_id_does_not_inflate_count() -> None:
    PageTitleRegistry.register(1, "Shared Title")
    PageTitleRegistry.register(1, "Shared Title")
    PageTitleRegistry.register(1, "Shared Title")
    assert PageTitleRegistry.is_ambiguous("Shared Title") is False
    assert PageTitleRegistry.title_count("Shared Title") == 1


def test_renaming_page_updates_counts() -> None:
    PageTitleRegistry.register(1, "Old Title")
    PageTitleRegistry.register(2, "Old Title")
    assert PageTitleRegistry.is_ambiguous("Old Title") is True

    PageTitleRegistry.register(1, "New Title")
    assert PageTitleRegistry.is_ambiguous("Old Title") is False
    assert PageTitleRegistry.title_count("Old Title") == 1
    assert PageTitleRegistry.title_count("New Title") == 1


def test_reset_clears_state() -> None:
    PageTitleRegistry.register(1, "X")
    PageTitleRegistry.register(2, "X")
    PageTitleRegistry.reset()
    assert PageTitleRegistry.is_ambiguous("X") is False
    assert PageTitleRegistry.title_count("X") == 0


def test_blank_inputs_ignored() -> None:
    PageTitleRegistry.register(0, "X")
    PageTitleRegistry.register(1, "")
    assert PageTitleRegistry.title_count("X") == 0
    assert PageTitleRegistry.title_count("") == 0
