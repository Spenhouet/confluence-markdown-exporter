---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
product_contract_source: ce-plan-bootstrap
origin: https://github.com/Spenhouet/confluence-markdown-exporter/issues/278
created: 2026-07-16
plan_depth: lightweight
---

# fix: Decouple moved-page cleanup from deleted-page detection

## Summary

`sync_removed_pages()` deletes the old file left behind by a moved/renamed Confluence page — but only as an incidental side effect of `LockfileManager.remove_pages()`, which is skipped entirely whenever no page was genuinely deleted from Confluence in that run. Since a moved page is by definition "seen" this run, it can never itself make `unseen_ids()` non-empty, so the common case (some pages moved, none deleted) silently leaves stale files behind forever. This plan decouples the moved-page cleanup pass from the deleted-page detection pass so the former always runs when `export.cleanup_stale` is enabled.

**Product Contract preservation:** N/A — no upstream requirements document exists for this fix; this plan was written directly from GitHub issue [#278](https://github.com/Spenhouet/confluence-markdown-exporter/issues/278) (`product_contract_source: ce-plan-bootstrap`).

---

## Problem Frame

**Origin:** GitHub issue #278 (reported by an external user against a real, large Confluence Cloud space; repo owner `@Spenhouet` has already agreed to accept a PR).

When a page is renamed/moved in Confluence and re-exported:
1. `Page.export()` writes the file to its new `export_path`.
2. `LockfileManager.record_page()` updates the lock file entry's `export_path` immediately.
3. The **old file** at the previous `export_path` should be deleted by the "moved page" loop inside `LockfileManager.remove_pages()` (`confluence_markdown_exporter/utils/lockfile.py:320-327`).

Step 3 only happens today if `LockfileManager.remove_pages()` is actually called, and it is only called from `sync_removed_pages()` (`confluence_markdown_exporter/confluence.py:2968-2984`) — which returns early whenever `LockfileManager.unseen_ids()` is empty (`confluence.py:2974-2977`), *before* `remove_pages()` is ever invoked. A moved page is always in `_seen_page_ids` (it was just exported), so it never contributes to `unseen_ids()`. The only way the moved-page cleanup loop runs today is if some *unrelated* page also happens to be missing from Confluence in the same run — an incidental trigger, not a guarantee.

Net effect: in the overwhelmingly common case ("some pages moved, nothing deleted"), stale old-path files accumulate on every run, undetected, with nothing logged. Confirmed against a real space: ~57 orphaned pages and ~18 orphaned attachments after repeated renames with no coinciding deletions.

## Scope Boundaries

**In scope:**
- Making the moved-page old-file cleanup run whenever `export.cleanup_stale` is enabled, regardless of whether any page was deleted from Confluence in the same run.
- Keeping the "check Confluence API for genuinely deleted pages" pass gated behind `unseen_ids()` being non-empty (unchanged — no reason to hit the API when every tracked page was seen this run).

**Out of scope:**
- Any change to `export.cleanup_stale`'s meaning, default, or config surface — the setting already documents covering both moved-page and deleted-page cleanup (`docs/configuration/options.md:339-343`); no doc changes are needed.
- Attachment cleanup for *renamed/re-versioned* attachments — already handled independently in `Page.export_attachments()` (`confluence.py:1294-1300`), which runs on every export of the owning page regardless of this bug.

### Deferred to Follow-Up Work

- **Attachments belonging to a page that is genuinely deleted from Confluence are never cleaned up.** `LockfileManager.remove_deleted_pages()` (post-split; today's `remove_pages()`) only unlinks the page's own `export_path` — it never iterates `entry.attachments` to remove the attachment files tracked for that page. This is a real, adjacent orphan-file source (plausibly part of the "~18 orphaned attachments" reported in issue #278), but it is a distinct code path from what #278's root-cause analysis and suggested fix describe, and fixing it wasn't requested. Noting it explicitly here rather than silently leaving it undiscovered or silently bundling an unrequested scope change into this fix.

## Key Technical Decisions

**KTD1 — Follow the issue's suggested fix shape exactly: split `remove_pages()` into two independently-callable methods.**
Rationale: the reporter's suggested fix (`cleanup_moved_pages()` always called, `remove_deleted_pages(deleted_ids)` called only when `unseen` is non-empty) cleanly maps to the two existing, already-separately-tested behaviors in `LockfileManager`, and the repo owner has already signaled acceptance of a PR shaped this way. No alternative was seriously considered — the current single-method design is the direct cause of the bug, and splitting it is the smallest change that fixes it without touching unrelated logic (API batching, attachment handling, lockfile save/merge semantics all stay untouched).

**KTD2 — Keep `export.cleanup_stale` as the single gate this fix touches, unchanged.**
Rationale: its existing description ("delete local files for pages that have been removed from Confluence **or whose export path has changed**") already covers both behaviors; users who disable it expect *no* stale-file deletion of any kind. Only the internal `unseen_ids()` early-return needs to move — it should gate the deletion-detection API call, not the moved-page cleanup. Note this is not the *only* precondition for cleanup to run: `LockfileManager._lock` (and therefore the guard both new methods share) is only populated when `export.skip_unchanged` is also enabled (`utils/lockfile.py:210-212`) — a pre-existing coupling this plan inherits and does not change. A user with `cleanup_stale=True` but `skip_unchanged=False` will still see no moved-page cleanup after this fix, exactly as today; fixing that cross-setting dependency is out of scope here.

**KTD3 — Do not preserve `remove_pages()` as a deprecated wrapper.**
Rationale: it has exactly one production call site (`confluence.py:2984`) and no external/public API surface; keeping a compatibility shim would add dead code for no consumer.

---

## Implementation Units

### U1. Split `LockfileManager.remove_pages()` into `cleanup_moved_pages()` and `remove_deleted_pages()`

**Goal:** Extract the moved-page file-cleanup loop into its own classmethod that has no dependency on `deleted_ids`, and keep deleted-page removal as a second, separately-callable classmethod. Remove the combined `remove_pages()` method.

**Requirements:** Directly implements the root-cause fix described in issue #278's "Suggested fix" section.

**Dependencies:** None.

**Files:**
- `confluence_markdown_exporter/utils/lockfile.py` (modify `LockfileManager`, ~lines 308-344)

**Approach:**
- `cleanup_moved_pages(cls) -> None`: same guard as today (`_lock`/`_lockfile_path`/`_output_path` must all be set — return silently otherwise); iterate `_seen_page_ids`, and for each present in `_all_entries_snapshot`, compare its old `export_path` against the current `_lock.get_page(page_id).export_path`; on mismatch, `unlink(missing_ok=True)` the old file and log at `info` exactly as today's code does. No lockfile save needed here — `record_page()` already persisted the new path when the page was exported.
- `remove_deleted_pages(cls, deleted_ids: set[str]) -> None`: same guard; for each id in `deleted_ids`, look up the entry, unlink `entry.export_path`, log, and collect into `result_delete_ids`; if `result_delete_ids` is non-empty, save the lockfile with `delete_ids=result_delete_ids` and increment `stats.inc_removed()` once per removed page — identical semantics to today's second half of `remove_pages()`.
- Delete the now-unused combined `remove_pages()` method entirely.

**Patterns to follow:** Mirror the existing guard-clause style and logging phrasing already used in `remove_pages()` (`utils/lockfile.py:315-343`) — this is a structural split, not a behavior rewrite.

**Test scenarios** (`tests/unit/utils/test_lockfile.py`):
- `cleanup_moved_pages` deletes the old file when a seen page's `export_path` changed between `_all_entries_snapshot` and the current lock entry.
- `cleanup_moved_pages` leaves the file alone when a seen page's `export_path` is unchanged.
- `cleanup_moved_pages` is a no-op (does not raise) when the manager was never initialized (`_lock is None`).
- `remove_deleted_pages` deletes the file and removes the lockfile entry for a given deleted id, while an unrelated kept page's entry survives.
- `remove_deleted_pages` handles an already-missing file gracefully (`unlink(missing_ok=True)` — no exception).
- `remove_deleted_pages` is a no-op (does not raise, does not touch the lockfile) when called with an empty set.
- `remove_deleted_pages` is a no-op (does not raise) when the manager was never initialized.

**Verification:** `uv run pytest tests/unit/utils/test_lockfile.py -k "MovedPages or RemoveDeletedPages"` (or equivalent test-class names chosen in U3) passes; `remove_pages` no longer exists anywhere in `lockfile.py`.

---

### U2. Update `sync_removed_pages()` to always run moved-page cleanup, gating only the deletion check on unseen pages

**Goal:** Fix the actual reported defect — with `export.cleanup_stale` enabled, moved-page file cleanup must run on every export, independent of whether `unseen_ids()` is empty.

**Requirements:** This is the orchestration-level fix that makes issue #278's repro scenario ("rename a page, no other page deleted, re-run") produce the expected result.

**Dependencies:** U1 (needs `cleanup_moved_pages()` / `remove_deleted_pages()` to exist).

**Files:**
- `confluence_markdown_exporter/confluence.py` (modify `sync_removed_pages`, ~lines 2968-2984)

**Approach:**
```text
sync_removed_pages(base_url):
    if not cleanup_stale: return          # unchanged — single feature gate

    cleanup_moved_pages()                  # NEW: always runs, no longer gated on unseen

    unseen = unseen_ids()
    if not unseen: return                  # unchanged early-exit, now only skips the API check below

    deleted = fetch_deleted_page_ids(unseen, base_url)
    remove_deleted_pages(deleted)          # renamed call, same semantics as before
```
This is directional pseudo-code for the reviewer, not implementation syntax — the implementer keeps the existing `console.status`/logging calls around the `fetch_deleted_page_ids` step unchanged.

**Patterns to follow:** Existing structure and logging of `sync_removed_pages` (`confluence.py:2968-2984`) — only the call sequencing changes, not the surrounding logging/status-spinner conventions.

**Test scenarios** (new/extended, likely in `tests/unit/test_confluence.py` or alongside the lockfile tests — implementer's call on which file, given `sync_removed_pages` lives in `confluence.py`):
- Covers the exact issue #278 repro: `unseen_ids()` empty (nothing deleted this run) **and** a moved page present in `_seen_page_ids`/`_all_entries_snapshot` with a changed `export_path` → calling `sync_removed_pages(base_url)` still deletes the old file, and `fetch_deleted_page_ids` is never invoked (assert via mock/patch not called, or via no network call).
- `export.cleanup_stale` disabled → neither `cleanup_moved_pages` nor the deletion-detection path run at all (existing behavior preserved; assert both are not called).
- `unseen_ids()` non-empty → both the moved-page cleanup and the deletion-detection/removal path run in the same call, and a confirmed-deleted page's file and lockfile entry are removed.

**Verification:** Run the new regression test (name TBD by implementer, e.g. `test_sync_removed_pages_cleans_up_moved_page_without_deletions`) and confirm it fails against the pre-fix code path (early return before `cleanup_moved_pages` existed) and passes after the fix — the manual repro from the issue (rename a page, no other deletions, re-run) now leaves only the new-path file on disk.

---

### U3. Migrate the existing `TestLockfileManagerCleanup` suite onto the split API

**Goal:** Update every existing test that calls the now-removed `LockfileManager.remove_pages()` to call `cleanup_moved_pages()` and/or `remove_deleted_pages()` instead, preserving each test's original intent.

**Requirements:** Keeps existing coverage (moved-file deletion, deleted-file + lockfile-entry removal, already-deleted-file handling, API-failure safe-default, unchanged-seen-pages skip) green after the U1 rename/split.

**Dependencies:** U1.

**Files:**
- `tests/unit/utils/test_lockfile.py` (`TestLockfileManagerCleanup`, currently lines 341-487)

**Approach:** Split `TestLockfileManagerCleanup` into two classes (e.g. `TestLockfileManagerCleanupMovedPages` and `TestLockfileManagerRemoveDeletedPages`) so each test class maps to exactly one of the two new methods, matching the existing per-behavior test-class convention already used elsewhere in this file (`TestLockfileManagerInit`, `TestLockfileManagerRecordPage`, `TestLockfileManagerShouldExport`, `TestLockfileManagerMarkSeen`). Update each test body's final call from `LockfileManager.remove_pages(...)` to the appropriate new method with the appropriate argument (`cleanup_moved_pages()` takes no `deleted_ids` argument; `remove_deleted_pages(deleted_ids)` keeps the same argument shape as before). No test *setup* (fixture state: `_lock`, `_all_entries_snapshot`, `_seen_page_ids`, `_output_path`) needs to change — only the final call under test.

**Patterns to follow:** The existing per-method test-class grouping already present in this same file.

**Test scenarios:** This unit implements the scenarios enumerated under U1 (production split) by migrating and re-homing the 8 existing tests currently in `TestLockfileManagerCleanup` (`test_cleanup_noop_when_not_initialized`, `test_cleanup_deletes_file_for_removed_page`, `test_cleanup_removes_entry_from_lockfile`, `test_cleanup_deletes_old_file_for_moved_page`, `test_cleanup_keeps_page_existing_on_confluence`, `test_cleanup_keeps_unchanged_seen_pages`, `test_cleanup_handles_already_deleted_file`, `test_cleanup_api_failure_keeps_pages`) plus adding the one genuinely new scenario (`cleanup_moved_pages` no-op when `export_path` unchanged) called out in U1 that isn't already covered by an existing test.

**Verification:** `uv run pytest tests/unit/utils/test_lockfile.py` passes in full, with zero remaining references to `remove_pages` in the file (`grep -n "remove_pages" tests/unit/utils/test_lockfile.py` returns nothing).

---

## Verification Contract

- `uv run pytest tests/unit/utils/test_lockfile.py tests/unit/test_confluence.py` passes.
- `grep -rn "remove_pages" confluence_markdown_exporter/ tests/` returns no matches (method fully replaced, not shadowed).
- Manual trace of the issue's repro scenario confirms the fix: with `skip_unchanged=True` and `cleanup_stale=True`, moving/renaming a single page and re-exporting (no other page deleted) results in only the new-path file existing on disk and in the lock file; the old-path file is gone.

## Definition of Done

- [ ] U1: `cleanup_moved_pages()` and `remove_deleted_pages()` exist on `LockfileManager`; `remove_pages()` is removed.
- [ ] U2: `sync_removed_pages()` calls `cleanup_moved_pages()` unconditionally (once past the `cleanup_stale` gate) and only gates `fetch_deleted_page_ids`/`remove_deleted_pages()` on `unseen_ids()` being non-empty.
- [ ] U3: All lockfile cleanup tests updated and passing; new regression test in place proving the issue #278 repro is fixed.
- [ ] Verification Contract checks above all pass.
