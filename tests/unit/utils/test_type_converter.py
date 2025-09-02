"""Unit tests for type_converter module."""

import pytest

from confluence_markdown_exporter.utils.type_converter import str_to_bool


class TestStrToBool:
    """Test cases for str_to_bool function."""

    def test_true_values(self) -> None:
        """Test that various true values are converted correctly."""
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES", "on", "On", "ON"]
        for value in true_values:
            assert str_to_bool(value) is True, f"Failed for value: {value}"

    def test_false_values(self) -> None:
        """Test that various false values are converted correctly."""
        false_values = [
            "false",
            "False",
            "FALSE",
            "0",
            "no",
            "No",
            "NO",
            "off",
            "Off",
            "OFF",
        ]
        for value in false_values:
            assert str_to_bool(value) is False, f"Failed for value: {value}"

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is properly stripped."""
        assert str_to_bool("  true  ") is True
        assert str_to_bool("\tfalse\t") is False
        assert str_to_bool("\n1\n") is True
        assert str_to_bool("  0  ") is False

    def test_invalid_values(self) -> None:
        """Test that invalid values raise ValueError."""
        invalid_values = ["maybe", "2", "invalid", "", "true false", "truthy"]
        for value in invalid_values:
            with pytest.raises(ValueError, match=f"Invalid boolean string: '{value}'"):
                str_to_bool(value)

    def test_empty_string(self) -> None:
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid boolean string: ''"):
            str_to_bool("")

    def test_none_handling(self) -> None:
        """Test behavior with None (should raise AttributeError for strip method)."""
        with pytest.raises(AttributeError):
            str_to_bool(None)  # type: ignore[arg-type]
