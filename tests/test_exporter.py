"""Tests for SVG foreignObject to text conversion."""

import re
from pathlib import Path

from pg2mermaid.exporter import _convert_foreignobjects_to_text

FIXTURES = Path(__file__).parent / "fixtures"


class TestConvertForeignObjectsToText:
    """Test _convert_foreignobjects_to_text replaces foreignObject with SVG text."""

    def test_all_foreignobjects_removed(self) -> None:
        """No <foreignObject> elements remain after conversion."""
        for svg_file in FIXTURES.glob("*.svg"):
            svg = svg_file.read_bytes()
            result = _convert_foreignobjects_to_text(svg).decode("utf-8")
            assert "foreignObject" not in result, f"foreignObject remains in {svg_file.name}"

    def test_text_elements_created(self) -> None:
        """Converted SVG contains <text> elements with original content."""
        svg = (FIXTURES / "example3_minimal.svg").read_bytes()
        result = _convert_foreignobjects_to_text(svg).decode("utf-8")
        texts = re.findall(r"<text [^>]*>(.*?)</text>", result)
        assert "employees" in texts
        assert "id" in texts
        assert "PK" in texts
        assert "varchar" in texts
        assert "salary" in texts

    def test_empty_foreignobjects_removed(self) -> None:
        """Empty foreignObjects (width=0, height=0) are removed without creating text."""
        svg = (FIXTURES / "example3_minimal.svg").read_bytes()
        result = _convert_foreignobjects_to_text(svg).decode("utf-8")
        texts = re.findall(r"<text [^>]*>(.*?)</text>", result)
        assert "" not in texts, "Empty text element should not be created"

    def test_edge_labels_centered(self) -> None:
        """Edge labels use text-anchor=middle and correct font properties."""
        svg = (FIXTURES / "example1_simple_blog.svg").read_bytes()
        result = _convert_foreignobjects_to_text(svg).decode("utf-8")
        match = re.search(r"<text [^>]*>user_id</text>", result)
        assert match is not None, "Edge label 'user_id' not found"
        tag = match.group(0)
        assert 'text-anchor="middle"' in tag
        assert 'font-size="14px"' in tag
        assert 'fill="#9370DB"' in tag

    def test_node_labels_left_aligned(self) -> None:
        """Entity labels use default (start) alignment and correct font properties."""
        svg = (FIXTURES / "example3_minimal.svg").read_bytes()
        result = _convert_foreignobjects_to_text(svg).decode("utf-8")
        match = re.search(r"<text [^>]*>employees</text>", result)
        assert match is not None
        tag = match.group(0)
        assert 'text-anchor="middle"' not in tag
        assert 'font-size="16px"' in tag
        assert 'fill="#333"' in tag

    def test_font_family_included(self) -> None:
        """Text elements include the Mermaid font-family."""
        svg = (FIXTURES / "example3_minimal.svg").read_bytes()
        result = _convert_foreignobjects_to_text(svg).decode("utf-8")
        match = re.search(r"<text [^>]*>employees</text>", result)
        assert match is not None
        assert "trebuchet ms" in match.group(0)

    def test_multiple_edge_labels(self) -> None:
        """SVG with multiple edge labels converts all of them."""
        svg = (FIXTURES / "example2_ecommerce.svg").read_bytes()
        result = _convert_foreignobjects_to_text(svg).decode("utf-8")
        edge_texts = re.findall(r'text-anchor="middle"[^>]*>(.*?)</text>', result)
        assert "category_id" in edge_texts
        assert "parent_id" in edge_texts

    def test_preserves_non_text_svg_structure(self) -> None:
        """Conversion preserves SVG elements like paths, rects, markers."""
        svg = (FIXTURES / "example3_minimal.svg").read_bytes()
        result = _convert_foreignobjects_to_text(svg).decode("utf-8")
        assert "<svg " in result
        assert "<path " in result
        assert "<marker " in result
        assert "<style>" in result

    def test_idempotent(self) -> None:
        """Running conversion twice produces the same result."""
        svg = (FIXTURES / "example1_simple_blog.svg").read_bytes()
        first = _convert_foreignobjects_to_text(svg)
        second = _convert_foreignobjects_to_text(first)
        assert first == second

    def test_passthrough_without_foreignobject(self) -> None:
        """SVG without foreignObject passes through unchanged."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><text>hello</text></svg>'
        result = _convert_foreignobjects_to_text(svg)
        assert result == svg
