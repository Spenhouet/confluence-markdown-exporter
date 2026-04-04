"""Shared rich console, logging setup, and export statistics tracking."""

import logging
import os
import threading
from dataclasses import dataclass
from dataclasses import field

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

_CME_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "dim": "dim white",
        "highlight": "bold cyan",
        "progress.description": "cyan",
        "progress.percentage": "bold cyan",
    }
)

# Detect CI: rich respects NO_COLOR automatically; we also check CI env var.
_IS_CI: bool = bool(os.environ.get("CI") or os.environ.get("NO_COLOR"))

console: Console = Console(
    theme=_CME_THEME,
    highlight=False,
    # In CI, disable live rendering (no ANSI escapes, no overwriting lines)
    force_terminal=False if _IS_CI else None,
    no_color=_IS_CI,
)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure the root logger to use rich output.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_path=log_level == "DEBUG",
        markup=True,
        log_time_format="[%X]",
    )
    handler.setLevel(level)
    root = logging.getLogger()
    root.setLevel(level)
    # Remove any existing handlers so we don't double-log
    root.handlers.clear()
    root.addHandler(handler)


@dataclass
class ExportStats:
    """Thread-safe counters for a single export run."""

    total: int = 0
    exported: int = 0
    skipped: int = 0
    failed: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def inc_exported(self) -> None:
        """Increment the exported counter by 1."""
        with self._lock:
            self.exported += 1

    def inc_skipped(self) -> None:
        """Increment the skipped counter by 1."""
        with self._lock:
            self.skipped += 1

    def inc_failed(self) -> None:
        """Increment the failed counter by 1."""
        with self._lock:
            self.failed += 1


# Module-level stats instance reset at the start of each export run
_stats: ExportStats = ExportStats()


def reset_stats(total: int = 0) -> ExportStats:
    """Reset and return the global export stats for a new run.

    Args:
        total: Total number of pages in the export scope (including skipped).

    Returns:
        The fresh ExportStats instance.
    """
    global _stats  # noqa: PLW0603
    _stats = ExportStats(total=total)
    return _stats


def get_stats() -> ExportStats:
    """Return the current global export stats."""
    return _stats
