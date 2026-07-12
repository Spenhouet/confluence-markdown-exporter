---
title: Confluence Markdown Exporter
description: >-
  Export Confluence pages to Markdown for Obsidian, Gollum, Azure DevOps, Foam,
  Dendron and more.
hide:
  - navigation
  - toc
---

<div class="bj-hero" markdown>

![Confluence Markdown Exporter](img/logo.png)

<p class="bj-tagline">Export Confluence pages to Markdown for Obsidian, Gollum, Azure DevOps, Foam, Dendron and more.</p>

[Get started](installation.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/Spenhouet/confluence-markdown-exporter){ .md-button }

</div>

## What it does

<div class="grid cards" markdown>

-   :material-rocket-launch: __One-command install__

    A single curl/PowerShell line installs an isolated, self-updating CLI via `uv`. No virtualenv juggling.

    [:octicons-arrow-right-24: Installation](installation.md)

-   :material-file-tree: __Pages, spaces, orgs__

    Export a single page, a page subtree, an entire space, or every space in your Atlassian organisation.

    [:octicons-arrow-right-24: Usage](usage.md)

-   :material-lightning-bolt: __Incremental by default__

    Skips unchanged pages using a lockfile. Re-runs export only what actually moved since last time.

    [:octicons-arrow-right-24: Features](features.md)

-   :material-target: __Target presets__

    Pre-baked configurations for Obsidian (wiki links, Dataview, Meta Bind) and Azure DevOps wikis (sanitized filenames, attachments folder).

    [:octicons-arrow-right-24: Target systems](configuration/target-systems.md)

-   :material-puzzle: __Macros and add-ons__

    Status badges, panels, page properties, draw.io, PlantUML, Mermaid, include/excerpt: all converted to portable Markdown.

    [:octicons-arrow-right-24: Features](features.md)

-   :material-shield-key: __Cloud and Server__

    Works against Confluence Cloud, the Atlassian API gateway, and on-premise Server / Data Center. API tokens, PATs and scoped tokens are all supported.

    [:octicons-arrow-right-24: Authentication](configuration/authentication.md)

</div>

## Get going in 60 seconds

Install, authenticate, export. That is the whole flow.

### 1. Install

=== "Linux / macOS"

    ```bash
    # Installs an isolated, self-updating CLI via uv.
    curl -LsSf uvx.sh/confluence-markdown-exporter/install.sh | sh
    ```

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://uvx.sh/confluence-markdown-exporter/install.ps1 | iex"
    ```

=== "uv"

    ```bash
    # Install as an isolated tool...
    uv tool install confluence-markdown-exporter

    # ...or run it once without installing:
    uvx confluence-markdown-exporter --help
    ```

=== "pip"

    ```bash
    pip install confluence-markdown-exporter
    ```

=== "Docker"

    ```bash
    # Prebuilt image, for non-interactive / CI use.
    docker pull spenhouet/confluence-markdown-exporter:latest
    docker run --rm spenhouet/confluence-markdown-exporter --help
    ```

### 2. Authenticate

```bash
cme config edit auth.confluence
```

Inside a container there is no interactive menu: generate the config on a workstation, then mount it (or pass `CME_AUTH__*` env vars). See the [Docker page](docker.md).

### 3. Export

```bash
# A page, a subtree, an entire space, or every space of an org:
cme pages   https://example.atlassian.net/wiki/spaces/SPACE/pages/123/Title
cme spaces  https://example.atlassian.net/wiki/spaces/SPACE
cme orgs    https://example.atlassian.net
```

Detailed setup and per-target presets live in the [installation docs](installation.md).
