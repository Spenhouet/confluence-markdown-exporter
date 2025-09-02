"""Unit tests for export module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from confluence_markdown_exporter.utils.export import escape_character_class
from confluence_markdown_exporter.utils.export import parse_encode_setting
from confluence_markdown_exporter.utils.export import sanitize_filename
from confluence_markdown_exporter.utils.export import sanitize_key
from confluence_markdown_exporter.utils.export import save_file


class TestParseEncodeSetting:
    """Test cases for parse_encode_setting function."""

    def test_empty_string(self) -> None:
        """Test parsing empty string returns empty dict."""
        result = parse_encode_setting("")
        assert result == {}

    def test_simple_mapping(self) -> None:
        """Test parsing simple character mapping."""
        result = parse_encode_setting('" ":"%2D","-":"%2D"')
        expected = {" ": "%2D", "-": "%2D"}
        assert result == expected

    def test_mixed_mapping(self) -> None:
        """Test parsing mixed character mapping."""
        result = parse_encode_setting('" ":"dash","-":"%2D"')
        expected = {" ": "dash", "-": "%2D"}
        assert result == expected

    def test_equals_mapping(self) -> None:
        """Test parsing equals sign mapping."""
        result = parse_encode_setting('"=":" equals "')
        expected = {"=": " equals "}
        assert result == expected

    def test_special_characters(self) -> None:
        """Test parsing special characters."""
        result = parse_encode_setting('"\\"":" quote ","\\\\":" backslash "')
        expected = {'"': " quote ", "\\": " backslash "}
        assert result == expected

    def test_invalid_json(self) -> None:
        """Test that invalid JSON returns empty dict."""
        result = parse_encode_setting("invalid json")
        assert result == {}

    def test_non_dict_json(self) -> None:
        """Test that non-dict JSON returns empty dict."""
        result = parse_encode_setting('"this is a string"')
        assert result == {}

    def test_malformed_json(self) -> None:
        """Test that malformed JSON returns empty dict."""
        result = parse_encode_setting('"key":"value",')
        assert result == {}


class TestSaveFile:
    """Test cases for save_file function."""

    def test_save_string_content(self) -> None:
        """Test saving string content to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"
            content = "Hello, World!"

            save_file(file_path, content)

            assert file_path.exists()
            assert file_path.read_text(encoding="utf-8") == content

    def test_save_bytes_content(self) -> None:
        """Test saving bytes content to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.bin"
            content = b"Binary content"

            save_file(file_path, content)

            assert file_path.exists()
            assert file_path.read_bytes() == content

    def test_create_parent_directories(self) -> None:
        """Test that parent directories are created when needed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "subdir" / "nested" / "test.txt"
            content = "Test content"

            save_file(file_path, content)

            assert file_path.exists()
            assert file_path.read_text(encoding="utf-8") == content

    def test_overwrite_existing_file(self) -> None:
        """Test overwriting an existing file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"
            original_content = "Original content"
            new_content = "New content"

            save_file(file_path, original_content)
            save_file(file_path, new_content)

            assert file_path.read_text(encoding="utf-8") == new_content

    def test_invalid_content_type(self) -> None:
        """Test that invalid content type raises TypeError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"

            with pytest.raises(TypeError, match="Content must be either a string or bytes."):
                save_file(file_path, 123)  # type: ignore[arg-type]


