---
id: usage
title: Usage
sidebar_position: 2
---

# Usage

Run the exporter with the desired Confluence page URL or space URL. Execute the console application by typing `confluence-markdown-exporter` (or its shorter alias `cme`) followed by one of the commands `pages`, `pages-with-descendants`, `spaces`, `orgs`, or `config`. Add `--help` to any command for additional information.

All export commands accept one or more URLs as space-separated arguments. Each command also has a singular alias (`page`, `page-with-descendants`, `space`, `org`) that behaves identically.

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

## Export spaces

Export all Confluence pages of one or more spaces by URL:

```sh
cme spaces <space-url>
cme spaces <space-url-1> <space-url-2> ...

# Singular alias (identical behaviour):
cme space <space-url>
```

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
