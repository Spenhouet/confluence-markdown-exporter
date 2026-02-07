"""Tests for state file model and persistence."""

from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from confluence_markdown_exporter.state import STATE_FILENAME
from confluence_markdown_exporter.state import ExportState
from confluence_markdown_exporter.state import PageState
from confluence_markdown_exporter.state import ScopeEntry
from confluence_markdown_exporter.state import load_state
from confluence_markdown_exporter.state import save_state
from confluence_markdown_exporter.state import update_page_state
from confluence_markdown_exporter.state import validate_state_url


class TestPageState:
    """Tests for the PageState Pydantic model."""

    def test_page_state_fields(self) -> None:
        """PageState stores version, last_exported, output_path, and status."""
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        ps = PageState(
            version=5,
            last_exported=now,
            output_path="spaces/Engineering/some-page.md",
            status="active",
        )
        assert ps.version == 5
        assert ps.last_exported == now
        assert ps.output_path == "spaces/Engineering/some-page.md"
        assert ps.status == "active"

    def test_page_state_deleted_status(self) -> None:
        """PageState accepts 'deleted' as a valid status."""
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        ps = PageState(
            version=3,
            last_exported=now,
            output_path="spaces/Old/removed-page.md",
            status="deleted",
        )
        assert ps.status == "deleted"

    def test_page_state_rejects_invalid_status(self) -> None:
        """PageState rejects statuses other than 'active' and 'deleted'."""
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValidationError, match="status"):
            PageState(
                version=1,
                last_exported=now,
                output_path="x.md",
                status="unknown",
            )


class TestScopeEntry:
    """Tests for the ScopeEntry Pydantic model."""

    def test_scope_entry_fields(self) -> None:
        """ScopeEntry stores command and args."""
        se = ScopeEntry(command="pages", args=["12345", "67890"])
        assert se.command == "pages"
        assert se.args == ["12345", "67890"]

    def test_scope_entry_empty_args(self) -> None:
        """ScopeEntry allows empty args list."""
        se = ScopeEntry(command="all-spaces", args=[])
        assert se.command == "all-spaces"
        assert se.args == []


class TestExportState:
    """Tests for the ExportState Pydantic model."""

    def test_export_state_fields(self) -> None:
        """ExportState stores schema_version, confluence_url, scopes, pages, etc."""
        state = ExportState(
            confluence_url="https://example.atlassian.net",
            scopes=[ScopeEntry(command="pages", args=["123"])],
        )
        assert state.schema_version == 1
        assert state.confluence_url == "https://example.atlassian.net"
        assert len(state.scopes) == 1
        assert state.min_export_timestamp is None
        assert state.pages == {}

    def test_export_state_with_pages(self) -> None:
        """ExportState can hold multiple page entries."""
        now = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        state = ExportState(
            confluence_url="https://example.atlassian.net",
            scopes=[],
            pages={
                "111": PageState(
                    version=2,
                    last_exported=now,
                    output_path="a.md",
                    status="active",
                ),
                "222": PageState(
                    version=1,
                    last_exported=now,
                    output_path="b.md",
                    status="deleted",
                ),
            },
        )
        assert len(state.pages) == 2
        assert state.pages["111"].version == 2
        assert state.pages["222"].status == "deleted"

    def test_export_state_with_min_export_timestamp(self) -> None:
        """ExportState can have a min_export_timestamp for --force re-exports."""
        ts = datetime(2026, 2, 5, 8, 0, 0, tzinfo=timezone.utc)
        state = ExportState(
            confluence_url="https://example.atlassian.net",
            scopes=[],
            min_export_timestamp=ts,
        )
        assert state.min_export_timestamp == ts


class TestLoadState:
    """Tests for the load_state function."""

    def test_load_state_missing_file_returns_none(self, tmp_path: Path) -> None:
        """load_state returns None when no state file exists."""
        result = load_state(tmp_path)
        assert result is None

    def test_load_state_reads_existing_file(self, tmp_path: Path) -> None:
        """load_state reads and deserializes a valid state file."""
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[ScopeEntry(command="spaces", args=["ENG"])],
        )
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded is not None
        assert loaded.confluence_url == "https://test.atlassian.net"
        assert len(loaded.scopes) == 1
        assert loaded.scopes[0].command == "spaces"


class TestSaveState:
    """Tests for the save_state function."""

    def test_save_state_creates_file(self, tmp_path: Path) -> None:
        """save_state creates the state file in the output directory."""
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[],
        )
        save_state(tmp_path, state)
        state_file = tmp_path / STATE_FILENAME
        assert state_file.exists()

    def test_save_state_json_is_indented(self, tmp_path: Path) -> None:
        """save_state writes human-readable indented JSON."""
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[],
        )
        save_state(tmp_path, state)
        state_file = tmp_path / STATE_FILENAME
        content = state_file.read_text()
        # Indented JSON has newlines and spaces
        assert "\n" in content
        assert "  " in content


