"""Utility module for parsing DrawIO files and extracting mermaid diagrams."""

import html
import json
import logging
from pathlib import Path
from typing import cast

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def load_drawio_file(file_path: str | Path) -> str | None:
    """Load and parse a DrawIO XML file.

    Args:
        file_path: Path to the DrawIO file (.drawio)

    Returns:
        The XML content as a string, or None if file doesn't exist
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return None

    return file_path.read_text(encoding="utf-8")


def extract_mermaid_data(xml_content: str) -> str | None:
    """Extract mermaid data from DrawIO XML.

    Args:
        xml_content: The XML content as a string.

    Returns:
        The extracted mermaid data string or None if not found.
    """
    try:
        soup = BeautifulSoup(xml_content, "xml")
        # Search for UserObject tag (XML parser preserves case)
        user_object = soup.find("UserObject")
        if user_object is None:
            return None
        try:
            attrs = cast(
                "dict[str, str]",
                user_object.attrs,  # type: ignore[attr-defined]
            )
            # XML parser preserves attribute case as mermaidData
            mermaid_data_attr = attrs.get("mermaidData")
            if mermaid_data_attr is None:
                return None
            # Unescape HTML entities if present
            return html.unescape(mermaid_data_attr)
        except AttributeError:
            return None
    except Exception:  # pylint: disable=broad-except
        logger.exception("Error extracting mermaid data from DrawIO XML")
        return None


def parse_mermaid_json(mermaid_data: str) -> str | None:
    """Parse mermaid data from JSON format and extract the diagram definition.

    The mermaid data is often stored as JSON with a "data" field containing
    the actual mermaid diagram as a string.

    Args:
        mermaid_data: The raw mermaid data string (may be JSON-formatted)

    Returns:
        The mermaid diagram string, or the input if already in plain format
    """
    try:
        # Try to parse as JSON
        parsed = json.loads(mermaid_data)
        if isinstance(parsed, dict) and "data" in parsed:
            return parsed["data"]
    except (json.JSONDecodeError, TypeError):
        # If not JSON, return as-is (already a plain diagram string)
        pass

    return mermaid_data


def format_mermaid_markdown(mermaid_diagram: str) -> str:
    """Format mermaid diagram as a markdown code fence.

    Args:
        mermaid_diagram: The mermaid diagram definition

    Returns:
        Formatted markdown code fence containing the mermaid diagram
    """
    return f"```mermaid\n{mermaid_diagram}\n```"


def load_and_parse_drawio(file_path: str | Path) -> str | None:
    """Load a DrawIO file and extract mermaid diagram as markdown.

    This is the main entry point that orchestrates the full process:
    1. Load the DrawIO XML file
    2. Extract mermaidData from UserObject
    3. Parse JSON format if needed
    4. Format as markdown code fence

    Args:
        file_path: Path to the DrawIO file (.drawio)

    Returns:
        Formatted markdown code fence with mermaid diagram, or None if not found/error
    """
    # Load the DrawIO file
    xml_content = load_drawio_file(file_path)
    if xml_content is None:
        return None

    # Extract mermaid data from XML
    mermaid_data = extract_mermaid_data(xml_content)
    if mermaid_data is None:
        return None

    # Parse mermaid data (handle JSON format)
    mermaid_diagram = parse_mermaid_json(mermaid_data)
    if mermaid_diagram is None:
        return None

    # Format as markdown
    return format_mermaid_markdown(mermaid_diagram)
