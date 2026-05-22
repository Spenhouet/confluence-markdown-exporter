---
id: options
title: Configuration options
sidebar_label: Options reference
sidebar_position: 2
---

# Configuration options

Reference for every supported option. All options can be set via `cme config set <key>=<value>` or overridden per-session through the listed environment variable.

## export.\*

### export.log_level

Controls output verbosity: `DEBUG` (every step), `INFO` (key milestones), `WARNING` (warnings/errors only), `ERROR` (errors only).

- Default: `INFO`
- ENV Var: `CME_EXPORT__LOG_LEVEL`

### export.output_path

The directory where all exported files and folders will be written. Used as the base for relative and absolute links.

- Default: `./` (current working directory)
- ENV Var: `CME_EXPORT__OUTPUT_PATH`

### export.page_href

How to generate links to pages in Markdown. Options: `relative` (default), `absolute`, or `wiki`.

- Default: `relative`
- ENV Var: `CME_EXPORT__PAGE_HREF`

| Value      | Output                                 |
| ---------- | -------------------------------------- |
| `relative` | `[Page Title](../path/to/page.md)`     |
| `absolute` | `[Page Title](/space/path/to/page.md)` |
| `wiki`     | `[[Page Title]]`                       |

### export.page_path

Path template for exported pages.

- Default: `{space_name}/{homepage_title}/{ancestor_titles}/{page_title}.md`
- ENV Var: `CME_EXPORT__PAGE_PATH`

### export.attachment_href

How to generate links to attachments in Markdown. Options: `relative` (default), `absolute`, or `wiki`.

- Default: `relative`
- ENV Var: `CME_EXPORT__ATTACHMENT_HREF`

| Value      | Output                                                                             |
| ---------- | ---------------------------------------------------------------------------------- |
| `relative` | `[file.pdf](../path/to/file.pdf)` / `![alt](../path/to/image.png)`                 |
| `absolute` | `[file.pdf](/space/attachments/file.pdf)` / `![alt](/space/attachments/image.png)` |
| `wiki`     | `[[file.pdf\|File Title]]` / `![[image.png]]`                                      |

### export.attachment_path

Path template for attachments.

- Default: `{space_name}/attachments/{attachment_file_id}{attachment_extension}`
- ENV Var: `CME_EXPORT__ATTACHMENT_PATH`

On Confluence Data Center / Server, where the API does not provide `fileId`, `{attachment_file_id}` falls back to the content id, so the default template still produces unique filenames.

### export.attachments_export

Which attachments to download to disk.

| Value        | Behaviour                                                                                                                                                                     |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `referenced` | Only attachments whose ID/filename appears in the page body (default).                                                                                                        |
| `all`        | Every attachment on the page. Large or numerous attachments increase export time.                                                                                             |
| `disabled`   | Skip downloads entirely: no files written, no lockfile entries, no lookup. Body image and file links still point at `attachment_path`, but the files will not exist locally. |

- Default: `referenced`
- ENV Var: `CME_EXPORT__ATTACHMENTS_EXPORT`

### export.image_captions

Whether to export Confluence image captions in the exported Markdown. When enabled, the storage format of each page is fetched (via an additional API body expansion) and `ac:image` captions are extracted and rendered as an italic line directly below the image:

```markdown
![](image.png)
_Caption text_
```

When disabled, no caption is added.

- Default: `False`
- ENV Var: `CME_EXPORT__IMAGE_CAPTIONS`

### export.page_breadcrumbs

Whether to include breadcrumb links at the top of the page.

- Default: `True`
- ENV Var: `CME_EXPORT__PAGE_BREADCRUMBS`

### export.page_properties_format

Controls how Confluence Page Properties macros (key-value tables) are rendered. Duplicate property keys are automatically disambiguated by appending a counter (e.g. `status`, `status_2`, `status_3`).