class TestSanitizeFilename:
    """Test cases for sanitize_filename function."""

    @patch("confluence_markdown_exporter.utils.export.export_options")
    def test_no_encoding_specified(self, mock_export_options: MagicMock) -> None:
        """Test sanitizing filename with no encoding specified."""
        mock_export_options.filename_encoding = ""
        mock_export_options.filename_length = 255

        result = sanitize_filename("Test File.txt")
        assert result == "Test File.txt"

    @patch("confluence_markdown_exporter.utils.export.export_options")
    def test_with_encoding_mapping(self, mock_export_options: MagicMock) -> None:
        """Test sanitizing filename with encoding mapping."""
        mock_export_options.filename_encoding = '" ":"_",":":"_"'
        mock_export_options.filename_length = 255

        result = sanitize_filename("Test File: Name.txt")
        assert result == "Test_File__Name.txt"

    @patch("confluence_markdown_exporter.utils.export.export_options")
    def test_trim_trailing_spaces_and_dots(self, mock_export_options: MagicMock) -> None:
        """Test that trailing spaces and dots are trimmed."""
        mock_export_options.filename_encoding = ""
        mock_export_options.filename_length = 255

        result = sanitize_filename("filename . . ")
        assert result == "filename"

    @patch("confluence_markdown_exporter.utils.export.export_options")
    def test_reserved_windows_names(self, mock_export_options: MagicMock) -> None:
        """Test that reserved Windows names are handled."""
        mock_export_options.filename_encoding = ""
        mock_export_options.filename_length = 255

        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        for name in reserved_names:
            result = sanitize_filename(name)
            assert result == f"{name}_"

            # Test case insensitive
            result = sanitize_filename(name.lower())
            assert result == f"{name.lower()}_"

    @patch("confluence_markdown_exporter.utils.export.export_options")
    def test_filename_length_limit(self, mock_export_options: MagicMock) -> None:
        """Test that filename length is limited."""
        mock_export_options.filename_encoding = ""
        mock_export_options.filename_length = 10

        long_filename = "very_long_filename_that_exceeds_limit"
        result = sanitize_filename(long_filename)
        assert len(result) == 10
        assert result == long_filename[:10]

    @patch("confluence_markdown_exporter.utils.export.export_options")
    def test_complex_filename_sanitization(self, mock_export_options: MagicMock) -> None:
        """Test complex filename sanitization with multiple rules."""
        mock_export_options.filename_encoding = '" ":"_","?":"_",":":"_"'
        mock_export_options.filename_length = 50

        filename = "My Document: What? How?  . ."
        result = sanitize_filename(filename)
        # Character replacements happen first, then rstrip of spaces and dots
        assert result == "My_Document__What__How___._"


class TestSanitizeKey:
    """Test cases for sanitize_key function."""

    def test_basic_string(self) -> None:
        """Test sanitizing basic string."""
        result = sanitize_key("Test String")
        assert result == "test_string"

    def test_special_characters(self) -> None:
        """Test sanitizing string with special characters."""
        result = sanitize_key("Test-Key: With @ Special % Characters!")
        assert result == "test_key_with_special_characters"

    def test_multiple_underscores_collapse(self) -> None:
        """Test that multiple consecutive underscores are collapsed."""
        result = sanitize_key("test___multiple___underscores")
        assert result == "test_multiple_underscores"

    def test_trim_leading_trailing_underscores(self) -> None:
        """Test that leading and trailing underscores are trimmed."""
        result = sanitize_key("__test_key__")
        assert result == "test_key"

    def test_starts_with_number(self) -> None:
        """Test that string starting with number gets key_ prefix."""
        result = sanitize_key("123test")
        assert result == "key_123test"

    def test_starts_with_special_character(self) -> None:
        """Test that string starting with special character becomes valid after processing."""
        result = sanitize_key("@test")
        # "@test" -> "@test" (lowercase) -> "_test" (replace @) -> "test" (strip _)
        # Since "test" starts with 't' (a letter), no key_ prefix is added
        assert result == "test"

    def test_custom_connector(self) -> None:
        """Test using custom connector character."""
        result = sanitize_key("Test String", connector="-")
        assert result == "test-string"

    def test_already_valid_key(self) -> None:
        """Test that already valid key remains unchanged."""
        result = sanitize_key("valid_key")
        assert result == "valid_key"

    def test_empty_string(self) -> None:
        """Test sanitizing empty string."""
        result = sanitize_key("")
        assert result == "key_"

    def test_only_special_characters(self) -> None:
        """Test string with only special characters."""
        result = sanitize_key("@#$%")
        assert result == "key_"


class TestEscapeCharacterClass:
    """Test cases for escape_character_class function."""

    def test_escape_backslash(self) -> None:
        """Test escaping backslash character."""
        result = escape_character_class("\\")
        assert result == "\\\\"

    def test_escape_dash(self) -> None:
        """Test escaping dash character."""
        result = escape_character_class("-")
        assert result == "\\-"

    def test_escape_right_bracket(self) -> None:
        """Test escaping right bracket character."""
        result = escape_character_class("]")
        assert result == "\\]"

    def test_escape_caret(self) -> None:
        """Test escaping caret character."""
        result = escape_character_class("^")
        assert result == "\\^"

    def test_escape_multiple_characters(self) -> None:
        """Test escaping multiple special characters."""
        result = escape_character_class("\\-]^")
        assert result == "\\\\\\-\\]\\^"

    def test_no_special_characters(self) -> None:
        """Test string with no special characters."""
        result = escape_character_class("abc123")
        assert result == "abc123"

    def test_mixed_characters(self) -> None:
        """Test string with mix of special and normal characters."""
        result = escape_character_class("a-b]c^d\\e")
        assert result == "a\\-b\\]c\\^d\\\\e"

    def test_empty_string(self) -> None:
        """Test escaping empty string."""
        result = escape_character_class("")
        assert result == ""
