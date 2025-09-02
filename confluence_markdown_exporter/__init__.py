"""Confluence Markdown Exporter package."""

try:
    from importlib.metadata import version

    __version__ = version("confluence-markdown-exporter")
except Exception:  # noqa: BLE001
    # fallback if package not installed or metadata not available
    __version__ = "unknown"
