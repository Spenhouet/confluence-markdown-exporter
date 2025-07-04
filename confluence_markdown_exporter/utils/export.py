import json
import re
from pathlib import Path

from confluence_markdown_exporter.utils.app_data_store import get_settings

settings = get_settings()
export_options = settings.export


def parse_encode_setting(encode_setting: str) -> dict[str, str]:
    """Parse encoding setting containing character mapping.

    Args:
        encode_setting: JSON object content without braces
            '"char1":"replacement1","char2":"replacement2"'

    Returns:
        Dictionary mapping characters to their replacements

    Examples:
        "" -> {}
        '" ":"%2D","-":"%2D"' -> {" ": "%2D", "-": "%2D"}
        '" ":"dash","-":"%2D"' -> {" ": "dash", "-": "%2D"}
        '"=":" equals "' -> {"=": " equals "}

    Note:
        Uses JSON format for mapping to handle all characters unambiguously.
        Curly braces are added automatically before parsing.
    """
    if not encode_setting:
        return {}

    # Add curly braces to make it valid JSON
    json_str = f"{{{encode_setting}}}"

    # Use JSON parsing for robust and unambiguous parsing
    try:
        mapping = json.loads(json_str)
        if isinstance(mapping, dict):
            return mapping
    except (json.JSONDecodeError, TypeError):
        # Fallback: if parsing fails, return empty mapping
        pass

    return {}


def save_file(file_path: Path, content: str | bytes) -> None:
    """Save content to a file, creating parent directories as needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        with file_path.open("wb") as file:
            file.write(content)
    elif isinstance(content, str):
        with file_path.open("w", encoding="utf-8") as file:
            file.write(content)
    else:
        msg = "Content must be either a string or bytes."
        raise TypeError(msg)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for cross-platform compatibility.

    Replaces characters based on encoding mapping,
    trims trailing spaces and dots, and prevents reserved names.

    Args:
        filename: The original filename.

    Returns:
        A sanitized filename string.
    """
    sanitized = filename

    if export_options.filename_encoding:
        encode_map = parse_encode_setting(export_options.filename_encoding)

        # Create pattern from all characters that have mappings
        if encode_map:
            chars_to_encode = "".join(encode_map.keys())
            encode_re = escape_character_class(chars_to_encode)
            encode_pattern = re.compile(f"[{encode_re}]")

            def map_char(m: re.Match[str]) -> str:
                char = m.group(0)
                return encode_map[char]

            sanitized = re.sub(encode_pattern, map_char, sanitized)

    # Trim spaces and dots from the end
    sanitized = sanitized.rstrip(" .")

    # Reserved Windows names (case-insensitive)
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }

    name = Path(sanitized).stem.upper()
    if name in reserved:
        sanitized = f"{sanitized}_"

    # Limit length to specificed number of characters
    return sanitized[: export_options.filename_length]


def sanitize_key(s: str, connector: str = "_") -> str:
    """Convert an input string to a valid Python/YAML-compatible key.

    - Lowercase the string.
    - Replace non-alphanumeric characters with underscores.
    - Collapse multiple underscores into one.
    - Trim leading/trailing underscores.
    - Prefix with 'key_' if the first character is not a letter or underscore.
    """
    s = s.lower()
    s = re.sub(f"[^a-z0-9{connector}]", connector, s)
    s = re.sub(f"{connector}+", connector, s)
    s = s.strip(connector)
    if not re.match(r"^[a-z]", s):
        s = f"key{connector}{s}"
    return s


def escape_character_class(s: str) -> str:
    """Escape characters for use in a regex character class.

    Args:
        s: The string containing characters to escape.

    Returns:
        The input string with special regex character class characters escaped.
    """
    # Escape backslash first, then other special characters for character classes
    return s.replace("\\", r"\\").replace("-", r"\-").replace("]", r"\]").replace("^", r"\^")
