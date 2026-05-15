---
id: docker
title: Docker
sidebar_position: 5
---

# Docker

Prebuilt images are published to Docker Hub at [`spenhouet/confluence-markdown-exporter`](https://hub.docker.com/r/spenhouet/confluence-markdown-exporter).

The Docker image is intended for **non-interactive / CI use**: you supply a pre-defined config (either as a mounted JSON file or as environment variables), and the container runs a single export command and exits.

:::note
The interactive `cme config` menu is **not** supported in this mode. Edit the JSON config file directly or change the env vars instead.
:::

## Available tags

- `latest`: the most recent release
- `<version>` (e.g. `5.1.0`): pinned release version
- `<major>` / `<major>.<minor>` (e.g. `5`, `5.1`): rolling tags following the latest release within that range

## Quick start

```bash
docker pull spenhouet/confluence-markdown-exporter:latest
docker run --rm spenhouet/confluence-markdown-exporter --help
```

The image pins `export.output_path` to `/data/output` (via the `CME_EXPORT__OUTPUT_PATH` env var baked into the image), overriding whatever value the mounted config file has. Bind-mount your host export directory there and exported files appear in it.

## Providing configuration

The image reads its config from `/data/config/app_data.json` (set via `CME_CONFIG_PATH`). Generate this file once on a workstation by running `cme config` locally, then check it in to your CI repository or your secret store and mount it into the container, using the same pattern as a Kubernetes ConfigMap volume:

```bash
docker run --rm \
  -v "$PWD/app_data.json:/data/config/app_data.json:ro" \
  -v "$PWD/output:/data/output" \
  spenhouet/confluence-markdown-exporter \
  pages <page-url>
```

The mounted file must be readable by UID `1000` (the non-root `cme` user inside the image). For a config file managed in a CI runner this is usually already the case; if not, `chmod 644 app_data.json` is enough.

In Docker Compose, the [`configs:`](https://docs.docker.com/reference/compose-file/configs/) top-level key expresses the same mount declaratively:

```yaml
services:
  cme:
    image: spenhouet/confluence-markdown-exporter:latest
    command: ["pages", "<page-url>"]
    configs:
      - source: cme_config
        target: /data/config/app_data.json
    volumes:
      - ./output:/data/output

configs:
  cme_config:
    file: ./app_data.json
```

## Overriding scalar settings via environment variables

Scalar settings can be overridden at runtime with environment variables using the `CME_` prefix and `__` as the nested delimiter:

```bash
docker run --rm \
  -e CME_EXPORT__LOG_LEVEL=DEBUG \
  -e CME_CONNECTION_CONFIG__MAX_WORKERS=5 \
  -v "$PWD/app_data.json:/data/config/app_data.json:ro" \
  -v "$PWD/output:/data/output" \
  spenhouet/confluence-markdown-exporter \
  pages <page-url>
```

See the full [options reference](./configuration/options.md) for every supported `CME_*` env var.

## Auth credentials in environment variables

:::warning
The `auth.confluence` and `auth.jira` settings are dicts keyed by the instance base URL. That URL key cannot be expressed inside an environment variable name.
:::

If you must inject auth credentials via env vars (e.g. to keep secrets out of the JSON file), supply the whole sub-dict as a single JSON-encoded value:

```bash
docker run --rm \
  -v "$PWD/app_data.json:/data/config/app_data.json:ro" \
  -e CME_AUTH__CONFLUENCE="{\"https://company.atlassian.net\":{\"username\":\"$CONFLUENCE_USER\",\"api_token\":\"$CONFLUENCE_API_TOKEN\"}}" \
  -v "$PWD/output:/data/output" \
  spenhouet/confluence-markdown-exporter \
  pages <page-url>
```

For most CI setups it is simpler to template the JSON file from the CI secret store before running the container.

## See also

- [Authentication](./configuration/authentication.md): full credential setup and scoped-token notes
- [CI / non-interactive](./configuration/ci.md): `CI=true`, `NO_COLOR`, log-level control
- [Installation](./installation.md): pip / uv / curl / PowerShell installers