| Value                   | Description                                                                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontmatter`           | Extract to YAML front matter; table is removed from the page body                                                                            |
| `table`                 | Keep as a regular markdown table; no metadata is written                                                                                     |
| `frontmatter_and_table` | Write to YAML front matter **and** keep the original table in the body (default)                                                             |
| `dataview-inline-field` | Replace the table with [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) `Key:: Value` inline fields                             |
| `meta-bind-view-fields` | Write YAML front matter and a table using [Meta Bind](https://www.moritzjung.dev/obsidian-meta-bind-plugin-docs/) `VIEW[{key}][text]` fields |

:::info Migration
The legacy `page_properties_as_front_matter=true/false` is still accepted and maps to `frontmatter` / `table` respectively.
:::

- Default: `frontmatter_and_table`
- ENV Var: `CME_EXPORT__PAGE_PROPERTIES_FORMAT`

### export.page_properties_report_format

Controls how Confluence Page Properties Report macros (dynamic cross-page property tables) are rendered.

| Value      | Description                                                                                                                                                                                                                                                                                                |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frozen`   | Export the rendered table as a static markdown table snapshot (default)                                                                                                                                                                                                                                    |
| `dataview` | Translate the CQL query to an [Obsidian Dataview](https://blacksmithgu.github.io/obsidian-dataview/) DQL code block; requires the Dataview plugin and all referenced child pages to be exported with their page properties as front matter; falls back to a frozen table if the query cannot be translated |

- Default: `frozen`
- ENV Var: `CME_EXPORT__PAGE_PROPERTIES_REPORT_FORMAT`

### export.confluence_url_in_frontmatter

Whether to include the original Confluence page URL in the YAML front matter of the exported file.

| Value    | Description                                                                                               |
| -------- | --------------------------------------------------------------------------------------------------------- |
| `none`   | Do not include any URL (default)                                                                          |
| `webui`  | Include `confluence_webui_url` (human-readable URL; may change when the page is renamed or moved)         |
| `tinyui` | Include `confluence_tinyui_url` (stable short permalink based on the page ID; survives renames and moves) |
| `both`   | Include both fields                                                                                       |

If a Page Properties macro on the page already defines `confluence_webui_url` or `confluence_tinyui_url`, the value from the macro takes precedence over the URL extracted from the API.

- Default: `none`
- ENV Var: `CME_EXPORT__CONFLUENCE_URL_IN_FRONTMATTER`

### export.page_metadata_in_frontmatter

Add eight Confluence page metadata fields to the YAML front matter of each exported page.

| Field | Source |
| ----- | ------ |
| `confluence_page_id` | Page ID (string) |
| `confluence_space_key` | Space key |
| `confluence_type` | Content type (`page` or `blogpost`) |
| `confluence_created` | ISO 8601 timestamp of when the page was first created (`history.createdDate`) |
| `confluence_created_by` | Display name of the original author (`history.createdBy.displayName`) |
| `confluence_last_modified` | ISO 8601 timestamp of the most recent version (`version.when`), including minor edits |
| `confluence_last_modified_by` | Display name of the last editor |
| `confluence_version` | Version number (integer) |

Fields with empty or zero values are omitted. If a Page Properties macro on the page already defines a key with the same name, the macro value takes precedence.

`confluence_page_id` is intentionally written as a quoted string (e.g. `'629839369'`) rather than an integer. Confluence Cloud page IDs can exceed JavaScript's safe-integer range (`2^53 − 1`), so JS-based static site generators (Hugo, Astro, …) parsing the front matter would silently truncate them. `confluence_created` and `confluence_last_modified` are also quoted because PyYAML wraps ISO-8601 timestamps with timezone offsets to prevent loaders from coercing the value into a `datetime` object.

Example front matter with both `confluence_url_in_frontmatter: webui` and `page_metadata_in_frontmatter: true`:

```yaml
---
tags:
  - team-foo
confluence_webui_url: https://.../wiki/spaces/.../pages/123/Title
confluence_page_id: '123'
confluence_space_key: TEAM
confluence_type: page
confluence_created: "2024-08-15T08:34:12.000+02:00"
confluence_created_by: Sam Creator
confluence_last_modified: "2026-04-12T10:34:00.000+02:00"
confluence_last_modified_by: Alex Johnson
confluence_version: 7
---
```

- Default: `false`
- ENV Var: `CME_EXPORT__PAGE_METADATA_IN_FRONTMATTER`

### export.filename_encoding

Character mapping for filename encoding.

- Default: Default mappings for forbidden characters.
- ENV Var: `CME_EXPORT__FILENAME_ENCODING`

### export.filename_length

Maximum length of filenames.

- Default: `255`
- ENV Var: `CME_EXPORT__FILENAME_LENGTH`

### export.filename_lowercase

Make all exported paths and filenames lowercase. By default the original casing from Confluence is retained.

- Default: `False`
- ENV Var: `CME_EXPORT__FILENAME_LOWERCASE`

### export.include_document_title

Whether to include the document title in the exported markdown file. If enabled, the title will be added as a top-level heading.

- Default: `True`
- ENV Var: `CME_EXPORT__INCLUDE_DOCUMENT_TITLE`

### export.include_toc

Whether to export the Confluence Table of Contents macro. When enabled, the TOC is converted to markdown. When disabled, the TOC macro is removed from the output.

- Default: `True`
- ENV Var: `CME_EXPORT__INCLUDE_TOC`

### export.include_macro

Controls how Confluence `include` and `excerpt-include` macros are rendered. The `include` macro embeds the full content of another page; `excerpt-include` embeds a named excerpt from another page.

| Value          | Behaviour                                                                                                                                                                     |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `inline`       | Expand the referenced page content inline at the point of inclusion (default). The body already rendered by Confluence is used, so no extra API calls are required.           |
| `transclusion` | Emit an Obsidian-style `![[Page Title]]` embed link. Obsidian renders the link as an inline preview of the target note. The referenced page must also be exported to resolve. |

- Default: `inline`
- ENV Var: `CME_EXPORT__INCLUDE_MACRO`

### export.enable_jira_enrichment

Fetch Jira issue data to enrich Confluence pages. When enabled, Jira issue links include the issue summary. Requires Jira auth to be configured.

- Default: `True`
- ENV Var: `CME_EXPORT__ENABLE_JIRA_ENRICHMENT`

### export.comments_export

Which comments to export to a sidecar `.comments.md` file placed next to the exported page file, using the same path stem.

| Value      | Behaviour                                                                                |
| ---------- | ---------------------------------------------------------------------------------------- |
| `none`     | No sidecar (default).                                                                    |
| `inline`   | Open inline comments only (annotated text as blockquote, then author / date / body).     |
| `footer`   | Open page-level (footer) comments only.                                                  |
| `all`      | Both, in a single sidecar with `## Inline comments` first, then `## Page comments`.      |

Only open comments are included; resolved comments are skipped. Replies are listed flat below their parent comment. Disabled by default; enabling adds one to two extra API calls per page.

Sidecar example for `comments_export = "all"`:

```markdown
---
confluence_page_id: '123'
confluence_page_title: "Example Page"
confluence_webui_url: "https://example.atlassian.net/wiki/spaces/TEAM/pages/123"
---

## Inline comments

### marked excerpt
> marked excerpt

**Alice** · 2026-04-01

Looks good to me.

## Page comments

### Discussion about the rollout

**Bob** · 2026-04-02

Are we shipping this Friday?
```

The legacy boolean key `inline_comments` is migrated automatically: `true` becomes `"inline"`, `false` becomes `"none"`.

- Default: `none`
- ENV Var: `CME_EXPORT__COMMENTS_EXPORT`

### export.convert_status_badges

Whether to convert Confluence status badge macros to HTML `<mark>` elements coloured with the badge's background colour. Each lozenge variant maps to an Atlassian design-system pastel:

| Lozenge        | Colour          | Hex       |
| -------------- | --------------- | --------- |
| Gray (default) | Gray            | `#dfe1e6` |
| Blue           | Blue            | `#cce0ff` |
| Green          | Green           | `#baf3db` |
| Yellow         | Yellow / Orange | `#f8e6a0` |
| Red            | Red             | `#ffd5d2` |
| Purple         | Purple / Violet | `#dfd8fd` |

When disabled, only the badge label text is kept.

- Default: `True`
- ENV Var: `CME_EXPORT__CONVERT_STATUS_BADGES`

### export.convert_text_highlights

Whether to convert Confluence text highlights (`<span style="background-color: rgb(...);">`) to HTML `<mark>` elements with a hex color value. When disabled, the highlight span is stripped and only the plain text is kept.

- Default: `True`
- ENV Var: `CME_EXPORT__CONVERT_TEXT_HIGHLIGHTS`

### export.convert_font_colors

Whether to convert Confluence font colors to HTML `<font>` elements with a hex color value. Handles both inline-style spans (`<span style="color: rgb(...);">`) and CSS-class-based spans (`<span data-colorid="...">`) used in the Confluence export view. When disabled, the color span is stripped and only the plain text is kept.

- Default: `True`
- ENV Var: `CME_EXPORT__CONVERT_FONT_COLORS`

### export.skip_unchanged

Skip exporting pages that have not changed since last export. Uses a lockfile to track page versions.

- Default: `True`
- ENV Var: `CME_EXPORT__SKIP_UNCHANGED`

### export.cleanup_stale

After export, delete local files for pages removed from Confluence or whose export path has changed.

- Default: `True`
- ENV Var: `CME_EXPORT__CLEANUP_STALE`

### export.lockfile_name

Name of the lock file used to track exported pages.

- Default: `confluence-lock.json`
- ENV Var: `CME_EXPORT__LOCKFILE_NAME`

### export.existence_check_batch_size

Number of page IDs per batch when checking page existence during cleanup. Capped at 25 for self-hosted (CQL).

- Default: `250`
- ENV Var: `CME_EXPORT__EXISTENCE_CHECK_BATCH_SIZE`

## connection_config.\*

### connection_config.backoff_and_retry

Enable or disable automatic retry with exponential backoff on network errors.

- Default: `True`
- ENV Var: `CME_CONNECTION_CONFIG__BACKOFF_AND_RETRY`

### connection_config.backoff_factor

Multiplier for exponential backoff between retries. For example, `2` means each retry waits twice as long as the previous.

- Default: `2`
- ENV Var: `CME_CONNECTION_CONFIG__BACKOFF_FACTOR`

### connection_config.max_backoff_seconds

Maximum seconds to wait between retries.

- Default: `60`
- ENV Var: `CME_CONNECTION_CONFIG__MAX_BACKOFF_SECONDS`

### connection_config.max_backoff_retries

Maximum number of retry attempts before giving up.

- Default: `5`
- ENV Var: `CME_CONNECTION_CONFIG__MAX_BACKOFF_RETRIES`

### connection_config.retry_status_codes

HTTP status codes that trigger a retry.

- Default: `[413, 429, 502, 503, 504]`
- ENV Var: `CME_CONNECTION_CONFIG__RETRY_STATUS_CODES`

### connection_config.timeout

Timeout in seconds for API requests. Prevents hanging on slow or unresponsive servers.

- Default: `30`
- ENV Var: `CME_CONNECTION_CONFIG__TIMEOUT`

### connection_config.verify_ssl

Whether to verify SSL certificates for HTTPS requests. Set to `False` only if you are sure about the security of your connection.

- Default: `True`
- ENV Var: `CME_CONNECTION_CONFIG__VERIFY_SSL`

### connection_config.use_v2_api

Enable Confluence REST API v2 endpoints. Supported on Atlassian Cloud and Data Center 8+. Disable for self-hosted Server instances.

- Default: `False`
- ENV Var: `CME_CONNECTION_CONFIG__USE_V2_API`

### connection_config.max_workers

Maximum number of parallel workers for page export. Set to `1` for serial/debug mode. Higher values improve performance but may hit API rate limits.

- Default: `20`
- ENV Var: `CME_CONNECTION_CONFIG__MAX_WORKERS`
