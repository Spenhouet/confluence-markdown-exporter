"""Unit tests for the measure_time module."""

import logging
import time
from datetime import datetime
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.utils.measure_time import measure
from confluence_markdown_exporter.utils.measure_time import measure_time


class TestMeasureTime:
    """Test cases for measure_time decorator."""

    def test_measure_time_decorator_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that measure_time decorator logs execution time."""
        logger_name = "confluence_markdown_exporter.utils.measure_time"
        caplog.set_level(logging.INFO, logger=logger_name)

        @measure_time
        def test_function(x: int, y: int) -> int:
            time.sleep(0.01)
            return x + y

        result = test_function(2, 3)
        assert result == 5

        log_messages = [record.message for record in caplog.records]
        assert len(log_messages) == 1
        assert "Function 'test_function' took" in log_messages[0]
        assert "seconds to execute" in log_messages[0]

    def test_measure_time_with_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that measure_time decorator handles exceptions properly."""
        logger_name = "confluence_markdown_exporter.utils.measure_time"
        caplog.set_level(logging.INFO, logger=logger_name)

        @measure_time
        def failing_function() -> None:
            msg = "Test error"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        # The decorator should not log on exception (it only logs on success)
        log_messages = [record.message for record in caplog.records]
        assert len(log_messages) == 0

    def test_measure_time_with_return_value(self) -> None:
        """Test that measure_time decorator preserves return values."""

        @measure_time
        def function_with_return() -> str:
            return "test_result"

        result = function_with_return()
        assert result == "test_result"

    def test_measure_time_with_args_kwargs(self) -> None:
        """Test that measure_time decorator works with args and kwargs."""

        @measure_time
        def function_with_params(a: int, b: int, c: int = 3) -> int:
            return a + b + c

        result = function_with_params(1, 2, c=4)
        assert result == 7


class TestMeasureContextManager:
    """Test cases for measure context manager."""

    def test_measure_success(self) -> None:
        """Test measure context manager completes successfully."""
        with measure("Test Operation"):
            time.sleep(0.01)

    def test_measure_with_exception(self) -> None:
        """Test measure context manager re-raises exceptions."""

        def failing_operation() -> None:
            msg = "Test error"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Test error"), measure("Failing Operation"):
            failing_operation()

    def test_measure_debug_logs_start(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that measure logs the start time at DEBUG level."""
        logger_name = "confluence_markdown_exporter.utils.measure_time"
        caplog.set_level(logging.DEBUG, logger=logger_name)

        with measure("Debug Operation"):
            pass

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("Started at" in m for m in debug_messages)

    @patch("confluence_markdown_exporter.utils.measure_time.datetime")
    def test_measure_timing_calculation(self, mock_datetime: pytest.MonkeyPatch) -> None:
        """Test that measure context manager does not suppress exceptions on timing."""
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 5)

        mock_datetime.now.side_effect = [start_time, end_time]

        with measure("Timed Operation"):
            pass

    def test_measure_no_exception_propagation(self) -> None:
        """Test that measure context manager doesn't suppress exceptions."""

        class CustomError(Exception):
            pass

        def raise_error() -> None:
            msg = "Custom error message"
            raise CustomError(msg)

        with pytest.raises(CustomError), measure("Exception Test"):
            raise_error()
