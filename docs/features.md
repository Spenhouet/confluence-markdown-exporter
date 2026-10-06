---
title: Features
---

# Features

Exports individual pages, pages with descendants, folders, or entire spaces via the Atlassian API. Skips unchanged pages by default, re-exporting only what has changed since the last run.

## Supported Confluence features

### Content & formatting

- **Rich text**: headings, paragraphs, bold, italic, underline, lists, tables, links, images, attachments, and image captions
- **Page links**: links to Confluence pages become relative Markdown links, whether they were inserted as page links, pasted as full page URLs, or pasted as tiny links (`/wiki/x/...`, the "Copy link" shortlink)
- **Images**: saved as local attachment files and linked, or embedded as base64 data URIs with [`export.embed_images`](./configuration/options.md#exportembed_images)
- **Emoticons**: Cloud emoji and Server/Data Center emoticons converted to Unicode characters
- **File previews**: the View File / PDF preview macro (`viewpdf`) becomes a link to the attachment
- **Code blocks**: language-aware fenced code blocks
- **Task lists**: checkboxes with completion state
- **Text highlights & font colours**: preserved with inline HTML colour styling
- **Status badges**: converted to coloured inline highlights
- **Info / note / tip / warning panels**: converted to Markdown alert blocks (`[!NOTE]`, `[!TIP]`, …)
- **Comments**: open inline and/or page-level (footer) comments exported as sidecar files next to each page
- **Include / excerpt-include macros**: embedded pages either inlined or exported as Obsidian transclusion links (`![[Page Title]]`)

### Page metadata

- **Page properties**: Page Properties macro exported as YAML front matter, [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) inline fields, or [Meta Bind](https://www.moritzjung.dev/obsidian-meta-bind-plugin-docs/) VIEW fields; duplicate keys are disambiguated automatically (configurable via [`export.page_properties_format`](./configuration/options.md#exportpage_properties_format))
- **Page Properties Report**: dynamic cross-page property tables exported as a static snapshot or a live [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) DQL query (configurable via [`export.page_properties_report_format`](./configuration/options.md#exportpage_properties_report_format)). Reports nested inside a third-party app macro (for example [Table Filter](https://marketplace.atlassian.com/apps/27447/table-filter-charts-spreadsheets-for-confluence)) are also exported. Note that such apps apply their filtering, sorting and column hiding in the browser, and that behaviour is not available through the API, so the export contains the full unfiltered report.
- **Page labels**: exported as `tags` in YAML front matter

### Diagrams & add-ons

- **[draw.io](https://marketplace.atlassian.com/apps/1210933/draw-io-diagrams-uml-bpmn-aws-erd-flowcharts)**: diagram files saved as attachments and shown via their preview image, on Cloud and on Server/Data Center; embedded Mermaid diagrams extracted as fenced Mermaid blocks
- **Gliffy**: diagrams shown via their preview image; the diagram source is saved with a `.gliffy` extension
- **[PlantUML](https://marketplace.atlassian.com/apps/1222993/flowchart-plantuml-diagrams-for-confluence)**: exported as fenced PlantUML code blocks, both the Server/Data Center macro (`plantuml`) and the Cloud macro (`plantumlcloud`), including the Forge version of the Cloud app; the diagram source is exported, not the rendered image. A diagram whose source cannot be found is exported as a `<!-- PlantUML diagram (source not found) -->` comment and logged as a warning
- **[Markdown Extensions](https://marketplace.atlassian.com/apps/1215703/markdown-extensions-for-confluence)**: pass-through of raw Markdown macro content

### Output layout

- **Path templates**: page and attachment paths are built from templates ([`export.page_path`](./configuration/options.md#exportpage_path), [`export.attachment_path`](./configuration/options.md#exportattachment_path))
- **Directory index pages**: parent pages can be exported as `index.md` or `README.md` inside a directory named after the page ([`export.page_path_if_parent`](./configuration/options.md#exportpage_path_if_parent))
- **Stale file cleanup**: files of pages that were deleted, renamed or moved in Confluence are removed on the next run
