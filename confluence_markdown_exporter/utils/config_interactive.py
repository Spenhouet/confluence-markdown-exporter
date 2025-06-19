import sys
from pathlib import Path
from typing import Any
from typing import get_args

import questionary
from pydantic import BaseModel
from pydantic import ValidationError
from questionary import Choice
from questionary import Style

from confluence_markdown_exporter.utils.app_data_store import ConfigModel
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import reset_settings
from confluence_markdown_exporter.utils.app_data_store import set_nested_setting
from confluence_markdown_exporter.utils.app_data_store import set_setting

custom_style = Style(
    [
        ("key", "fg:#00b8d4 bold"),  # cyan bold for key
        ("value", "fg:#888888 italic"),  # gray italic for value
        ("pointer", "fg:#00b8d4 bold"),
        ("highlighted", "fg:#00b8d4 bold"),
    ]
)


def _get_field_type(model: type[BaseModel], key: str):
    # Handles both Pydantic v1 and v2
    if hasattr(model, "model_fields"):  # v2
        return model.model_fields[key].annotation
    return model.__annotations__[key]


def _get_submodel(model: type[BaseModel], key: str):
    if hasattr(model, "model_fields"):
        sub = model.model_fields[key].annotation
    else:
        sub = model.__annotations__[key]
    # Only return submodel if it's a subclass of BaseModel
    if isinstance(sub, type):
        try:
            if issubclass(sub, BaseModel):
                return sub
        except TypeError:
            # sub is not a class or not suitable for issubclass
            return None
    return None


def _get_field_metadata(model: type[BaseModel], key: str):
    # Returns dict with title, description, examples for a field
    if hasattr(model, "model_fields"):  # Pydantic v2
        field = model.model_fields[key]
        return {
            "title": getattr(field, "title", None),
            "description": getattr(field, "description", None),
            "examples": getattr(field, "examples", None),
        }
    # Pydantic v1 fallback
    field = model.__fields__[key]
    return {
        "title": getattr(field.field_info, "title", None),
        "description": getattr(field.field_info, "description", None),
        "examples": getattr(field.field_info, "examples", None),
    }


def _format_prompt_message(key_name: str, current_value: object, model: type[BaseModel]) -> str:
    meta = _get_field_metadata(model, key_name)
    lines = []
    # Title
    if meta["title"]:
        lines.append(f"{meta['title']}\n")
    else:
        lines.append(f"{key_name}\n")

    # Description
    if meta["description"]:
        lines.append(meta["description"])

    # Examples
    if meta["examples"]:
        ex = meta["examples"]
        if isinstance(ex, (list, tuple)) and ex:
            lines.append("\nExamples:")
            for example in ex:
                lines.append(f"  • {example}")
    # Instruction
    lines.append(f"\nChange {meta['title']} to:")
    return "\n".join(lines)


def _prompt_for_new_value(
    key_name: str, current_value: object, model: type[BaseModel], parent_key: str | None = None
):
    field_type = _get_field_type(model, key_name)
    prompt_message = _format_prompt_message(key_name, current_value, model)

    # Handle Literal fields (for select menus)
    if sys.version_info >= (3, 8):
        from typing import Literal

        is_literal = getattr(field_type, "__origin__", None) is Literal or str(
            field_type
        ).startswith("typing.Literal")
    else:
        is_literal = False
    if is_literal:
        options = list(get_args(field_type))
        return questionary.select(
            prompt_message,
            choices=[str(opt) for opt in options],
            default=str(current_value),
            style=custom_style,
        ).ask()

    def pydantic_validate(val):
        try:
            if parent_key:
                # For nested fields
                data = model().model_dump()
                data[key_name] = val
                model(**data)  # Will raise if invalid
            else:
                data = model().model_dump()
                data[key_name] = val
                model(**data)
            return True
        except ValidationError as e:
            return str(e.errors()[0]["msg"])

    if field_type is bool:
        return questionary.confirm(
            prompt_message, default=bool(current_value), style=custom_style
        ).ask()
    if field_type is Path:
        return questionary.path(
            prompt_message,
            default=str(current_value),
            validate=pydantic_validate,
            style=custom_style,
        ).ask()
    if field_type is int:
        answer = questionary.text(
            prompt_message,
            default=str(current_value),
            validate=lambda v: v.isdigit() or "Must be an integer",
            style=custom_style,
        ).ask()
        if answer is not None:
            try:
                return int(answer)
            except Exception:
                questionary.print("Invalid integer value.")
        return None
    if field_type is list or field_type is list[int]:
        answer = questionary.text(
            prompt_message + " (comma-separated)",
            default=",".join(map(str, current_value)),
            style=custom_style,
        ).ask()
        if answer is not None:
            try:
                return [int(x.strip()) for x in answer.split(",") if x.strip()]
            except Exception:
                questionary.print("Invalid list of integers.")
        return None
    # str or fallback
    return questionary.text(
        prompt_message, default=str(current_value), validate=pydantic_validate, style=custom_style
    ).ask()


