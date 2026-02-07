"""Tests for sync orchestration module."""

from datetime import datetime
from datetime import timezone
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from confluence_markdown_exporter.state import ExportState
from confluence_markdown_exporter.state import PageState
from confluence_markdown_exporter.state import ScopeEntry
from confluence_markdown_exporter.state import SyncDelta


def _make_state(
    scopes: list[ScopeEntry] | None = None,
    pages: dict[str, PageState] | None = None,
    min_export_timestamp: datetime | None = None,
) -> ExportState:
    """Helper to create an ExportState with given scopes and pages."""
    return ExportState(
        confluence_url="https://test.atlassian.net",
        scopes=scopes or [],
        pages=pages or {},
        min_export_timestamp=min_export_timestamp,
    )


class TestReplayScopes:
    """Tests for the replay_scopes function."""

    @patch("confluence_markdown_exporter.sync.confluence")
    @patch("confluence_markdown_exporter.sync.Space")
    def test_spaces_scope(
        self, mock_space_cls: MagicMock, mock_confluence: MagicMock
    ) -> None:
        """Spaces scope fetches pages from each space and returns page versions."""
        from confluence_markdown_exporter.sync import replay_scopes

        # Set up Space mock
        mock_space = MagicMock()
        mock_space.pages = [101, 102]
        mock_space_cls.from_key.return_value = mock_space

        # Set up lightweight page version fetch
        mock_confluence.get_page_by_id.side_effect = [
            {"id": 101, "version": {"number": 3}},
            {"id": 102, "version": {"number": 7}},
        ]

        state = _make_state(
            scopes=[ScopeEntry(command="spaces", args=["ENG"])]
        )
        result = replay_scopes(state)

        assert result == {"101": 3, "102": 7}
        mock_space_cls.from_key.assert_called_once_with("ENG")

    @patch("confluence_markdown_exporter.sync.confluence")
    @patch("confluence_markdown_exporter.sync.Organization")
    def test_all_spaces_scope(
        self, mock_org_cls: MagicMock, mock_confluence: MagicMock
    ) -> None:
        """All-spaces scope fetches org pages and returns page versions."""
        from confluence_markdown_exporter.sync import replay_scopes

        mock_space = MagicMock()
        mock_space.pages = [201, 202, 203]
        mock_org = MagicMock()
        mock_org.spaces = [mock_space]
        mock_org_cls.from_api.return_value = mock_org

        mock_confluence.get_page_by_id.side_effect = [
            {"id": 201, "version": {"number": 1}},
            {"id": 202, "version": {"number": 2}},
            {"id": 203, "version": {"number": 5}},
        ]

        state = _make_state(
            scopes=[ScopeEntry(command="all_spaces", args=[])]
        )
        result = replay_scopes(state)

        assert result == {"201": 1, "202": 2, "203": 5}
        mock_org_cls.from_api.assert_called_once()

    @patch("confluence_markdown_exporter.sync.confluence")
    @patch("confluence_markdown_exporter.sync.Page")
    def test_pages_scope(
        self, mock_page_cls: MagicMock, mock_confluence: MagicMock
    ) -> None:
        """Pages scope fetches individual pages by ID and returns versions."""
        from confluence_markdown_exporter.sync import replay_scopes

        mock_page_1 = MagicMock()
        mock_page_1.id = 301
        mock_page_1.page_version = 4

        mock_page_2 = MagicMock()
        mock_page_2.id = 302
        mock_page_2.page_version = 2

        mock_page_cls.from_id.side_effect = [mock_page_1, mock_page_2]

        state = _make_state(
            scopes=[ScopeEntry(command="pages", args=["301", "302"])]
        )
        result = replay_scopes(state)

        assert result == {"301": 4, "302": 2}
        assert mock_page_cls.from_id.call_count == 2

    @patch("confluence_markdown_exporter.sync.confluence")
    @patch("confluence_markdown_exporter.sync.Page")
    def test_pages_with_descendants_scope(
        self, mock_page_cls: MagicMock, mock_confluence: MagicMock
    ) -> None:
        """Pages-with-descendants scope fetches page + descendants versions."""
        from confluence_markdown_exporter.sync import replay_scopes

        mock_parent = MagicMock()
        mock_parent.id = 401
        mock_parent.page_version = 3
        mock_parent.descendants = [402, 403]

        mock_child_1 = MagicMock()
        mock_child_1.id = 402
        mock_child_1.page_version = 1

        mock_child_2 = MagicMock()
        mock_child_2.id = 403
        mock_child_2.page_version = 2

        def from_id_dispatch(page_id: int) -> MagicMock:
            return {401: mock_parent, 402: mock_child_1, 403: mock_child_2}[page_id]

        mock_page_cls.from_id.side_effect = from_id_dispatch

        # For spaces/all_spaces, confluence.get_page_by_id is used.
        # For pages/pages_with_descendants, Page.from_id is used directly.
        # But descendants need version lookups too:
        mock_confluence.get_page_by_id.side_effect = [
            {"id": 402, "version": {"number": 1}},
            {"id": 403, "version": {"number": 2}},
        ]

        state = _make_state(
            scopes=[
                ScopeEntry(command="pages_with_descendants", args=["401"])
            ]
        )
        result = replay_scopes(state)

        assert result == {"401": 3, "402": 1, "403": 2}

    @patch("confluence_markdown_exporter.sync.confluence")
    @patch("confluence_markdown_exporter.sync.Space")
    @patch("confluence_markdown_exporter.sync.Page")
    def test_multiple_scopes_deduplicate(
        self,
        mock_page_cls: MagicMock,
        mock_space_cls: MagicMock,
        mock_confluence: MagicMock,
    ) -> None:
        """Multiple scopes are combined and deduplicated by page_id."""
        from confluence_markdown_exporter.sync import replay_scopes

        # First scope: spaces with page 101
        mock_space = MagicMock()
        mock_space.pages = [101]
        mock_space_cls.from_key.return_value = mock_space

        mock_confluence.get_page_by_id.side_effect = [
            {"id": 101, "version": {"number": 5}},
        ]

        # Second scope: individual page 101 (duplicate) and 102
        mock_page_101 = MagicMock()
        mock_page_101.id = 101
        mock_page_101.page_version = 5

        mock_page_102 = MagicMock()
        mock_page_102.id = 102
        mock_page_102.page_version = 1

        mock_page_cls.from_id.side_effect = [mock_page_101, mock_page_102]

        state = _make_state(
            scopes=[
                ScopeEntry(command="spaces", args=["ENG"]),
                ScopeEntry(command="pages", args=["101", "102"]),
            ]
        )
        result = replay_scopes(state)

        # Page 101 appears in both scopes but should only be in result once
        assert result == {"101": 5, "102": 1}


