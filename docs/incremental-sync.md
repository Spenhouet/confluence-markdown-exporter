# Incremental Sync

Incremental sync allows you to update a previously exported set of Confluence pages without re-downloading everything. After the initial export, subsequent runs only fetch and re-export pages that have actually changed, saving time and API calls.

## Problem

Without incremental sync, every export run:

- Re-fetches all page metadata and content from the Confluence API
- Re-converts and re-writes every markdown file, even if nothing changed
- Loses all progress if interrupted (timeout, network error, rate limit)

For large Confluence instances with thousands of pages, this makes regular syncing impractical.

## How It Works

### State File

When you run any export command (`pages`, `pages-with-descendants`, `spaces`, `all-spaces`), the tool automatically creates a state file named `.cme-state.json` in the output directory. This file tracks:

- **Confluence URL** -- ensures state is not accidentally mixed between different Confluence instances
- **Scopes** -- which commands and arguments were used (e.g., `spaces Engineering`)
- **Per-page state** -- the Confluence version number, last export timestamp, output file path, and whether the page is active or deleted

The state file lives in the output directory so it stays alongside the exported content and can be version-controlled if desired.

### Change Detection

The tool uses **Confluence page version numbers** (monotonically increasing integers from the Confluence API) as the primary change detection mechanism. This is more reliable than timestamps:

- If a page's Confluence version is higher than the stored version, it gets re-exported
- If versions match, the page is skipped (unchanged)
- Pages present in Confluence but not in the state file are treated as new
- Pages tracked in state but no longer in Confluence are treated as deleted

## Workflow

### Initial Export

Run any export command as usual:

```sh
confluence-markdown-exporter spaces ENGINEERING --output-path ./output/
```

This creates the markdown files and the `.cme-state.json` state file in `./output/`.

### Subsequent Syncs

Instead of re-running the export command, use `sync`:

```sh
confluence-markdown-exporter sync --output-path ./output/
```

The sync command:

1. Loads the state file from the output directory
2. Replays the original export scopes against the Confluence API (lightweight metadata calls)
3. Computes a delta -- which pages are new, modified, deleted, or unchanged
4. Exports only new and modified pages; deletes orphaned local files
5. Updates the state file

Output is a git-status-style report:

```
  new:  Engineering/Architecture/new-design.md
  mod:  Engineering/Runbooks/on-call.md
  del:  Marketing/Old Campaign/brief.md
3 new, 1 modified, 1 deleted, 496 unchanged
```

### Adding More Scopes

If you want to add another space or page set to an existing export, use the `--append` flag:

```sh
confluence-markdown-exporter spaces MARKETING --output-path ./output/ --append
```

Without `--append`, the export command will refuse to run if a state file already exists, directing you to use `sync` instead.

### Checking Status

To see what is being tracked without contacting the Confluence API:

```sh
confluence-markdown-exporter status --output-path ./output/
```

This shows the tracked scopes, total page count, and active/deleted breakdown.

## Commands Reference

### `sync`

```sh
confluence-markdown-exporter sync [--output-path PATH] [--force] [--dry-run]
```

Incrementally sync previously exported pages. Requires a state file from a prior export.

| Flag | Description |
|------|-------------|
| `--force` | Re-export all pages regardless of version. Useful when the export format or configuration has changed. |
| `--dry-run` | Show what would change without modifying any files or state. |

**How `--force` works:** Sets an internal `min_export_timestamp` so that all pages are considered stale, even if their Confluence version has not changed. Pages that are not processed during a forced run (e.g., due to a crash) will still be re-exported on the next sync.

### `status`

```sh
confluence-markdown-exporter status [--output-path PATH]
```

Display the local state of a previous export. Makes no API calls.

Output includes:

- Confluence URL
- Schema version
- Export scopes (command and arguments)
- Total pages tracked, with active and deleted counts

### Export Commands (`--append` flag)

All export commands (`pages`, `pages-with-descendants`, `spaces`, `all-spaces`) accept `--append`:

```sh
confluence-markdown-exporter pages <page-id> --output-path ./output/ --append
confluence-markdown-exporter spaces <space-key> --output-path ./output/ --append
```

| Behavior | Without `--append` | With `--append` |
|----------|-------------------|-----------------|
| No state file | Creates new state file | Creates new state file |
| State file exists | Error (use `sync` instead) | Adds scope to existing state |

## Error Handling

### Interrupted Runs

The state file is updated progressively as each page is exported. If a run is interrupted (network error, timeout, Ctrl+C), pages that were already exported are tracked in state. The next `sync` picks up where it left off.

### Confluence URL Mismatch

If the Confluence URL in your current configuration does not match the URL stored in the state file, the tool will refuse to proceed with a clear error message. This prevents accidentally mixing content from different Confluence instances.

### Permission Changes

If a page becomes inaccessible (e.g., permissions revoked), it is treated as deleted during sync. The local file is removed and the page is marked as deleted in state.

### Duplicate Scopes

When using `--append`, if the exact scope (command + arguments) already exists in the state file, it is silently ignored rather than duplicated.

## State File Schema

The `.cme-state.json` file uses the following structure:

```json
{
  "schema_version": 1,
  "confluence_url": "https://mycompany.atlassian.net",
  "scopes": [
    {"command": "spaces", "args": ["ENGINEERING"]},
    {"command": "pages", "args": ["645208921"]}
  ],
  "min_export_timestamp": null,
  "pages": {
    "12345": {
      "version": 42,
      "last_exported": "2026-02-05T14:30:00Z",
      "output_path": "Engineering/Architecture/design-doc.md",
      "status": "active"
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `schema_version` | Schema version for future migrations. Currently `1`. |
| `confluence_url` | The Confluence instance this state belongs to. |
| `scopes` | List of export commands and their arguments. |
| `min_export_timestamp` | Set by `--force`. Pages exported before this time are re-exported. |
| `pages` | Map of page ID to page state. |
| `pages.<id>.version` | Confluence page version number at time of export. |
| `pages.<id>.last_exported` | UTC timestamp of when this page was last exported. |
| `pages.<id>.output_path` | Relative path to the exported markdown file. |
| `pages.<id>.status` | `active` or `deleted`. |

The state file is safe to commit to version control.
