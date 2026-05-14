"""Tests for the logging helpers in rich_console."""

import logging
from pathlib import Path

from confluence_markdown_exporter.utils.rich_console import setup_logging


def test_setup_logging_writes_to_file(tmp_path: Path) -> None:
    """When a log_file is given, log records are also written to that file."""
    log_file = tmp_path / "cme.log"
    setup_logging("DEBUG", log_file=log_file)

    logger = logging.getLogger("cme.test")
    logger.debug("a debug message")
    logger.info("an info message")

    for handler in logging.getLogger().handlers:
        handler.flush()

    contents = log_file.read_text(encoding="utf-8")
    assert "a debug message" in contents
    assert "an info message" in contents


def test_setup_logging_without_file_does_not_create_one(tmp_path: Path) -> None:
    """Default invocation does not create a log file."""
    log_file = tmp_path / "cme.log"
    setup_logging("INFO")

    logging.getLogger("cme.test").info("hello")

    assert not log_file.exists()
