---
id: index
title: Configuration
slug: /configuration/
sidebar_position: 1
---

# Configuration

All configuration and authentication is stored in a single JSON file managed by the application. You do not need to manually edit this file; use the `cme config` commands instead.

## Config commands

| Command                         | Description                                    |
| ------------------------------- | ---------------------------------------------- |
| `cme config`                    | Open the interactive configuration menu        |
| `cme config list`               | Print the full configuration as YAML           |
| `cme config get <key>`          | Print the value of a single config key         |
| `cme config set <key=value>...` | Set one or more config values                  |
| `cme config edit <key>`         | Open the interactive editor for a specific key |
| `cme config path`               | Print the path to the config file              |
| `cme config reset`              | Reset all configuration to defaults            |

### Interactive menu

```sh
cme config
```

Opens a full interactive menu where you can:

- See all config options and their current values
- Select any option to change it (including authentication)
- Navigate into nested sections (e.g. `auth.confluence`)
- Reset all config to defaults

### List current configuration

```sh
cme config list           # YAML (default)
cme config list -o json   # JSON
```

Prints the entire current configuration. Output format defaults to YAML; use `-o json` for JSON.

### Get a single value

```sh
cme config get export.log_level
cme config get connection_config.max_workers
```

Prints the current value of the specified key. Nested sections are printed as YAML.

### Set values

```sh
cme config set export.log_level=DEBUG
cme config set export.output_path=/tmp/export
cme config set export.skip_unchanged=false
```

Sets one or more `key=value` pairs directly. Values are parsed as JSON where possible (so `true`, `false`, and numbers work as expected), falling back to a plain string.

:::note
For auth keys that contain a URL (e.g. `auth.confluence.https://...`), use `cme config edit auth.confluence` instead, which handles URL-based keys correctly.
:::

### Edit a specific key interactively

```sh
cme config edit auth.confluence
cme config edit export.log_level
```

Opens the interactive editor directly at the specified config section, skipping the top-level menu.

### Show config file path

```sh
cme config path
```

Prints the absolute path to the configuration file. Useful when `CME_CONFIG_PATH` is set or when locating the file for backup/inspection.

### Reset to defaults

```sh
cme config reset
cme config reset --yes   # skip confirmation
```

Resets the entire configuration to factory defaults after confirmation.

## ENV var overrides

All options can be set via the config file (using `cme config set`) or overridden for the current session via environment variables.

ENV vars **take precedence** over stored config and are **not** persisted. ENV var names use the `CME_` prefix and `__` (double underscore) as the nested delimiter, matching the key in uppercase. Example: `export.log_level` → `CME_EXPORT__LOG_LEVEL`.

:::note
Auth credentials use URL-keyed nested dicts (e.g. `auth.confluence["https://company.atlassian.net"]`) and cannot be mapped to flat ENV var names. Use `cme config edit auth.confluence` or `cme config set` for auth configuration.
:::

## Custom config file location

By default, configuration is stored in a platform-specific application directory. You can override the config file location by setting the `CME_CONFIG_PATH` environment variable to the desired file path:

```sh
export CME_CONFIG_PATH=/path/to/your/custom_config.json
```

If set, the application will read and write config from this file instead.

## Next

- [Full option reference →](./options.md)
- [Authentication →](./authentication.md)
- [Target-system presets (Obsidian, ADO, …) →](./target-systems.md)
- [Running in CI / non-interactive environments →](./ci.md)
