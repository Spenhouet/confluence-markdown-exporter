"""Confluence Markdown Exporter package."""

try:
    from importlib.metadata import version
    __version__ = version("confluence-markdown-exporter")
except ImportError:
    # fallback for Python < 3.8
    from importlib_metadata import version
    __version__ = version("confluence-markdown-exporter")
except Exception:
    # fallback if package not installed or metadata not available
    __version__ = "unknown"