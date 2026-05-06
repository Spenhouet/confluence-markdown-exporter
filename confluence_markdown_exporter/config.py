"""Config sub-app for the cme CLI."""

import json
import logging
from typing import Annotated

import jmespath
import typer
import yaml

from confluence_markdown_exporter.utils.app_data_store import APP_CONFIG_PATH
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import reset_to_defaults
from confluence_markdown_exporter.utils.app_data_store import set_setting

logger = logging.getLogger(__name__)

# Each table row must be its own \n\n-separated block so typer's epilog
# renderer keeps single \n between rows, forming valid markdown table syntax.
_CONFIG_KEYS_EPILOG = (
    "---\n\n"
    "**Available config keys** (run `cme config list` to see all current values):\n\n"
    "| Key | Description |\n\n"
    "| --- | ----------- |\n\n"
    "| `export.output_path` | Directory where exported files are saved |\n\n"
    "| `export.log_level` | Verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |\n\n"
    "| `export.skip_unchanged` | Skip pages unchanged since last export |\n\n"
    "| `export.cleanup_stale` | Delete local files for removed pages |\n\n"
    "| `export.page_path` | File path template for exported pages |\n\n"
    "| `export.attachment_path` | File path template for exported attachments |\n\n"
    "| `export.page_href` | Link style for pages: `relative` or `absolute` |\n\n"
    "| `export.attachment_href` | Link style for attachments: `relative` or `absolute` |\n\n"
    "| `export.include_document_title` | Prepend H1 title to each page |\n\n"
    "| `export.include_toc` | Export Table of Contents macro (`true`/`false`) |\n\n"
    "| `export.page_breadcrumbs` | Include breadcrumb links at top of page |\n\n"
    "| `export.confluence_url_in_frontmatter` | Include Confluence page URL in YAML "
    "front matter: `none`, `webui`, `tinyui`, `both` |\n\n"
    "| `export.page_metadata_in_frontmatter` | Add Confluence page metadata "
    "fields (page_id, space_key, last_modified, last_modified_by, version) "
    "to YAML front matter (`true`/`false`) |\n\n"
    "| `export.enable_jira_enrichment` | Fetch Jira data for enriched links |\n\n"
    "| `export.attachments_export` | Which attachments to download:"
    " `referenced` (default), `all`, `disabled` |\n\n"
    "| `export.image_captions` | Use image captions as markdown alt text (`true`/`false`) |\n\n"
    "| `export.inline_comments` | Export open inline comments as sidecar `.comments.md` files |\n\n"
    "| `export.convert_status_badges` | Convert Confluence status badges to `<mark>` elements |\n\n"
    "| `export.convert_text_highlights` | Convert background-color spans to `<mark>` elements |\n\n"
    "| `export.convert_font_colors` | Convert font-color spans to `<font>` elements |\n\n"
    "| `export.filename_length` | Maximum filename length (default: 255) |\n\n"
    "| `connection_config.max_workers` | Parallel export workers (default: 20) |\n\n"
    "| `connection_config.use_v2_api` | Use Confluence REST API v2 (`true`/`false`) |\n\n"
    "| `connection_config.verify_ssl` | Verify SSL certificates (`true`/`false`) |\n\n"
    "| `connection_config.timeout` | API request timeout in seconds |\n\n"
    "| `auth.confluence` | Credentials keyed by instance URL — use `cme config edit` |\n\n"
    "| `auth.jira` | Jira credentials keyed by instance URL — use `cme config edit` |\n\n"
    "---\n\n"
    "Env var override: prefix with `CME_` and `__` as delimiter. "
    "Examples: `CME_EXPORT__OUTPUT_PATH=/tmp/export`, `CME_CONNECTION_CONFIG__MAX_WORKERS=5`.\n\n"
)