class TestRoundTrip:
    """Tests for save then load round-trip integrity."""

    def test_round_trip_produces_identical_state(self, tmp_path: Path) -> None:
        """Saving then loading state produces an identical ExportState."""
        now = datetime(2026, 2, 1, 10, 30, 0, tzinfo=timezone.utc)
        original = ExportState(
            schema_version=1,
            confluence_url="https://roundtrip.atlassian.net",
            scopes=[
                ScopeEntry(command="pages", args=["100", "200"]),
                ScopeEntry(command="spaces", args=["ENG"]),
            ],
            min_export_timestamp=now,
            pages={
                "100": PageState(
                    version=3,
                    last_exported=now,
                    output_path="Engineering/page-a.md",
                    status="active",
                ),
                "200": PageState(
                    version=1,
                    last_exported=now,
                    output_path="Engineering/page-b.md",
                    status="deleted",
                ),
            },
        )
        save_state(tmp_path, original)
        loaded = load_state(tmp_path)
        assert loaded is not None
        assert loaded == original


class TestUpdatePageState:
    """Tests for the update_page_state function."""

    def test_update_page_state_adds_new_entry(self) -> None:
        """update_page_state adds a new page entry with status='active'."""
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[],
        )
        update_page_state(state, page_id="999", version=7, output_path="pages/new.md")
        assert "999" in state.pages
        assert state.pages["999"].version == 7
        assert state.pages["999"].output_path == "pages/new.md"
        assert state.pages["999"].status == "active"
        assert state.pages["999"].last_exported is not None

    def test_update_page_state_overwrites_existing(self) -> None:
        """update_page_state updates an existing page entry."""
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[],
            pages={
                "999": PageState(
                    version=3,
                    last_exported=now,
                    output_path="old/path.md",
                    status="active",
                ),
            },
        )
        update_page_state(state, page_id="999", version=5, output_path="new/path.md")
        assert state.pages["999"].version == 5
        assert state.pages["999"].output_path == "new/path.md"
        assert state.pages["999"].last_exported > now

    def test_update_page_state_sets_active_status(self) -> None:
        """update_page_state always sets status to 'active'."""
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[],
            pages={
                "888": PageState(
                    version=2,
                    last_exported=now,
                    output_path="x.md",
                    status="deleted",
                ),
            },
        )
        update_page_state(state, page_id="888", version=3, output_path="x.md")
        assert state.pages["888"].status == "active"


class TestValidateStateUrl:
    """Tests for the validate_state_url function."""

    def test_validate_state_url_matching(self) -> None:
        """validate_state_url does not raise when URLs match."""
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[],
        )
        # Should not raise
        validate_state_url(state, "https://test.atlassian.net")

    def test_validate_state_url_mismatch_raises(self) -> None:
        """validate_state_url raises ValueError when URLs differ."""
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[],
        )
        with pytest.raises(ValueError, match="mismatch"):
            validate_state_url(state, "https://other.atlassian.net")

    def test_validate_state_url_mismatch_raises_with_hint(self) -> None:
        """validate_state_url error message suggests --force to update."""
        state = ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[],
        )
        with pytest.raises(ValueError, match="--force"):
            validate_state_url(state, "https://other.atlassian.net")

    def test_validate_state_url_update_changes_url(self) -> None:
        """validate_state_url with update=True updates the stored URL."""
        state = ExportState(
            confluence_url="https://old.atlassian.net",
            scopes=[],
        )
        validate_state_url(state, "https://new.atlassian.net", update=True)
        assert state.confluence_url == "https://new.atlassian.net"


class TestSyncDelta:
    """Tests for the SyncDelta dataclass."""

    def test_sync_delta_fields(self) -> None:
        """SyncDelta has new, modified, stale, deleted, unchanged lists."""
        from confluence_markdown_exporter.state import SyncDelta

        delta = SyncDelta(
            new=["1"],
            modified=["2"],
            stale=["3"],
            deleted=["4"],
            unchanged=["5"],
        )
        assert delta.new == ["1"]
        assert delta.modified == ["2"]
        assert delta.stale == ["3"]
        assert delta.deleted == ["4"]
        assert delta.unchanged == ["5"]

    def test_sync_delta_empty(self) -> None:
        """SyncDelta can have all empty lists."""
        from confluence_markdown_exporter.state import SyncDelta

        delta = SyncDelta(
            new=[], modified=[], stale=[], deleted=[], unchanged=[]
        )
        assert delta.new == []
        assert delta.modified == []
        assert delta.stale == []
        assert delta.deleted == []
        assert delta.unchanged == []