class TestExecuteSync:
    """Tests for the execute_sync function."""

    @patch("confluence_markdown_exporter.sync.export_and_track")
    @patch("confluence_markdown_exporter.sync.save_state")
    def test_dry_run_no_changes(
        self, mock_save: MagicMock, mock_export_track: MagicMock, tmp_path: Path
    ) -> None:
        """dry_run=True does not export or update state."""
        from confluence_markdown_exporter.sync import execute_sync

        now = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        state = _make_state(
            pages={
                "100": PageState(
                    version=1,
                    last_exported=now,
                    output_path="old.md",
                    status="active",
                ),
            }
        )
        delta = SyncDelta(
            new=["200"],
            modified=["100"],
            stale=[],
            deleted=[],
            unchanged=[],
        )

        execute_sync(state, delta, tmp_path, dry_run=True)

        mock_export_track.assert_not_called()
        mock_save.assert_not_called()

    @patch("confluence_markdown_exporter.sync.export_and_track")
    @patch("confluence_markdown_exporter.sync.save_state")
    def test_exports_new_pages(
        self, mock_save: MagicMock, mock_export_track: MagicMock, tmp_path: Path
    ) -> None:
        """New pages are exported via export_and_track."""
        from confluence_markdown_exporter.sync import execute_sync

        state = _make_state()
        delta = SyncDelta(
            new=["200", "201"],
            modified=[],
            stale=[],
            deleted=[],
            unchanged=[],
        )

        execute_sync(state, delta, tmp_path, dry_run=False)

        mock_export_track.assert_called_once_with(
            [200, 201], state, tmp_path
        )

    @patch("confluence_markdown_exporter.sync.export_and_track")
    @patch("confluence_markdown_exporter.sync.save_state")
    def test_reexports_modified_pages(
        self, mock_save: MagicMock, mock_export_track: MagicMock, tmp_path: Path
    ) -> None:
        """Modified pages are re-exported via export_and_track."""
        from confluence_markdown_exporter.sync import execute_sync

        now = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        state = _make_state(
            pages={
                "300": PageState(
                    version=2,
                    last_exported=now,
                    output_path="page.md",
                    status="active",
                ),
            }
        )
        delta = SyncDelta(
            new=[],
            modified=["300"],
            stale=[],
            deleted=[],
            unchanged=[],
        )

        execute_sync(state, delta, tmp_path, dry_run=False)

        mock_export_track.assert_called_once_with(
            [300], state, tmp_path
        )

    @patch("confluence_markdown_exporter.sync.export_and_track")
    @patch("confluence_markdown_exporter.sync.save_state")
    def test_deletes_orphan_files(
        self, mock_save: MagicMock, mock_export_track: MagicMock, tmp_path: Path
    ) -> None:
        """Deleted pages have their files removed and state entries updated."""
        from confluence_markdown_exporter.sync import execute_sync

        now = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        # Create the file that should be deleted
        orphan_file = tmp_path / "spaces" / "old-page.md"
        orphan_file.parent.mkdir(parents=True, exist_ok=True)
        orphan_file.write_text("old content")

        state = _make_state(
            pages={
                "400": PageState(
                    version=1,
                    last_exported=now,
                    output_path="spaces/old-page.md",
                    status="active",
                ),
            }
        )
        delta = SyncDelta(
            new=[],
            modified=[],
            stale=[],
            deleted=["400"],
            unchanged=[],
        )

        execute_sync(state, delta, tmp_path, dry_run=False)

        # File should be deleted
        assert not orphan_file.exists()
        # State should mark page as deleted
        assert state.pages["400"].status == "deleted"
        # State should be saved
        assert mock_save.called
        # No exports should happen for deleted pages
        mock_export_track.assert_called_once_with([], state, tmp_path)

    @patch("confluence_markdown_exporter.sync.export_and_track")
    @patch("confluence_markdown_exporter.sync.save_state")
    def test_reexports_stale_pages(
        self, mock_save: MagicMock, mock_export_track: MagicMock, tmp_path: Path
    ) -> None:
        """Stale pages (from --force) are re-exported via export_and_track."""
        from confluence_markdown_exporter.sync import execute_sync

        old_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        force_time = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        state = _make_state(
            pages={
                "500": PageState(
                    version=3,
                    last_exported=old_time,
                    output_path="stale.md",
                    status="active",
                ),
            },
            min_export_timestamp=force_time,
        )
        delta = SyncDelta(
            new=[],
            modified=[],
            stale=["500"],
            deleted=[],
            unchanged=[],
        )

        execute_sync(state, delta, tmp_path, dry_run=False)

        mock_export_track.assert_called_once_with(
            [500], state, tmp_path
        )


