import re
import urllib.parse
from pathlib import Path
from confluence_markdown_exporter.utils.app_data_store import ExportConfig


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


def sanitize_filename(filename: str, options: ExportConfig) -> str:
    """Sanitize a filename for cross-platform compatibility.

    Replaces forbidden characters with a replacement string,
    trims trailing spaces and dots, and prevents reserved names.

    Args:
        filename: The original filename.
        replacement: Replacement for forbidden characters.

    Returns:
        A sanitized filename string.
    """
    # Define forbidden characters (Windows + POSIX)
    forbidden_pattern = re.compile(f"[{options.filename_replace}]")
    sanitized = re.sub(forbidden_pattern, options.filename_replace_with, filename)

    if options.filename_encode:
        encode_pattern = re.compile(f"[{options.filename_encode}]")
        def encode_special(m: re.Match[str]) -> str:
            # These are ADO-specific exceptions to URI encoding.
            if m.group(0) == '-':
                return '%2D'
            if m.group(0) == ' ':
                return '-'
            return urllib.parse.quote(m.group(0), safe="")
        sanitized = re.sub(encode_pattern, encode_special, sanitized)

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
    return sanitized[:options.filename_length]


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
