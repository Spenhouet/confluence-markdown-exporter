from pathlib import Path
from typing import Literal
from typing import get_args
from typing import get_origin

import jmespath
import questionary
from pydantic import BaseModel
from pydantic import SecretStr
from pydantic import ValidationError
from questionary import Choice
from questionary import Style

from confluence_markdown_exporter.utils.app_data_store import ConfigModel
from confluence_markdown_exporter.utils.app_data_store import get_app_config_path
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.app_data_store import reset_to_defaults
from confluence_markdown_exporter.utils.app_data_store import save_app_data
from confluence_markdown_exporter.utils.app_data_store import set_setting
from confluence_markdown_exporter.utils.app_data_store import set_setting_with_keys

custom_style = Style(
    [
        ("key", "fg:#00b8d4 bold"),  # cyan bold for key
        ("value", "fg:#888888 italic"),  # gray italic for value
        ("pointer", "fg:#00b8d4 bold"),
        ("highlighted", "fg:#00b8d4 bold"),
    ]
)


def _get_field_type(model: type[BaseModel], key: str) -> type | None:
    # Handles both Pydantic v1 and v2
    if hasattr(model, "model_fields"):  # v2
        return model.model_fields[key].annotation
    return model.__annotations__[key]


def _get_submodel(model: type[BaseModel], key: str) -> type[BaseModel] | None:
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


def _get_field_metadata(model: type[BaseModel], key: str) -> dict:
    # Support jmespath-style dot-separated paths for nested fields
    if "." in key:
        keys = key.split(".")
        key = keys[-1]

    # Returns dict with title, description, examples for a field
    if hasattr(model, "model_fields"):  # Pydantic v2
        field = model.model_fields[key]
        return {
            "title": getattr(field, "title", None),
            "description": getattr(field, "description", None),
            "examples": getattr(field, "examples", None),
        }
    # Pydantic v1 fallback
    field = model.model_fields[key]
    return {
        "title": getattr(field, "title", None),
        "description": getattr(field, "description", None),
        "examples": getattr(field, "example", None),
    }


def _format_prompt_message(key_name: str, model: type[BaseModel]) -> str:
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
        if isinstance(ex, list | tuple) and ex:
            lines.append("\nExamples:")
            lines.extend(f"  • {example}" for example in ex)
    # Instruction
    lines.append(f"\nChange {meta['title']} to:")
    return "\n".join(lines)


def _validate_int(val: str) -> bool | str:
    return val.isdigit() or "Must be an integer"


def _validate_pydantic(val: object, model: type[BaseModel], key_name: str) -> bool | str:
    try:
        data = model().model_dump()
        data[key_name] = val
        model(**data)
    except ValidationError as e:
        return str(e.errors()[0]["msg"])
    else:
        return True


def _prompt_literal(prompt_message: str, field_type: type, current_value: object) -> object:
    options = list(get_args(field_type))
    return questionary.select(
        prompt_message,
        choices=[str(opt) for opt in options],
        default=str(current_value),
        style=custom_style,
    ).ask()


def _prompt_bool(prompt_message: str, current_value: object) -> object:
    return questionary.confirm(
        prompt_message, default=bool(current_value), style=custom_style
    ).ask()


def _prompt_path(
    prompt_message: str,
    current_value: object,
    model: type[BaseModel],
    key_name: str,
) -> object:
    return questionary.path(
        prompt_message,
        default=str(current_value),
        validate=lambda val: _validate_pydantic(val, model, key_name),
        style=custom_style,
    ).ask()


def _prompt_int(prompt_message: str, current_value: object) -> object:
    answer = questionary.text(
        prompt_message,
        default=str(current_value),
        validate=_validate_int,
        style=custom_style,
    ).ask()
    if answer is not None:
        try:
            return int(answer)
        except ValueError:
            questionary.print("Invalid integer value.")
    return None


def _prompt_list(prompt_message: str, current_value: object) -> object:
    default_val = ""
    val_type = str
    if isinstance(current_value, list):
        default_val = ",".join(map(str, current_value))
        if len(current_value) > 0:
            val_type = type(current_value[0])
    answer = questionary.text(
        prompt_message + " (comma-separated)",
        default=default_val,
        style=custom_style,
    ).ask()
    if answer is not None:
        answer = answer.strip().lstrip("[").rstrip("]").strip(",").replace(" ", "")
        try:
            return [val_type(x.strip()) for x in answer.split(",") if x.strip()]
        except ValueError:
            questionary.print("Input should be a list (e.g. 1,2,3 or [1,2,3]).")
    return None


