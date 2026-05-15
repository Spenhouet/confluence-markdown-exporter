---
id: features
title: Features
sidebar_position: 3
---

# Features

Exports individual pages, pages with descendants, or entire spaces via the Atlassian API. Skips unchanged pages by default, re-exporting only what has changed since the last run.

## Supported Confluence features

### Content & formatting

- **Rich text**: headings, paragraphs, bold, italic, underline, lists, tables, links, images, attachments, and image captions
- **Code blocks**: language-aware fenced code blocks
- **Task lists**: checkboxes with completion state
- **Text highlights & font colours**: preserved with inline HTML colour styling
- **Status badges**: converted to coloured inline highlights
- **Info / note / tip / warning panels**: converted to Markdown alert blocks (`[!NOTE]`, `[!TIP]`, …)
- **Comments**: open inline and/or page-level (footer) comments exported as sidecar files next to each page
- **Include / excerpt-include macros**: embedded pages either inlined or exported as Obsidian transclusion links (`![[Page Title]]`)

### Page metadata

- **Page properties**: Page Properties macro exported as YAML front matter, [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) inline fields, or [Meta Bind](https://www.moritzjung.dev/obsidian-meta-bind-plugin-docs/) VIEW fields; duplicate keys are disambiguated automatically (configurable via [`export.page_properties_format`](./configuration/options.md#exportpage_properties_format))
- **Page Properties Report**: dynamic cross-page property tables exported as a static snapshot or a live [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) DQL query (configurable via [`export.page_properties_report_format`](./configuration/options.md#exportpage_properties_report_format))
- **Page labels**: exported as `tags` in YAML front matter

### Diagrams & add-ons

- **[draw.io](https://marketplace.atlassian.com/apps/1210933/draw-io-diagrams-uml-bpmn-aws-erd-flowcharts)**: diagram files saved as attachments; embedded Mermaid diagrams extracted as fenced Mermaid blocks
- **[PlantUML](https://marketplace.atlassian.com/apps/1222993/flowchart-plantuml-diagrams-for-confluence)**: exported as fenced PlantUML code blocks
- **[Markdown Extensions](https://marketplace.atlassian.com/apps/1215703/markdown-extensions-for-confluence)**: pass-through of raw Markdown macro content