def _handle_reset():
    confirm = questionary.confirm(
        "Are you sure you want to reset all config to defaults?", style=custom_style
    ).ask()
    if confirm:
        reset_settings()
        questionary.print("Config reset to defaults.")
        questionary.text("Press Enter to continue...", style=custom_style).ask()


def _edit_dict_config(config_dict: dict, parent_key: str, model: type[BaseModel]):
    while True:
        choices = []
        for k, v in config_dict.items():
            meta = _get_field_metadata(model, k)
            display_title = meta["title"] if meta and meta["title"] else k
            choices.append(
                Choice(title=[("class:key", str(display_title)), ("class:value", f"  {v}")], value=k)
            )
        choices.append(Choice(title="[Back]", value="__back__"))
        key = questionary.select(
            f"Edit options for '{parent_key}':", choices=choices, style=custom_style
        ).ask()
        if key == "__back__" or key is None:
            break
        current_value = config_dict[key]
        submodel = _get_submodel(model, key)
        # Only recurse if current_value is a dict and submodel is a BaseModel
        if isinstance(current_value, dict) and submodel is not None:
            _edit_dict_config(current_value, f"{parent_key}.{key}", submodel)
        else:
            while True:
                value_cast = _prompt_for_new_value(key, current_value, model, parent_key=key)
                if value_cast is not None:
                    try:
                        set_nested_setting(parent_key, key, value_cast)
                        config_dict[key] = value_cast
                        questionary.print(f"{parent_key}.{key} updated to {value_cast}.")
                        break
                    except Exception as e:
                        questionary.print(f"Error: {e}")
                        retry = questionary.confirm("Try again?", style=custom_style).ask()
                        if not retry:
                            break
                else:
                    break


def interactive_config_menu() -> None:
    """Directly show change config view with reset as last option."""
    while True:
        settings = get_settings().dict()
        choices = []
        for k, v in settings.items():
            # Get title from Pydantic metadata, fallback to key
            meta = _get_field_metadata(ConfigModel, k)
            display_title = meta["title"] if meta and meta["title"] else k
            if isinstance(v, dict):
                choices.append(
                    Choice(
                        title=[("class:key", str(display_title)), ("class:value", "  [submenu]")],
                        value=(k, True),
                    )
                )
            else:
                choices.append(
                    Choice(
                        title=[("class:key", str(display_title)), ("class:value", f"  {v}")], value=(k, False)
                    )
                )
        choices.append(Choice(title="[Reset config to defaults]", value=("__reset__", False)))
        choices.append(Choice(title="[Exit]", value=("__exit__", False)))
        key, is_dict = questionary.select(
            "Select a config to change (or reset):", choices=choices, style=custom_style
        ).ask() or (None, False)
        if key == "__reset__":
            _handle_reset()
            continue
        if key == "__exit__" or key is None:
            break
        current_value = settings[key]
        if is_dict:
            submodel = _get_submodel(ConfigModel, key)
            if submodel is not None:
                _edit_dict_config(current_value, key, submodel)
        else:
            while True:
                value_cast = _prompt_for_new_value(key, current_value, ConfigModel)
                if value_cast is None or value_cast == current_value:
                    # User cancelled or made no change: do not update config
                    break
                try:
                    set_setting(key, value_cast)
                    questionary.print(f"{display_title} updated to {value_cast}.")
                    break
                except Exception as e:
                    questionary.print(f"Error: {e}")
                    retry = questionary.confirm("Try again?", style=custom_style).ask()
                    if not retry:
                        break