def _prompt_str(
    prompt_message: str,
    current_value: object,
    model: type[BaseModel],
    key_name: str,
) -> object:
    return questionary.text(
        prompt_message,
        default=str(current_value),
        validate=lambda val: _validate_pydantic(val, model, key_name),
        style=custom_style,
    ).ask()


def get_model_by_path(model: type[BaseModel], path: str) -> type[BaseModel]:
    """Traverse a Pydantic model class using a dot-separated path and return the submodel class."""
    keys = path.split(".")
    for key in keys:
        # Try direct submodel first
        sub = _get_submodel(model, key)
        if sub is not None:
            model = sub
            continue
        # Try dict[str, SomeModel] — the key may be a field name or an instance name
        if hasattr(model, "model_fields") and key in model.model_fields:
            dict_sub = _get_dict_value_model(model, key)
            if dict_sub is not None:
                model = dict_sub
                continue
        # key is an instance name inside a dict[str, SomeModel] — model stays the same
    return model


def _get_dict_value_model(model: type[BaseModel], key: str) -> type[BaseModel] | None:
    """If the field annotation is dict[str, SomeModel], return SomeModel; else None."""
    if hasattr(model, "model_fields"):
        annotation = model.model_fields[key].annotation
    else:
        annotation = model.__annotations__.get(key)
    if annotation is None:
        return None
    origin = get_origin(annotation)
    if origin is dict:
        args = get_args(annotation)
        if len(args) == 2 and isinstance(args[1], type):  # noqa: PLR2004
            try:
                if issubclass(args[1], BaseModel):
                    return args[1]
            except TypeError:
                pass
    return None


def _edit_instance_fields(  # noqa: C901
    instance_key: str,
    instance_data: dict,
    item_model: type[BaseModel],
    parent_path_parts: list[str],
) -> None:
    """Edit the fields of a single named instance using set_setting_with_keys.

    This avoids the dot-split path system so URL keys (which contain dots)
    work correctly.
    """
    selected_field: str | None = None
    while True:
        choices = []
        for k, v in instance_data.items():
            if v is None:
                continue
            try:
                meta = _get_field_metadata(item_model, k)
                display_title = meta["title"] if meta and meta["title"] else k
            except (KeyError, AttributeError):
                display_title = k
            display_val = "Not set" if isinstance(v, str | SecretStr) and str(v) == "" else v
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", f"  {display_val}"),
                    ],
                    value=k,
                )
            )
        choices.append(Choice(title="[Back]", value="__back__"))
        field_key = questionary.select(
            f"Edit credentials for '{instance_key}':",
            choices=choices,
            style=custom_style,
            default=selected_field,
        ).ask()
        if field_key == "__back__" or field_key is None:
            return
        selected_field = field_key
        current_val = instance_data.get(field_key)
        while True:
            new_val = _prompt_for_new_value(field_key, current_val, item_model)
            if new_val is not None:
                try:
                    set_setting_with_keys([*parent_path_parts, instance_key, field_key], new_val)
                    instance_data[field_key] = new_val
                    questionary.print(f"Updated {field_key}.")
                    # Offer cross-service sync for auth credential fields
                    if len(parent_path_parts) >= 2 and parent_path_parts[0] == "auth":  # noqa: PLR2004
                        _maybe_sync_auth_change(
                            instance_key, parent_path_parts[1], field_key, new_val, current_val
                        )
                    break
                except (ValueError, TypeError) as e:
                    questionary.print(f"Error: {e}")
                    retry = questionary.confirm("Try again?", style=custom_style).ask()
                    if not retry:
                        break
            else:
                break


