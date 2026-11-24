---
title: Usage
---

# Usage

Run the exporter with the desired Confluence page URL or space URL. Execute the console application by typing `confluence-markdown-exporter` (or its shorter alias `cme`) followed by one of the commands `pages`, `pages-with-descendants`, `folders`, `spaces`, `orgs`, or `config`. Add `--help` to any command for additional information.

All export commands accept one or more URLs as space-separated arguments. Each command also has a singular alias (`page`, `page-with-descendants`, `folder`, `space`, `org`) that behaves identically.

## Export pages

Export one or more Confluence pages by URL:

```sh
cme pages <page-url>
cme pages <page-url-1> <page-url-2> ...

# Singular alias (identical behaviour):
cme page <page-url>
```

Supported page URL formats:

- Confluence Cloud: `https://company.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Page+Title`
- Confluence Cloud (API gateway): `https://api.atlassian.com/ex/confluence/CLOUDID/wiki/spaces/SPACEKEY/pages/123456789/Page+Title`
- Confluence Server (long): `https://wiki.company.com/display/SPACEKEY/Page+Title`
- Confluence Server (short): `https://wiki.company.com/SPACEKEY/Page+Title`
- Confluence Server (param): `https://wiki.company.com/pages/viewpage.action?pageId=123456789`

## Export pages with descendants

Export one or more Confluence pages and all their descendant pages by URL:

```sh
cme pages-with-descendants <page-url>
cme pages-with-descendants <page-url-1> <page-url-2> ...

# Singular alias (identical behaviour):
cme page-with-descendants <page-url>
```

## Export folders

Export every page in one or more Confluence Cloud folders by URL, including pages in nested folders:

```sh
cme folders <folder-url>
cme folders <folder-url-1> <folder-url-2> ...

# Singular alias (identical behaviour):
cme folder <folder-url>
```

Folder URLs look like `https://company.atlassian.net/wiki/spaces/SPACEKEY/folder/123456789`. Folders exist on Confluence Cloud only.

## Export spaces

Export all Confluence pages of one or more spaces by URL:

```sh
cme spaces <space-url>
cme spaces <space-url-1> <space-url-2> ...

# Singular alias (identical behaviour):
cme space <space-url>
```

A space export covers the space homepage and every page beneath it. Pages outside that tree, such as a second root page, are skipped and a warning reports how many. Set [`export.only_homepage_descendants`](configuration/options.md#exportonly_homepage_descendants) to `false` to include them.

Supported space URL formats:

- Confluence Cloud: `https://company.atlassian.net/wiki/spaces/SPACEKEY`
- Confluence Cloud (API gateway): `https://api.atlassian.com/ex/confluence/CLOUDID/wiki/spaces/SPACEKEY`
- Confluence Server (long): `https://wiki.company.com/display/SPACEKEY`
- Confluence Server (short): `https://wiki.company.com/SPACEKEY`

## Export all spaces of an organization

Export all Confluence pages across all spaces of one or more organizations by URL:

```sh
cme orgs <base-url>
cme orgs <base-url-1> <base-url-2> ...

# Singular alias (identical behaviour):
cme org <base-url>
```

## Databases

Confluence Cloud databases inside an exported space, folder or page tree are exported according to [`export.database_export`](configuration/options.md#exportdatabase_export) (default: `table`). When set to `table`, the database schema fields and row entries are fetched via the Confluence REST API and formatted as a Markdown table (or HTML table depending on `export.table_format`). You can also export raw CSV or JSON sidecars via [`export.database_formats`](configuration/options.md#exportdatabase_formats). If the database REST API is inaccessible or fails, the exporter gracefully falls back to generating a placeholder page with a link to the original database. Set `export.database_export` to `placeholder` for fallback link pages only, or `none` to skip databases. Database URLs (e.g. `https://company.atlassian.net/wiki/spaces/KEY/database/123/Tasks`) can also be exported directly using `cme pages URL` or the `cme database URL` / `cme databases URL` aliases.

**Limitations:**

- **Entry backlink display options:** When [`export.database_resolve_depth`](configuration/options.md#exportdatabase_resolve_depth) is greater than `0`, `backlink` fields always render the list of referencing entries. The Confluence Cloud *"Display as: Number of items linked to entry"* column option cannot be preserved because the Confluence Cloud REST API v2 does not expose backlink display settings or view configurations.

## Output layout

The exported Markdown file(s) will be saved in the configured output directory (see [`export.output_path`](./configuration/options.md#exportoutput_path)) e.g.:

```text
output_path/
└── MYSPACE/
   ├── MYSPACE.md
   └── MYSPACE/
      ├── My Confluence Page.md
      └── My Confluence Page/
            ├── My nested Confluence Page.md
            └── Another one.md
```
