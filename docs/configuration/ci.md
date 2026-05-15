---
id: ci
title: Running in CI
sidebar_label: CI / non-interactive
sidebar_position: 5
---

# Running in CI / non-interactive environments

The exporter automatically detects CI environments and suppresses rich terminal formatting (colors, spinner animations, progress bar redraws) so that log output is clean and readable in CI logs.

Detection is based on two standard environment variables:

| Variable     | Effect                                                                    |
| ------------ | ------------------------------------------------------------------------- |
| `CI=true`    | Disables ANSI color codes and live terminal output                        |
| `NO_COLOR=1` | Same effect (follows the [no-color.org](https://no-color.org) convention) |

Most CI platforms (GitHub Actions, GitLab CI, CircleCI, Jenkins, etc.) set `CI=true` automatically.

## Controlling log verbosity

You can control output verbosity via the `CME_EXPORT__LOG_LEVEL` env var or the [`export.log_level`](./options.md#exportlog_level) config option:

```sh
# Enable verbose debug logging for a single run (not persisted):
CME_EXPORT__LOG_LEVEL=DEBUG cme pages <page-url>

# Reduce verbosity permanently:
cme config set export.log_level=WARNING

# Or for the current session only:
CME_EXPORT__LOG_LEVEL=WARNING cme pages <page-url>
```

This is useful for using different log levels for different environments or for scripting.

## Tips for CI pipelines

- Use a dedicated config file via [`CME_CONFIG_PATH`](./index.md#custom-config-file-location) so CI runs don't share state with developer machines.
- Provide credentials via secrets and set them with `cme config set` at the start of the run, or use ENV var overrides for non-auth options.
- Pin the version using the version-specific installer URL; see [Installation](../installation.md#pinning-a-specific-version).