def _edit_instance_dict_loop(  # noqa: C901, PLR0912
    instances: dict,
    item_model: type[BaseModel],
    parent_key: str,
) -> None:
    """Interactive loop for managing a dict[str, BaseModel] (URL-keyed instances)."""
    parent_path_parts = parent_key.split(".")

    while True:
        choices = [
            Choice(title=[("class:key", instance_url)], value=("edit", instance_url))
            for instance_url in instances
        ]
        choices.append(Choice(title="[Add instance]", value=("add", None)))
        if len(instances) > 1:
            choices.append(Choice(title="[Remove instance]", value=("remove", None)))
        choices.append(Choice(title="[Back]", value=("back", None)))

        action, instance_url = questionary.select(
            f"Manage instances for '{parent_key}':",
            choices=choices,
            style=custom_style,
        ).ask() or ("back", None)

        if action == "back" or action is None:
            return

        if action == "add":
            new_url = questionary.text(
                "Enter the base URL for the new instance (e.g. https://company.atlassian.net):",
                validate=lambda v: (
                    "URL cannot be empty" if not v.strip()
                    else "Instance already exists" if v.strip() in instances
                    else True
                ),
                style=custom_style,
            ).ask()
            if new_url:
                new_url = new_url.strip().rstrip("/")
                new_instance = item_model()
                set_setting_with_keys([*parent_path_parts, new_url], new_instance.model_dump())
                instances[new_url] = new_instance.model_dump()
            continue

        if action == "remove":
            if len(instances) <= 1:
                questionary.print("Cannot remove the only instance.", style="fg:yellow")
                continue
            choices_r = [Choice(title=url, value=url) for url in instances]
            to_remove = questionary.select(
                "Select instance to remove:",
                choices=choices_r,
                style=custom_style,
            ).ask()
            if to_remove:
                confirm = questionary.confirm(
                    f"Remove instance '{to_remove}'?", default=False, style=custom_style
                ).ask()
                if confirm:
                    instances.pop(to_remove, None)
                    current = get_settings().model_dump()
                    sub: dict = current
                    for k in parent_path_parts:
                        sub = sub[k]
                    sub.pop(to_remove, None)
                    save_app_data(ConfigModel.model_validate(current))
            continue

        if action == "edit" and instance_url:
            current_val = instances.get(instance_url, {})
            if not isinstance(current_val, dict):
                current_val = current_val.model_dump()  # type: ignore[union-attr]
            _edit_instance_fields(instance_url, current_val, item_model, parent_path_parts)
            # Refresh from disk
            updated = get_settings().model_dump()
            sub = updated
            for k in parent_path_parts:
                sub = sub[k]
            instances[instance_url] = sub.get(instance_url, current_val)


def _main_config_menu(settings: dict, default: tuple[str, bool] | None = None) -> tuple:
    choices = []
    for k, v in settings.items():
        meta = _get_field_metadata(ConfigModel, k)
        display_title = meta["title"] if meta and meta["title"] else k
        if isinstance(v, dict):
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", "  [submenu]"),
                    ],
                    value=(k, True),
                )
            )
        else:
            display_val = "Not set" if isinstance(v, str | SecretStr) and str(v) == "" else v
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", f"  {display_val}"),
                    ],
                    value=(k, False),
                )
            )
    choices.append(Choice(title="[Reset config to defaults]", value=("__reset__", False)))
    choices.append(Choice(title="[Exit]", value=("__exit__", False)))
    # Find the matching Choice value for default
    default_value = None
    if default is not None:
        for c in choices:
            if hasattr(c, "value") and c.value == default:
                default_value = c.value
                break
    return questionary.select(
        f"Config file location: {get_app_config_path()}\n\nSelect a config to change (or reset):",
        choices=choices,
        style=custom_style,
        default=default_value,
    ).ask() or (None, False)


def _prompt_for_new_value(  # noqa: PLR0911
    key_name: str,
    current_value: object,
    model: type[BaseModel],
) -> object:
    field_type = _get_field_type(model, key_name)
    origin = get_origin(field_type)
    prompt_message = _format_prompt_message(key_name, model)
    if field_type is None:
        field_type = str  # Default to string if no type found
    if origin is Literal:
        return _prompt_literal(prompt_message, field_type, current_value)
    if field_type is bool:
        return _prompt_bool(prompt_message, current_value)
    if field_type is Path:
        return _prompt_path(prompt_message, current_value, model, key_name)
    if field_type is int:
        return _prompt_int(prompt_message, current_value)
    if field_type is list or origin is list:
        return _prompt_list(prompt_message, current_value)
    if isinstance(current_value, SecretStr):
        return _prompt_str(prompt_message, current_value.get_secret_value(), model, key_name)
    return _prompt_str(prompt_message, current_value, model, key_name)


_AUTH_CREDENTIAL_FIELDS = {"username", "api_token", "pat"}


