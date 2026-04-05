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
from confluence_markdown_exporter.utils.config_interactive import main_config_menu_loop

logger = logging.getLogger(__name__)

app = typer.Typer(
    invoke_without_command=True,
    help="Manage configuration interactively or via subcommands.",
)


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context) -> None:
    """Open the interactive configuration menu if no subcommand is given."""
    if ctx.invoked_subcommand is None:
        main_config_menu_loop(None)


@app.command()
def reset(
    yes: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
    ] = False,
) -> None:
    """Reset all configuration to defaults."""
    if not yes:
        confirmed = typer.confirm("Reset all configuration to defaults?", default=False)
        if not confirmed:
            raise typer.Abort
    reset_to_defaults()
    typer.echo("Configuration reset to defaults.")


@app.command()
def path() -> None:
    """Output the path to the configuration file."""
    typer.echo(str(APP_CONFIG_PATH))


@app.command(name="list")
def list_config(
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: 'yaml' or 'json'."),
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


@app.command()
def get(
    key: Annotated[
        str,
        typer.Argument(help="Config key in dot notation, e.g. 'export.log_level'."),
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


@app.command(name="set")
def set_config(
    key_values: Annotated[
        list[str],
        typer.Argument(
            help=(
                "One or more key=value pairs, e.g. 'export.log_level=DEBUG'."
                " For auth keys containing URLs, use 'cme config edit' instead."
            )
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


@app.command()
def edit(
    key: Annotated[
        str,
        typer.Argument(
            help="Config key to open in the interactive editor, e.g. 'auth.confluence'."
        ),
    ],
) -> None:
    """Open the interactive editor for a specific config key."""
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
