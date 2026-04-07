"""Shared rich console, logging setup, and export statistics tracking."""

import logging
import threading
from dataclasses import dataclass
from dataclasses import field
from os import getenv

from rich.console import Console
from rich.logging import RichHandler
from rich.style import Style
from rich.theme import Theme

_CME_THEME = Theme(
    {
        "none": Style.null(),
        "reset": Style(
            color="default",
            bgcolor="default",
            dim=False,
            bold=False,
            italic=False,
            underline=False,
            blink=False,
            blink2=False,
            reverse=False,
            conceal=False,
            strike=False,
        ),
        "dim": Style(dim=True),
        "bright": Style(dim=False),
        "bold": Style(bold=True),
        "strong": Style(bold=True),
        "code": Style(reverse=True, bold=True),
        "italic": Style(italic=True),
        "emphasize": Style(italic=True),
        "underline": Style(underline=True),
        "blink": Style(blink=True),
        "blink2": Style(blink2=True),
        "reverse": Style(reverse=True),
        "strike": Style(strike=True),
        "black": Style(color="black"),
        "red": Style(color="red"),
        "green": Style(color="green"),
        "yellow": Style(color="yellow"),
        "magenta": Style(color="magenta"),
        "cyan": Style(color="cyan"),
        "white": Style(color="white"),
        "inspect.attr": Style(color="yellow", italic=True),
        "inspect.attr.dunder": Style(color="yellow", italic=True, dim=True),
        "inspect.callable": Style(bold=True, color="red"),
        "inspect.async_def": Style(italic=True, color="bright_cyan"),
        "inspect.def": Style(italic=True, color="bright_cyan"),
        "inspect.class": Style(italic=True, color="bright_cyan"),
        "inspect.error": Style(bold=True, color="red"),
        "inspect.equals": Style(),
        "inspect.help": Style(color="cyan"),
        "inspect.doc": Style(dim=True),
        "inspect.value.border": Style(color="green"),
        "live.ellipsis": Style(bold=True, color="red"),
        "layout.tree.row": Style(dim=False, color="red"),
        "layout.tree.column": Style(dim=False, color="blue"),
        "logging.keyword": Style(bold=True, color="yellow"),
        "logging.level.notset": Style(dim=True),
        "logging.level.debug": Style(color="green"),
        "logging.level.info": Style(color="blue"),
        "logging.level.warning": Style(color="yellow"),
        "logging.level.error": Style(color="red", bold=True),
        "logging.level.critical": Style(color="red", bold=True, reverse=True),
        "log.level": Style.null(),
        "log.time": Style(color="cyan", dim=True),
        "log.message": Style.null(),
        "log.path": Style(dim=True),
        "repr.ellipsis": Style(color="yellow"),
        "repr.indent": Style(color="green", dim=True),
        "repr.error": Style(color="red", bold=True),
        "repr.str": Style(color="green", italic=False, bold=False),
        "repr.brace": Style(bold=True),
        "repr.comma": Style(bold=True),
        "repr.ipv4": Style(bold=True, color="bright_green"),
        "repr.ipv6": Style(bold=True, color="bright_green"),
        "repr.eui48": Style(bold=True, color="bright_green"),
        "repr.eui64": Style(bold=True, color="bright_green"),
        "repr.tag_start": Style(bold=True),
        "repr.tag_name": Style(color="bright_magenta", bold=True),
        "repr.tag_contents": Style(color="default"),
        "repr.tag_end": Style(bold=True),
        "repr.attrib_name": Style(color="yellow", italic=False),
        "repr.attrib_equal": Style(bold=True),
        "repr.attrib_value": Style(color="magenta", italic=False),
        "repr.number": Style(color="cyan", bold=True, italic=False),
        "repr.number_complex": Style(color="cyan", bold=True, italic=False),  # same
        "repr.bool_true": Style(color="bright_green", italic=True),
        "repr.bool_false": Style(color="bright_red", italic=True),
        "repr.none": Style(color="magenta", italic=True),
        "repr.url": Style(underline=True, color="bright_blue", italic=False, bold=False),
        "repr.uuid": Style(color="bright_yellow", bold=False),
        "repr.call": Style(color="magenta", bold=True),
        "repr.path": Style(color="magenta"),
        "repr.filename": Style(color="bright_magenta"),
        "rule.line": Style(color="bright_green"),
        "rule.text": Style.null(),
        "json.brace": Style(bold=True),
        "json.bool_true": Style(color="bright_green", italic=True),
        "json.bool_false": Style(color="bright_red", italic=True),
        "json.null": Style(color="magenta", italic=True),
        "json.number": Style(color="cyan", bold=True, italic=False),
        "json.str": Style(color="green", italic=False, bold=False),
        "json.key": Style(color="blue", bold=True),
        "prompt": Style.null(),
        "prompt.choices": Style(color="magenta", bold=True),
        "prompt.default": Style(color="cyan", bold=True),
        "prompt.invalid": Style(color="red"),
        "prompt.invalid.choice": Style(color="red"),
        "pretty": Style.null(),
        "scope.border": Style(color="blue"),
        "scope.key": Style(color="yellow", italic=True),
        "scope.key.special": Style(color="yellow", italic=True, dim=True),
        "scope.equals": Style(color="red"),
        "table.header": Style(bold=True),
        "table.footer": Style(bold=True),
        "table.cell": Style.null(),
        "table.title": Style(italic=True),
        "table.caption": Style(italic=True, dim=True),
        "traceback.error": Style(color="red", italic=True),
        "traceback.border.syntax_error": Style(color="bright_red"),
        "traceback.border": Style(color="red"),
        "traceback.text": Style.null(),
        "traceback.title": Style(color="red", bold=True),
        "traceback.exc_type": Style(color="bright_red", bold=True),
        "traceback.exc_value": Style.null(),
        "traceback.offset": Style(color="bright_red", bold=True),
        "traceback.error_range": Style(underline=True, bold=True),
        "traceback.note": Style(color="green", bold=True),
        "traceback.group.border": Style(color="magenta"),
        "bar.back": Style(color="grey23"),
        "bar.complete": Style(color="rgb(249,38,114)"),
        "bar.finished": Style(color="rgb(114,156,31)"),
        "bar.pulse": Style(color="rgb(249,38,114)"),
        "progress.description": Style.null(),
        "progress.filesize": Style(color="green"),
        "progress.filesize.total": Style(color="green"),
        "progress.download": Style(color="green"),
        "progress.elapsed": Style(color="yellow"),
        "progress.percentage": Style(color="magenta"),
        "progress.remaining": Style(color="cyan"),
        "progress.data.speed": Style(color="red"),
        "progress.spinner": Style(color="green"),
        "status.spinner": Style(color="green"),
        "tree": Style(),
        "tree.line": Style(),
        "markdown.paragraph": Style(),
        "markdown.text": Style(),
        "markdown.em": Style(italic=True),
        "markdown.emph": Style(italic=True),  # For commonmark backwards compatibility
        "markdown.strong": Style(bold=True),
        "markdown.code": Style(color="cyan"),
        "markdown.code_block": Style(color="cyan"),
        "markdown.block_quote": Style(color="magenta"),
        "markdown.list": Style(color="cyan"),
        "markdown.item": Style(),
        "markdown.item.bullet": Style(color="yellow", bold=True),
        "markdown.item.number": Style(color="yellow", bold=True),
        "markdown.hr": Style(color="yellow"),
        "markdown.h1.border": Style(),
        "markdown.h1": Style(bold=True),
        "markdown.h2": Style(bold=True, underline=True),
        "markdown.h3": Style(bold=True),
        "markdown.h4": Style(bold=True, dim=True),
        "markdown.h5": Style(underline=True),
        "markdown.h6": Style(italic=True),
        "markdown.h7": Style(italic=True, dim=True),
        "markdown.link": Style(color="bright_blue"),
        "markdown.link_url": Style(color="blue", underline=True),
        "markdown.s": Style(strike=True),
        "iso8601.date": Style(color="blue"),
        "iso8601.time": Style(color="magenta"),
        "iso8601.timezone": Style(color="yellow"),
    }
)