class TestFormatSyncReport:
    """Tests for the format_sync_report function."""

    def test_new_pages_not_in_state_show_page_id(self) -> None:
        """New pages not yet in state show page ID instead of <unknown page>."""
        from confluence_markdown_exporter.sync import format_sync_report

        state = _make_state()
        delta = SyncDelta(
            new=["12345"],
            modified=[],
            stale=[],
            deleted=[],
            unchanged=[],
        )

        report = format_sync_report(delta, state)
        assert "  new:  page 12345" in report
        assert "<unknown" not in report

    def test_modified_pages_format(self) -> None:
        """Modified pages are shown with 'mod:' prefix."""
        from confluence_markdown_exporter.sync import format_sync_report

        now = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        state = _make_state(
            pages={
                "2": PageState(
                    version=5,
                    last_exported=now,
                    output_path="path/to/modified.md",
                    status="active",
                ),
            }
        )
        delta = SyncDelta(
            new=[],
            modified=["2"],
            stale=[],
            deleted=[],
            unchanged=[],
        )

        report = format_sync_report(delta, state)
        assert "  mod:  path/to/modified.md" in report

    def test_deleted_pages_format(self) -> None:
        """Deleted pages are shown with 'del:' prefix."""
        from confluence_markdown_exporter.sync import format_sync_report

        now = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        state = _make_state(
            pages={
                "3": PageState(
                    version=1,
                    last_exported=now,
                    output_path="path/to/deleted.md",
                    status="active",
                ),
            }
        )
        delta = SyncDelta(
            new=[],
            modified=[],
            stale=[],
            deleted=["3"],
            unchanged=[],
        )

        report = format_sync_report(delta, state)
        assert "  del:  path/to/deleted.md" in report

    def test_summary_line(self) -> None:
        """Summary line shows counts for all categories."""
        from confluence_markdown_exporter.sync import format_sync_report

        now = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        state = _make_state(
            pages={
                "1": PageState(
                    version=1,
                    last_exported=now,
                    output_path="new1.md",
                    status="active",
                ),
                "2": PageState(
                    version=1,
                    last_exported=now,
                    output_path="new2.md",
                    status="active",
                ),
                "3": PageState(
                    version=1,
                    last_exported=now,
                    output_path="new3.md",
                    status="active",
                ),
                "4": PageState(
                    version=5,
                    last_exported=now,
                    output_path="mod.md",
                    status="active",
                ),
                "5": PageState(
                    version=1,
                    last_exported=now,
                    output_path="del.md",
                    status="active",
                ),
            }
        )
        # Simulate 496 unchanged by providing page IDs
        unchanged_ids = [str(i) for i in range(100, 596)]
        for uid in unchanged_ids:
            state.pages[uid] = PageState(
                version=1,
                last_exported=now,
                output_path=f"page-{uid}.md",
                status="active",
            )

        delta = SyncDelta(
            new=["1", "2", "3"],
            modified=["4"],
            stale=[],
            deleted=["5"],
            unchanged=unchanged_ids,
        )

        report = format_sync_report(delta, state)
        assert "3 new, 1 modified, 1 deleted, 496 unchanged" in report

    def test_empty_delta(self) -> None:
        """Empty delta shows only summary line with all zeros."""
        from confluence_markdown_exporter.sync import format_sync_report

        state = _make_state()
        delta = SyncDelta(
            new=[], modified=[], stale=[], deleted=[], unchanged=[]
        )

        report = format_sync_report(delta, state)
        assert "0 new, 0 modified, 0 deleted, 0 unchanged" in report
        # No file lines should appear
        lines = [line for line in report.strip().split("\n") if line.strip()]
        assert len(lines) == 1  # Only the summary line