app = typer.Typer(
    rich_markup_mode="markdown",
    invoke_without_command=True,
    help=(
        "Manage configuration interactively or via subcommands.\n\n"
        "Running `cme config` without a subcommand opens the **interactive menu**, "
        "which lets you browse and change all settings including authentication credentials.\n\n"
        "For scripting or automation, use the subcommands below."
    ),
    epilog=(
        "**Subcommands at a glance:**\n\n"
        "- `cme config` — interactive menu\n\n"
        "- `cme config list` — print full config as YAML\n\n"
        "- `cme config list -o json` — print full config as JSON\n\n"
        "- `cme config get export.log_level` — print a single value\n\n"
        "- `cme config set export.log_level=DEBUG` — set a value\n\n"
        "- `cme config edit auth.confluence` — edit credentials interactively\n\n"
        "- `cme config path` — show config file path\n\n"
        "- `cme config reset` — reset all settings to defaults\n\n"
        "- `cme config reset export.log_level` — reset a single key to its default\n\n"
    ),
)


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context) -> None:
    """Open the interactive configuration menu if no subcommand is given."""
    if ctx.invoked_subcommand is None:
        from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop

        main_config_menu_loop(None)


@app.command(
    help=(
        "Reset configuration to defaults.\n\n"
        "Without a `KEY` argument, resets the **entire configuration** to factory defaults. "
        "Pass a dot-notation key to reset only that key or section.\n\n"
        "Use `--yes` / `-y` to skip the confirmation prompt (useful in scripts)."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme config reset` — reset everything (prompts for confirmation)\n\n"
        "- `cme config reset --yes` — skip confirmation prompt\n\n"
        "- `cme config reset export.log_level` — reset a single key to its default\n\n"
        "- `cme config reset connection_config` — reset a whole section to defaults\n\n"
    ),
)
def reset(
    key: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Dot-notation config key or section to reset to its default. "
                "If omitted, the entire configuration is reset. "
                "Examples: `export.log_level`, `connection_config`, `export`."
            ),
            metavar="KEY",
        ),
    ] = None,
    yes: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
    ] = False,
) -> None:
    if not yes:
        target = f"'{key}'" if key else "all configuration"
        confirmed = typer.confirm(f"Reset {target} to defaults?", default=False)
        if not confirmed:
            raise typer.Abort
    reset_to_defaults(key)
    target = f"'{key}'" if key else "Configuration"
    typer.echo(f"{target} reset to defaults.")


@app.command(
    help=(
        "Print the path to the configuration file.\n\n"
        "Override the config file location by setting the `CME_CONFIG_PATH` environment variable."
    ),
    epilog=(
        "**Example:**\n\n"
        "- `cme config path`\n\n"
        "- `CME_CONFIG_PATH=/custom/path.json cme config path` — custom config file\n\n"
    ),
)
def path() -> None:
    """Output the path to the configuration file."""
    typer.echo(str(APP_CONFIG_PATH))


@app.command(
    name="list",
    help=(
        "Print the current configuration as YAML (default) or JSON.\n\n"
        "Shows all settings and their current effective values. "
        "Use this to discover available config keys for `cme config get` and "
        "`cme config set`.\n\n"
        "> **Note:** Secret values (API tokens, passwords) are printed in plaintext."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme config list` — YAML output (default)\n\n"
        "- `cme config list -o json` — JSON output\n\n"
        "- `cme config list -o yaml` — explicit YAML\n\n"
    ),
)
def list_config(
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format. Accepted values: `yaml` (default) or `json`.",
            metavar="FORMAT",
        ),
    ] = "yaml",
) -> None:
    """Output the current configuration as YAML or JSON."""
    current_settings = get_settings()
    data = json.loads(current_settings.model_dump_json())
    fmt = output.lower()
    if fmt == "json":
        typer.echo(json.dumps(data, indent=2))
    elif fmt in ("yaml", "yml"):
        typer.echo(yaml.dump(data, default_flow_style=False, allow_unicode=True), nl=False)
    else:
        typer.echo(f"Unknown format '{output}': expected 'yaml' or 'json'.", err=True)
        raise typer.Exit(code=1)


