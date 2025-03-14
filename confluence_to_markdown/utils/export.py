import re
from pathlib import Path


def save_file(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as file:
        file.write(content)


def sanitize_filename(filename: str, replacement: str = "_") -> str:
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
    forbidden_pattern = r'[<>:"/\\|?*\0]'
    sanitized = re.sub(forbidden_pattern, replacement, filename)

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

    # Limit length to 255 characters (common filesystem limit)
    return sanitized[:255]
