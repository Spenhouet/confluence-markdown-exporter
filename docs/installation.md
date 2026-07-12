---
title: Installation
---

# Installation

Pick the install method that fits your environment. All methods produce the same `cme` / `confluence-markdown-exporter` CLI.

=== "Linux / macOS"

    ```bash
    curl -LsSf uvx.sh/confluence-markdown-exporter/install.sh | sh
    ```

    Uses [uv](https://docs.astral.sh/uv/) under the hood to create an isolated, self-updating environment. No need to manage a virtualenv yourself.

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://uvx.sh/confluence-markdown-exporter/install.ps1 | iex"
    ```

    Uses [uv](https://docs.astral.sh/uv/) under the hood. Run from PowerShell.

=== "pip"

    ```bash
    pip install confluence-markdown-exporter
    ```

    Installs from PyPI into the active Python environment. Requires Python >= 3.10. If you don't already have a project virtualenv, prefer the **uv** or **Linux/macOS/Windows installer** tabs; they isolate the tool for you.

=== "uv"

    ```bash
    # Install as an isolated, self-managed tool
    uv tool install confluence-markdown-exporter

    # ...or run it once without installing
    uvx confluence-markdown-exporter --help
    ```

    [`uv tool install`](https://docs.astral.sh/uv/concepts/tools/) puts the CLI on your PATH inside its own isolated environment. [`uvx`](https://docs.astral.sh/uv/guides/tools/) runs it ephemerally; handy for one-off exports or CI.

=== "Docker"

    ```bash
    docker pull spenhouet/confluence-markdown-exporter:latest
    docker run --rm spenhouet/confluence-markdown-exporter --help
    ```

    The Docker image is intended for **non-interactive / CI use**: you supply a pre-defined config (mounted JSON file or env vars) and the container runs a single export command and exits. The interactive `cme config` menu is not available inside the container. Full setup (mounted config, Compose example, env-var auth) is on the [Docker page](docker.md).

## Pinning a specific version

=== "Linux / macOS"

    ```bash
    curl -LsSf uvx.sh/confluence-markdown-exporter/5.3.0/install.sh | sh
    ```

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://uvx.sh/confluence-markdown-exporter/5.3.0/install.ps1 | iex"
    ```

=== "pip"

    ```bash
    pip install confluence-markdown-exporter==5.3.0
    ```

=== "uv"

    ```bash
    uv tool install confluence-markdown-exporter==5.3.0
    ```

=== "Docker"

    ```bash
    docker pull spenhouet/confluence-markdown-exporter:5.3.0
    ```

    Pinned tags are kept available indefinitely; rolling tags (`latest`, `<major>`, `<major>.<minor>`) advance with each release. See [Docker, available tags](docker.md#available-tags).

## Verify the install

=== "Local"

    ```bash
    cme --help
    ```

=== "Docker"

    ```bash
    docker run --rm spenhouet/confluence-markdown-exporter --help
    ```

You should see the top-level commands: `pages`, `pages-with-descendants`, `spaces`, `orgs`, and `config`.

## Next steps

- [Authenticate and configure your first export](configuration/index.md#interactive-menu) (local install)
- [Export pages or whole spaces](usage.md) (local install)
- [Docker page](docker.md): non-interactive setup (mounted config + env vars)