@app.command(
    help=(
        "Print the current value of a single config key.\n\n"
        "Keys use dot notation to address nested settings "
        "(e.g. `export.log_level`, `connection_config.max_workers`). "
        "Nested sections are printed as YAML. "
        "Run `cme config list` to see all available keys."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme config get export.log_level`\n\n"
        "- `cme config get export.output_path`\n\n"
        "- `cme config get connection_config.max_workers`\n\n"
        "- `cme config get connection_config` — prints the whole section as YAML\n\n"
        "- `cme config get export` — prints all export settings\n\n"
        + _CONFIG_KEYS_EPILOG
    ),
)
def get(
    key: Annotated[
        str,
        typer.Argument(
            help=(
                "Config key in dot notation. "
                "Examples: `export.log_level`, `connection_config.max_workers`, `export`."
            ),
            metavar="KEY",
        ),
    ],
) -> None:
    """Output the current value of a config key."""
    current_settings = get_settings()
    data = json.loads(current_settings.model_dump_json())
    value = jmespath.search(key, data)
    if value is None:
        typer.echo(f"Key '{key}' not found.", err=True)
        raise typer.Exit(code=1)
    if isinstance(value, dict | list):
        typer.echo(yaml.dump(value, default_flow_style=False, allow_unicode=True), nl=False)
    else:
        typer.echo(str(value))


@app.command(
    name="set",
    help=(
        "Set one or more configuration values.\n\n"
        "Each argument must be a `key=value` pair using dot notation for the key. "
        "Values are parsed as JSON where possible "
        "(so `true`, `false`, numbers, and JSON arrays work), "
        "falling back to a plain string.\n\n"
        "> **Note:** For auth keys that contain a URL "
        "(e.g. `auth.confluence.https://...`), use `cme config edit auth.confluence` "
        "instead — the interactive editor handles URL-based keys correctly."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme config set export.log_level=DEBUG`\n\n"
        "- `cme config set export.output_path=/tmp/export`\n\n"
        "- `cme config set export.skip_unchanged=false`\n\n"
        "- `cme config set connection_config.max_workers=5`\n\n"
        "- `cme config set connection_config.verify_ssl=false`\n\n"
        "- `cme config set export.log_level=INFO export.output_path=./out`"
        " — multiple keys at once\n\n"
        + _CONFIG_KEYS_EPILOG
    ),
)
def set_config(
    key_values: Annotated[
        list[str],
        typer.Argument(
            help=(
                "One or more `key=value` pairs. "
                "Keys use dot notation (e.g. `export.log_level=DEBUG`). "
                "Values are parsed as JSON first, then as plain strings. "
                "For auth keys containing URLs, use `cme config edit` instead."
            ),
            metavar="KEY=VALUE",
        ),
    ],
) -> None:
    """Set one or more configuration values."""
    for kv in key_values:
        if "=" not in kv:
            typer.echo(f"Invalid format '{kv}': expected key=value.", err=True)
            raise typer.Exit(code=1)
        key, _, raw_value = kv.partition("=")
        value = _parse_value(raw_value)
        try:
            set_setting(key.strip(), value)
        except (ValueError, KeyError) as e:
            typer.echo(f"Failed to set '{key.strip()}': {e}", err=True)
            raise typer.Exit(code=1) from e
    typer.echo("Configuration updated.")


@app.command(
    help=(
        "Open the interactive editor for a specific config key.\n\n"
        "Launches the interactive configuration menu pre-navigated to the given key. "
        "Especially useful for editing authentication credentials, "
        "where the instance URL is part of the key and cannot be set via `cme config set`."
    ),
    epilog=(
        "**Examples:**\n\n"
        "- `cme config edit auth.confluence` — add or update Confluence credentials\n\n"
        "- `cme config edit auth.jira` — edit Jira credentials\n\n"
        "- `cme config edit export.log_level` — edit a setting interactively\n\n"
        "- `cme config edit export.output_path` — set output path interactively\n\n"
    ),
)
def edit(
    key: Annotated[
        str,
        typer.Argument(
            help=(
                "Config key to open in the interactive editor, using dot notation. "
                "Examples: `auth.confluence`, `auth.jira`, `export.log_level`."
            ),
            metavar="KEY",
        ),
    ],
) -> None:
    """Open the interactive editor for a specific config key."""
    from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop

    main_config_menu_loop(key)


def _parse_value(value_str: str) -> object:
    """Parse a CLI value string, trying JSON first then falling back to raw string.

    Handles JSON scalars (true/false, numbers, null), arrays, and objects.
    Also accepts Python-style True/False for convenience.
    """
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        pass
    lower = value_str.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return value_str