TERMINAL_WIDTH = getenv("TERMINAL_WIDTH")
MAX_WIDTH = int(TERMINAL_WIDTH) if TERMINAL_WIDTH else None
FORCE_TERMINAL = (
    False
    if getenv("NO_COLOR") or getenv("CI")
    else True
    if getenv("FORCE_COLOR") or getenv("PY_COLORS") or getenv("GITHUB_ACTIONS")
    else None
)


def get_rich_console(*, stderr: bool = False) -> Console:
    return Console(
        theme=_CME_THEME,
        highlight=False,
        # In CI, disable live rendering (no ANSI escapes, no overwriting lines, no colors)
        force_terminal=FORCE_TERMINAL,
        width=MAX_WIDTH,
        stderr=stderr,
    )


console: Console = get_rich_console()


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
        markup=False,
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
    removed: int = 0
    attachments_exported: int = 0
    attachments_skipped: int = 0
    attachments_failed: int = 0
    attachments_removed: int = 0
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

    def inc_removed(self) -> None:
        """Increment the pages removed counter by 1."""
        with self._lock:
            self.removed += 1

    def inc_attachments_exported(self) -> None:
        """Increment the attachments exported counter by 1."""
        with self._lock:
            self.attachments_exported += 1

    def inc_attachments_skipped(self) -> None:
        """Increment the attachments skipped counter by 1."""
        with self._lock:
            self.attachments_skipped += 1

    def inc_attachments_failed(self) -> None:
        """Increment the attachments failed counter by 1."""
        with self._lock:
            self.attachments_failed += 1

    def inc_attachments_removed(self) -> None:
        """Increment the attachments removed counter by 1."""
        with self._lock:
            self.attachments_removed += 1


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
