---
id: intro
title: Introduction
sidebar_position: 1
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Logo from '@site/static/img/logo.png';

<div style={{textAlign: 'center', padding: '1rem 0 2rem'}}>
  <img src={Logo} alt="confluence-markdown-exporter" style={{maxWidth: '420px', width: '100%'}} />
</div>

> Export Confluence pages to Markdown for Obsidian, Gollum, Azure DevOps, Foam, Dendron and any other Markdown-based platform.

Exports individual pages, pages with descendants, or entire Confluence spaces via the Atlassian API into clean Markdown. Skips unchanged pages by default, re-exporting only what has changed since the last run.

## What's in these docs

- **[Installation](./installation.md)**: install and update the CLI in one command
- **[Usage](./usage.md)**: export pages, descendants, spaces, or organisations
- **[Features](./features.md)**: supported Confluence content, macros, and add-ons
- **[Configuration](./configuration/index.md)**: every option with defaults and ENV vars
- **[Target systems](./configuration/target-systems.md)**: Obsidian, Azure DevOps, …
- **[Troubleshooting](./troubleshooting.md)**: known issues and how to report

## Get started in 60 seconds

### 1. Install

<Tabs groupId="install-method" queryString>

<TabItem value="linux" label="Linux">

```bash
curl -LsSf uvx.sh/confluence-markdown-exporter/install.sh | sh
```

</TabItem>

<TabItem value="macos" label="macOS">

```bash
curl -LsSf uvx.sh/confluence-markdown-exporter/install.sh | sh
```

</TabItem>

<TabItem value="windows" label="Windows">

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://uvx.sh/confluence-markdown-exporter/install.ps1 | iex"
```

</TabItem>

<TabItem value="pip" label="pip">

```bash
pip install confluence-markdown-exporter
```

</TabItem>

<TabItem value="uv" label="uv">

```bash
uv tool install confluence-markdown-exporter
# or, one-shot run without installing:
uvx confluence-markdown-exporter --help
```

</TabItem>

<TabItem value="docker" label="Docker">

```bash
docker pull spenhouet/confluence-markdown-exporter:latest
docker run --rm spenhouet/confluence-markdown-exporter --help
```

The Docker image is intended for non-interactive / CI use; see the [Docker page](./docker.md) for config-file mounts and environment variables.

</TabItem>

</Tabs>

### 2. Authenticate (interactive)

```bash
cme config edit auth.confluence
```

### 3. Export a page

```bash
cme pages https://company.atlassian.net/wiki/spaces/SPACE/pages/123/Page+Title
```

That's it. Your Markdown lands in the configured `export.output_path` (current directory by default).
