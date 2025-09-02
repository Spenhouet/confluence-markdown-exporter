"""Unit tests for the measure_time module."""

import logging
import time
from datetime import datetime
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.utils.measure_time import format_log_message
from confluence_markdown_exporter.utils.measure_time import measure
from confluence_markdown_exporter.utils.measure_time import measure_time


class TestMeasureTime:
    """Test cases for measure_time decorator."""

    def test_measure_time_decorator_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that measure_time decorator logs execution time."""
        # Capture logs from the specific logger used by measure_time
        logger_name = "confluence_markdown_exporter.utils.measure_time"
        caplog.set_level(logging.INFO, logger=logger_name)

        @measure_time
        def test_function(x: int, y: int) -> int:
            time.sleep(0.01)  # Small delay to ensure measurable time
            return x + y

        result = test_function(2, 3)
        assert result == 5

        # Check that log message contains function name and time
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


class TestFormatLogMessage:
    """Test cases for format_log_message function."""

    def test_format_log_message_basic(self) -> None:
        """Test basic log message formatting."""
        test_time = datetime(2023, 1, 1, 12, 0, 0)
        result = format_log_message("Test Step", test_time, "started")
        assert result == "Test Step started at 2023-01-01 12:00:00"

    def test_format_log_message_different_states(self) -> None:
        """Test log message formatting with different states."""
        test_time = datetime(2023, 6, 15, 9, 30, 45)

        # Test started state
        result = format_log_message("Process", test_time, "started")
        assert result == "Process started at 2023-06-15 09:30:45"

        # Test ended state
        result = format_log_message("Process", test_time, "ended")
        assert result == "Process ended at 2023-06-15 09:30:45"

        # Test failed state
        result = format_log_message("Process", test_time, "failed")
        assert result == "Process failed at 2023-06-15 09:30:45"

    def test_format_log_message_special_characters(self) -> None:
        """Test log message formatting with special characters in step name."""
        test_time = datetime(2023, 12, 25, 23, 59, 59)
        result = format_log_message("Data Export: Phase 1", test_time, "completed")
        assert result == "Data Export: Phase 1 completed at 2023-12-25 23:59:59"


class TestMeasureContextManager:
    """Test cases for measure context manager."""

    def test_measure_success(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test measure context manager with successful execution."""
        logger_name = "confluence_markdown_exporter.utils.measure_time"
        caplog.set_level(logging.INFO, logger=logger_name)

        with measure("Test Operation"):
            time.sleep(0.01)

        log_messages = [record.message for record in caplog.records]
        # Context manager logs: start, end, and duration
        assert len(log_messages) == 3
        assert "Test Operation started at" in log_messages[0]
        assert "Test Operation ended at" in log_messages[1]
        assert "Test Operation took" in log_messages[2]

    def test_measure_with_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test measure context manager with exception."""
        logger_name = "confluence_markdown_exporter.utils.measure_time"
        caplog.set_level(logging.INFO, logger=logger_name)

        def failing_operation() -> None:
            msg = "Test error"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Test error"), measure("Failing Operation"):
            failing_operation()

        log_messages = [record.message for record in caplog.records]
        # Context manager logs: start, failed, and duration
        assert len(log_messages) == 3
        assert "Failing Operation started at" in log_messages[0]
        assert "Failing Operation failed at" in log_messages[1]
        assert "Failing Operation took" in log_messages[2]

    @patch("confluence_markdown_exporter.utils.measure_time.datetime")
    def test_measure_timing_calculation(
        self, mock_datetime: Mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that measure context manager calculates duration correctly."""
        # Mock datetime to control timing
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 5)  # 5 seconds later

        mock_datetime.now.side_effect = [start_time, end_time]

        logger_name = "confluence_markdown_exporter.utils.measure_time"
        caplog.set_level(logging.INFO, logger=logger_name)

        with measure("Timed Operation"):
            pass

        log_messages = [record.message for record in caplog.records]
        assert len(log_messages) >= 2
        assert "Timed Operation started at 2023-01-01 12:00:00" in log_messages[0]
        assert "Timed Operation ended at 2023-01-01 12:00:05" in log_messages[1]

    def test_measure_no_exception_propagation(self) -> None:
        """Test that measure context manager doesn't suppress exceptions."""

        class CustomError(Exception):
            pass

        def raise_error() -> None:
            msg = "Custom error message"
            raise CustomError(msg)

        with pytest.raises(CustomError), measure("Exception Test"):
            raise_error()
