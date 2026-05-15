<p align="center">
  <a href="https://github.com/Spenhouet/confluence-markdown-exporter"><img src="https://raw.githubusercontent.com/Spenhouet/confluence-markdown-exporter/b8caaba935eea7e7017b887c86a740cb7bf99708/logo.png" alt="confluence-markdown-exporter"></a>
</p>
<p align="center">
    <em>The confluence-markdown-exporter exports Confluence pages in Markdown format. This exporter helps in migrating content from Confluence to platforms that support Markdown e.g. Obsidian, Gollum, Azure DevOps (ADO), Foam, Dendron and more.</em>
</p>
<p align="center">
  <a href="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/ci.yml"><img src="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/ci.yml/badge.svg" alt="Test, Lint and Build"></a>
  <a href="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/release.yml"><img src="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/release.yml/badge.svg" alt="Build and publish to PyPI"></a>
  <a href="https://pypi.org/project/confluence-markdown-exporter" target="_blank">
    <img src="https://img.shields.io/pypi/v/confluence-markdown-exporter?color=%2334D058&label=PyPI%20package" alt="Package version">
   </a>
  <a href="https://spenhouet.github.io/confluence-markdown-exporter/" target="_blank">
    <img src="https://img.shields.io/badge/docs-online-blue" alt="Documentation">
   </a>
</p>

## What it does

Exports individual pages, pages with descendants, or entire Confluence spaces via the Atlassian API into clean Markdown. Skips unchanged pages by default, re-exporting only what has changed since the last run.

Supported targets include Obsidian, Gollum, Azure DevOps (ADO) wikis, Foam, Dendron, and anything else that consumes Markdown.

Full feature list, configuration reference, and target-system presets live in the **[documentation site](https://spenhouet.github.io/confluence-markdown-exporter/)**.

## Quickstart

### 1. Install

**macOS and Linux**

```bash
curl -LsSf uvx.sh/confluence-markdown-exporter/install.sh | sh
```

**Windows**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://uvx.sh/confluence-markdown-exporter/install.ps1 | iex"
```

Installing a specific version:

```bash
curl -LsSf uvx.sh/confluence-markdown-exporter/5.1.0/install.sh | sh
```

### 2. Authenticate

Set Confluence credentials interactively (URL, username, API token / PAT):

```sh
cme config edit auth.confluence
```

See [Authentication](https://spenhouet.github.io/confluence-markdown-exporter/configuration/authentication) for token scopes and Jira setup.

### 3. Export

```sh
# A single page
cme pages <page-url>

# A page and all its descendants
cme pages-with-descendants <page-url>

# An entire space
cme spaces <space-url>

# Every space of an organisation
cme orgs <base-url>
```

Output goes to the configured `export.output_path` (current directory by default).

## Documentation

The full documentation lives at **<https://spenhouet.github.io/confluence-markdown-exporter/>** and includes:

- [Installation](https://spenhouet.github.io/confluence-markdown-exporter/installation)
- [Usage guide](https://spenhouet.github.io/confluence-markdown-exporter/usage) — pages, descendants, spaces, orgs, output layout
- [Feature list](https://spenhouet.github.io/confluence-markdown-exporter/features) — supported Confluence content, macros, and add-ons
- [Configuration](https://spenhouet.github.io/confluence-markdown-exporter/configuration) — config commands, ENV vars, full option reference
- [Target-system presets](https://spenhouet.github.io/confluence-markdown-exporter/configuration/target-systems) — Obsidian, Azure DevOps, …
- [CI / non-interactive use](https://spenhouet.github.io/confluence-markdown-exporter/configuration/ci)
- [Compatibility](https://spenhouet.github.io/confluence-markdown-exporter/compatibility) and [Troubleshooting](https://spenhouet.github.io/confluence-markdown-exporter/troubleshooting)

## Contributing

If you would like to contribute, please read [our contribution guideline](CONTRIBUTING.md).

## License

This tool is an open source project released under the [MIT License](LICENSE).
