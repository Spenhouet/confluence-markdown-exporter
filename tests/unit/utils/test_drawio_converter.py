"""Tests for DrawIO converter functionality."""

from pathlib import Path

from confluence_markdown_exporter.utils.drawio_converter import extract_mermaid_data
from confluence_markdown_exporter.utils.drawio_converter import format_mermaid_markdown
from confluence_markdown_exporter.utils.drawio_converter import load_and_parse_drawio
from confluence_markdown_exporter.utils.drawio_converter import load_drawio_file
from confluence_markdown_exporter.utils.drawio_converter import parse_mermaid_json


class TestLoadDrawioFile:
    """Test DrawIO file loading."""

    def test_load_existing_file(self, tmp_path: Path) -> None:
        """Test loading an existing DrawIO file."""
        test_content = "<mxfile><diagram>test</diagram></mxfile>"
        test_file = tmp_path / "test.drawio"
        test_file.write_text(test_content)

        result = load_drawio_file(test_file)
        assert result == test_content

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading a nonexistent file returns None."""
        nonexistent = tmp_path / "nonexistent.drawio"
        result = load_drawio_file(nonexistent)
        assert result is None


class TestExtractMermaidData:
    """Test mermaid data extraction from XML."""

    def test_extract_valid_mermaid_data(self) -> None:
        """Test extracting valid mermaid data."""
        # XML parser preserves case, so use UserObject and mermaidData
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<mxfile>
  <diagram>
    <mxGraphModel>
      <root>
        <UserObject mermaidData='{"data": "graph TB\\n  A --> B"}' />
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""
        result = extract_mermaid_data(xml_content)
        assert result is not None
        assert "graph TB" in result

    def test_extract_no_mermaid_data(self) -> None:
        """Test extraction when no mermaid data exists."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<mxfile>
  <diagram>
    <mxGraphModel>
      <root>
        <UserObject />
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""
        result = extract_mermaid_data(xml_content)
        assert result is None

    def test_extract_invalid_xml(self) -> None:
        """Test extraction with invalid XML returns None."""
        xml_content = "<invalid>xml"
        result = extract_mermaid_data(xml_content)
        assert result is None


class TestParseMermaidJson:
    """Test mermaid JSON parsing."""

    def test_parse_json_with_data_field(self) -> None:
        """Test parsing JSON with 'data' field."""
        json_data = '{"data": "graph TB\\n  A --> B"}'
        result = parse_mermaid_json(json_data)
        assert result == "graph TB\n  A --> B"

    def test_parse_plain_diagram(self) -> None:
        """Test parsing plain diagram string."""
        diagram = "graph TB\n  A --> B"
        result = parse_mermaid_json(diagram)
        assert result == diagram

    def test_parse_malformed_json(self) -> None:
        """Test parsing malformed JSON returns input as-is."""
        malformed = '{"incomplete": '
        result = parse_mermaid_json(malformed)
        assert result == malformed


class TestFormatMermaidMarkdown:
    """Test mermaid markdown formatting."""

    def test_format_diagram(self) -> None:
        """Test formatting a diagram as markdown."""
        diagram = "graph TB\n  A --> B"
        result = format_mermaid_markdown(diagram)
        assert result == "```mermaid\ngraph TB\n  A --> B\n```"


class TestLoadAndParseDrawio:
    """Integration tests for full DrawIO parsing."""

    def test_full_pipeline(self, tmp_path: Path) -> None:
        """Test full pipeline from file to markdown."""
        # XML parser preserves case, so use UserObject and mermaidData
        mermaid_data = '{"data": "graph TB\\n    A[Start]\\n    B[End]\\n    A --> B"}'
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<mxfile>
  <diagram>
    <mxGraphModel>
      <root>
        <UserObject mermaidData='{mermaid_data}' />
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""
        test_file = tmp_path / "test.drawio"
        test_file.write_text(xml_content)

        result = load_and_parse_drawio(test_file)
        assert result is not None
        assert "```mermaid" in result
        assert "graph TB" in result
        assert "A[Start]" in result
        assert "B[End]" in result

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Test with nonexistent file returns None."""
        result = load_and_parse_drawio(tmp_path / "nonexistent.drawio")
        assert result is None

    def test_file_without_mermaid_data(self, tmp_path: Path) -> None:
        """Test file without mermaid data returns None."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<mxfile>
  <diagram>
    <mxGraphModel>
      <root>
        <mxCell />
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""
        test_file = tmp_path / "test.drawio"
        test_file.write_text(xml_content)

        result = load_and_parse_drawio(test_file)
        assert result is None