def _maybe_sync_auth_change(
    instance_url: str,
    service: str,
    key: str,
    value_cast: object,
    previous_value: object,
) -> None:
    """After changing an auth credential, offer to sync it to the paired service instance.

    Args:
        instance_url: The URL key of the instance being edited (may contain dots).
        service: ``"confluence"`` or ``"jira"``.
        key: The field name that changed (``"username"``, ``"api_token"``, or ``"pat"``).
        value_cast: The new value.
        previous_value: The old value (used to skip the prompt when was empty before).
    """
    if key not in _AUTH_CREDENTIAL_FIELDS:
        return

    if service == "confluence":
        other_service = "Jira"
        other_service_key = "jira"
    elif service == "jira":
        other_service = "Confluence"
        other_service_key = "confluence"
    else:
        return

    # Only ask when replacing an existing (non-empty) value
    if isinstance(previous_value, SecretStr):
        if not previous_value.get_secret_value():
            return
    elif not previous_value:
        return

    should_sync = questionary.confirm(
        f"Also apply this {key} change to the {other_service} instance '{instance_url}'?",
        default=True,
        style=custom_style,
    ).ask()
    if should_sync:
        try:
            set_setting_with_keys(["auth", other_service_key, instance_url, key], value_cast)
            questionary.print(f"auth.{other_service_key}.{instance_url}.{key} updated to match.")
        except (ValueError, TypeError) as e:
            questionary.print(f"Could not sync to {other_service}: {e}")


def _reset_and_reload(parent_key: str | None, display_title: str | None = None) -> None:
    """Reset config (whole or section) and reload config_dict from disk, with confirmation."""
    if parent_key is None:
        confirm_msg = "Are you sure you want to reset all config to defaults?"
    else:
        confirm_msg = f"Are you sure you want to reset section '{display_title}' to defaults?"
    confirm = questionary.confirm(confirm_msg, style=custom_style).ask()
    if not confirm:
        return
    reset_to_defaults(parent_key or None)
    updated = get_settings().model_dump()
    if parent_key:
        # Traverse to the correct nested dict for jmespath/dot-paths
        keys = parent_key.split(".")
        sub = updated
        for k in keys:
            sub = sub[k]
        # Optionally, update sub in place if needed (here, just to trigger reload/print)
    else:
        for k in list(updated.keys()):
            updated[k] = updated[k]
    if display_title:
        questionary.print(f"Section '{display_title}' reset to defaults.")
    else:
        questionary.print("Config reset to defaults.")


def _get_choices(config_dict: dict, model: type[BaseModel]) -> list:
    choices = []
    for k, v in config_dict.items():
        if v is None:
            continue
        meta = _get_field_metadata(model, k)
        display_title = meta["title"] if meta and meta["title"] else k
        if isinstance(v, dict):
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", "  [submenu]"),
                    ],
                    value=k,
                )
            )
        else:
            display_val = "Not set" if isinstance(v, str | SecretStr) and str(v) == "" else v
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", f"  {display_val}"),
                    ],
                    value=k,
                )
            )
    choices.append(Choice(title="[Reset this group to defaults]", value="__reset_section__"))
    choices.append(Choice(title="[Back]", value="__back__"))
    return choices