class TestExportAndTrack:
    """Tests for the export_and_track orchestration function.

    export_and_track wraps the export-then-track-state pattern:
    for each page, it calls page.export() (pure domain) then
    update_page_state + save_state (infrastructure).
    """

    @patch("confluence_markdown_exporter.sync.save_state")
    @patch("confluence_markdown_exporter.sync.update_page_state")
    @patch("confluence_markdown_exporter.sync.Page")
    def test_exports_pages_and_tracks_state(
        self,
        mock_page_cls: MagicMock,
        mock_update: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Each page is exported, then state is updated and saved progressively."""
        from confluence_markdown_exporter.sync import export_and_track

        mock_page = MagicMock()
        mock_page.id = 100
        mock_page.page_version = 3
        mock_page.export_path = Path("spaces/ENG/page.md")
        mock_page_cls.from_id.return_value = mock_page

        state = _make_state()

        export_and_track([100], state, tmp_path)

        # Page should be exported (no state args — clean domain call)
        mock_page.export.assert_called_once_with()
        # State should be updated with page info
        mock_update.assert_called_once_with(
            state,
            page_id="100",
            version=3,
            output_path="spaces/ENG/page.md",
        )
        # State should be saved after each page
        mock_save.assert_called_once_with(tmp_path, state)

    @patch("confluence_markdown_exporter.sync.save_state")
    @patch("confluence_markdown_exporter.sync.update_page_state")
    @patch("confluence_markdown_exporter.sync.Page")
    def test_multiple_pages_tracked_progressively(
        self,
        mock_page_cls: MagicMock,
        mock_update: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Multiple pages are each exported and tracked in sequence."""
        from confluence_markdown_exporter.sync import export_and_track

        page_a = MagicMock()
        page_a.id = 1
        page_a.page_version = 2
        page_a.export_path = Path("a.md")

        page_b = MagicMock()
        page_b.id = 2
        page_b.page_version = 5
        page_b.export_path = Path("b.md")

        mock_page_cls.from_id.side_effect = [page_a, page_b]

        state = _make_state()
        export_and_track([1, 2], state, tmp_path)

        assert mock_page_cls.from_id.call_count == 2
        assert page_a.export.call_count == 1
        assert page_b.export.call_count == 1
        assert mock_update.call_count == 2
        assert mock_save.call_count == 2

    @patch("confluence_markdown_exporter.sync.save_state")
    @patch("confluence_markdown_exporter.sync.update_page_state")
    @patch("confluence_markdown_exporter.sync.Page")
    def test_empty_page_list(
        self,
        mock_page_cls: MagicMock,
        mock_update: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Empty page list does nothing."""
        from confluence_markdown_exporter.sync import export_and_track

        state = _make_state()
        export_and_track([], state, tmp_path)

        mock_page_cls.from_id.assert_not_called()
        mock_update.assert_not_called()
        mock_save.assert_not_called()

    @patch("confluence_markdown_exporter.sync.save_state")
    @patch("confluence_markdown_exporter.sync.update_page_state")
    @patch("confluence_markdown_exporter.sync.Page")
    def test_skips_inaccessible_pages(
        self,
        mock_page_cls: MagicMock,
        mock_update: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Inaccessible pages (title='Page not accessible') are skipped for state tracking."""
        from confluence_markdown_exporter.sync import export_and_track

        mock_page = MagicMock()
        mock_page.id = 999
        mock_page.title = "Page not accessible"
        mock_page.page_version = 0
        mock_page.export_path = Path()
        mock_page_cls.from_id.return_value = mock_page

        state = _make_state()
        export_and_track([999], state, tmp_path)

        # export() is still called (it handles the skip internally)
        mock_page.export.assert_called_once_with()
        # But state should NOT be updated for inaccessible pages
        mock_update.assert_not_called()
        mock_save.assert_not_called()