class TestComputeDelta:
    """Tests for the compute_delta function."""

    def _make_state(
        self,
        pages: dict[str, PageState] | None = None,
        min_export_timestamp: datetime | None = None,
    ) -> ExportState:
        """Helper to create an ExportState with given pages."""
        return ExportState(
            confluence_url="https://test.atlassian.net",
            scopes=[ScopeEntry(command="spaces", args=["ENG"])],
            min_export_timestamp=min_export_timestamp,
            pages=pages or {},
        )

    def test_new_page_detection(self) -> None:
        """Page in current_pages but not in state is classified as new."""
        from confluence_markdown_exporter.state import compute_delta

        state = self._make_state()
        current_pages = {"page-1": 1}
        delta = compute_delta(state, current_pages)
        assert delta.new == ["page-1"]
        assert delta.modified == []
        assert delta.stale == []
        assert delta.deleted == []
        assert delta.unchanged == []

    def test_modified_detection(self) -> None:
        """Page with higher version in current_pages is classified as modified."""
        from confluence_markdown_exporter.state import compute_delta

        now = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        state = self._make_state(
            pages={
                "page-1": PageState(
                    version=3,
                    last_exported=now,
                    output_path="a.md",
                    status="active",
                ),
            }
        )
        current_pages = {"page-1": 5}
        delta = compute_delta(state, current_pages)
        assert delta.modified == ["page-1"]
        assert delta.new == []
        assert delta.unchanged == []

    def test_stale_detection_with_force(self) -> None:
        """Page with matching version but exported before min_export_timestamp is stale."""
        from confluence_markdown_exporter.state import compute_delta

        old_export = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        force_time = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        state = self._make_state(
            pages={
                "page-1": PageState(
                    version=3,
                    last_exported=old_export,
                    output_path="a.md",
                    status="active",
                ),
            },
            min_export_timestamp=force_time,
        )
        current_pages = {"page-1": 3}
        delta = compute_delta(state, current_pages)
        assert delta.stale == ["page-1"]
        assert delta.modified == []
        assert delta.unchanged == []

    def test_deleted_detection(self) -> None:
        """Active page in state but not in current_pages is classified as deleted."""
        from confluence_markdown_exporter.state import compute_delta

        now = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        state = self._make_state(
            pages={
                "page-1": PageState(
                    version=2,
                    last_exported=now,
                    output_path="a.md",
                    status="active",
                ),
            }
        )
        current_pages: dict[str, int] = {}
        delta = compute_delta(state, current_pages)
        assert delta.deleted == ["page-1"]
        assert delta.new == []
        assert delta.modified == []

    def test_unchanged_detection(self) -> None:
        """Page with matching version and recent export is classified as unchanged."""
        from confluence_markdown_exporter.state import compute_delta

        now = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        state = self._make_state(
            pages={
                "page-1": PageState(
                    version=4,
                    last_exported=now,
                    output_path="a.md",
                    status="active",
                ),
            }
        )
        current_pages = {"page-1": 4}
        delta = compute_delta(state, current_pages)
        assert delta.unchanged == ["page-1"]
        assert delta.new == []
        assert delta.modified == []
        assert delta.stale == []
        assert delta.deleted == []

    def test_unchanged_without_min_export_timestamp(self) -> None:
        """Without min_export_timestamp, matching version is always unchanged."""
        from confluence_markdown_exporter.state import compute_delta

        old_export = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        state = self._make_state(
            pages={
                "page-1": PageState(
                    version=4,
                    last_exported=old_export,
                    output_path="a.md",
                    status="active",
                ),
            },
            min_export_timestamp=None,
        )
        current_pages = {"page-1": 4}
        delta = compute_delta(state, current_pages)
        assert delta.unchanged == ["page-1"]

    def test_combination_of_all_categories(self) -> None:
        """A mix of new, modified, stale, deleted, and unchanged pages."""
        from confluence_markdown_exporter.state import compute_delta

        old_export = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        recent_export = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)
        force_time = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        state = self._make_state(
            pages={
                "modified-page": PageState(
                    version=2,
                    last_exported=recent_export,
                    output_path="mod.md",
                    status="active",
                ),
                "stale-page": PageState(
                    version=5,
                    last_exported=old_export,
                    output_path="stale.md",
                    status="active",
                ),
                "deleted-page": PageState(
                    version=1,
                    last_exported=recent_export,
                    output_path="del.md",
                    status="active",
                ),
                "unchanged-page": PageState(
                    version=3,
                    last_exported=recent_export,
                    output_path="unch.md",
                    status="active",
                ),
            },
            min_export_timestamp=force_time,
        )
        current_pages = {
            "new-page": 1,
            "modified-page": 5,
            "stale-page": 5,
            "unchanged-page": 3,
        }
        delta = compute_delta(state, current_pages)
        assert sorted(delta.new) == ["new-page"]
        assert sorted(delta.modified) == ["modified-page"]
        assert sorted(delta.stale) == ["stale-page"]
        assert sorted(delta.deleted) == ["deleted-page"]
        assert sorted(delta.unchanged) == ["unchanged-page"]

    def test_already_deleted_pages_ignored(self) -> None:
        """Pages with status='deleted' in state are not counted as deleted again."""
        from confluence_markdown_exporter.state import compute_delta

        now = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        state = self._make_state(
            pages={
                "old-deleted": PageState(
                    version=1,
                    last_exported=now,
                    output_path="old.md",
                    status="deleted",
                ),
            }
        )
        current_pages: dict[str, int] = {}
        delta = compute_delta(state, current_pages)
        assert delta.deleted == []
        assert delta.new == []
        assert delta.unchanged == []