def _edit_dict_config_loop(  # noqa: C901, PLR0912, PLR0915
    config_dict: dict,
    model: type[BaseModel],
    parent_key: str,
    parent_model: type[BaseModel],
    last_selected: str | None = None,
) -> str | None:
    selected_key = last_selected
    while True:
        choices = _get_choices(config_dict, model)
        meta = None
        if hasattr(parent_model, "model_fields") and parent_key:
            meta = _get_field_metadata(parent_model, parent_key)
        display_title = meta["title"] if meta and meta["title"] else parent_key
        key = questionary.select(
            f"Edit options for '{display_title}':",
            choices=choices,
            style=custom_style,
            default=selected_key,
        ).ask()
        if key == "__back__" or key is None:
            return selected_key
        if key == "__reset_section__":
            _reset_and_reload(parent_key, display_title)
            # Reload the updated config_dict for this section from disk
            updated = get_settings().model_dump()
            if parent_key:
                # Traverse to the correct nested dict for jmespath/dot-paths
                keys = parent_key.split(".")
                sub = updated
                for k in keys:
                    sub = sub[k]
                config_dict.clear()
                config_dict.update(sub)
            else:
                config_dict.clear()
                config_dict.update(updated)
            selected_key = None
            continue
        current_value = config_dict[key] if key else None
        # Check for dict[str, BaseModel] (named instances, e.g. auth.confluence)
        dict_value_model = _get_dict_value_model(model, key)
        if isinstance(current_value, dict) and dict_value_model is not None:
            _edit_instance_dict_loop(
                current_value,
                dict_value_model,
                f"{parent_key}.{key}" if parent_key else key,
            )
            selected_key = key
            continue
        submodel = _get_submodel(model, key)
        if isinstance(current_value, dict) and submodel is not None:
            # Always set selected_key to the submenu key after returning
            _edit_dict_config_loop(
                current_value,
                submodel,
                f"{parent_key}.{key}" if parent_key else key,
                model,
                last_selected=None,
            )
            selected_key = key
        else:
            while True:
                value_cast = _prompt_for_new_value(key, current_value, model)
                if value_cast is not None:
                    try:
                        set_setting(f"{parent_key}.{key}" if parent_key else key, value_cast)
                        config_dict[key] = value_cast
                        questionary.print(f"{parent_key}.{key} updated to {value_cast}.")
                        selected_key = key
                        break
                    except (ValueError, TypeError) as e:
                        questionary.print(f"Error: {e}")
                        retry = questionary.confirm("Try again?", style=custom_style).ask()
                        if not retry:
                            break
                else:
                    break
            # After editing, keep cursor at this entry
            selected_key = key


def _edit_dict_config(
    config_dict: dict,
    model: type[BaseModel],
    parent_key: str,
    parent_model: type[BaseModel],
    last_selected: str | None = None,
) -> str | None:
    return _edit_dict_config_loop(config_dict, model, parent_key, parent_model, last_selected)


def main_config_menu_loop(jump_to: str | None = None) -> None:  # noqa: C901, PLR0912
    settings = get_settings().model_dump()
    if jump_to:
        submenu = jmespath.search(jump_to, settings)
        preselect: str | None = None
        if not isinstance(submenu, dict):
            # jump_to points to a leaf value — open its parent section with cursor on that item
            leaf_key = jump_to.rsplit(".", 1)[-1]
            jump_to = jump_to.rsplit(".", 1)[0] if "." in jump_to else jump_to
            submenu = jmespath.search(jump_to, settings)
            preselect = leaf_key
        parent_path = jump_to.rsplit(".", 1)[0] if "." in jump_to else None
        parent_model = get_model_by_path(ConfigModel, parent_path) if parent_path else ConfigModel
        # If jump_to resolves to a dict[str, BaseModel] field (URL-keyed instances such as
        # auth.confluence), delegate directly to the instance-dict editor so that
        # URL keys are never mistaken for Pydantic field names.
        last_segment = jump_to.rsplit(".", 1)[-1] if "." in jump_to else jump_to
        dict_value_model = _get_dict_value_model(parent_model, last_segment)
        if dict_value_model is not None and isinstance(submenu, dict):
            _edit_instance_dict_loop(submenu, dict_value_model, jump_to)
            return
        submodel = get_model_by_path(ConfigModel, jump_to)
        _edit_dict_config(submenu, submodel, jump_to, parent_model, last_selected=preselect)
        return
    last_selected = None
    while True:
        settings = get_settings().model_dump()
        key, is_dict = _main_config_menu(settings, default=last_selected)
        if key == "__reset__":
            _reset_and_reload(None)
            last_selected = None
            continue
        if key == "__exit__" or key is None:
            break
        last_selected = (key, is_dict)
        current_value = settings[key]
        if is_dict:
            submodel = _get_submodel(ConfigModel, key)
            if submodel is not None:
                returned_key = _edit_dict_config(
                    current_value, submodel, key, ConfigModel, last_selected=None
                )
                last_selected = (key, is_dict) if returned_key is None else (returned_key, True)
        else:
            while True:
                value_cast = _prompt_for_new_value(key, current_value, ConfigModel)
                if value_cast is None or value_cast == current_value:
                    # User cancelled or made no change: do not update config
                    break
                try:
                    set_setting(key, value_cast)
                    questionary.print(f"{key} updated to {value_cast}.")
                    last_selected = (key, is_dict)
                    break
                except (ValueError, TypeError) as e:
                    questionary.print(f"Error: {e}")
                    retry = questionary.confirm("Try again?", style=custom_style).ask()
                    if not retry:
                        break
