"""Tests for the CLI interface."""

import json
from pathlib import Path

from pg2mermaid.cli import main


FIXTURE_PATH = str(Path(__file__).parent / "fixtures" / "simple.sql")


class TestCLIBasic:
    """Test basic CLI functionality."""

    def test_convert_file(self) -> None:
        result = main([FIXTURE_PATH])
        assert result == 0

    def test_output_to_file(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "-o", str(out)])
        assert result == 0
        assert out.exists()
        content = out.read_text()
        assert "erDiagram" in content

    def test_missing_file(self) -> None:
        result = main(["nonexistent.sql"])
        assert result == 1

    def test_empty_input(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.sql"
        empty.write_text("")
        result = main([str(empty)])
        assert result == 1

    def test_version(self, capsys) -> None:  # type: ignore[no-untyped-def]
        try:
            main(["--version"])
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "pg2mermaid" in captured.out


class TestCLIOutputModes:
    """Test CLI output mode options."""

    def test_compact_mode(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--compact", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        # Compact should only have PK/FK columns
        assert "serial id PK" in content
        # Non-PK/FK columns should not appear in compact
        assert "text body" not in content

    def test_full_mode(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--full", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        assert "erDiagram" in content


class TestCLIFormats:
    """Test CLI format options."""

    def test_markdown_format(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--format", "markdown", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        assert content.startswith("```mermaid")
        assert content.strip().endswith("```")

    def test_json_format(self, tmp_path: Path) -> None:
        out = tmp_path / "output.json"
        result = main([FIXTURE_PATH, "--format", "json", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        data = json.loads(content)
        assert "schemas" in data
        assert "relationships" in data


class TestCLIFiltering:
    """Test CLI filtering options."""

    def test_exclude_tables(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--exclude", "comments", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        assert "comments" not in content
        assert "users" in content

    def test_include_tables(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--table", "users", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        assert "users" in content
        # Other tables should not appear in table definitions
        lines = content.split("\n")
        table_def_lines = [l for l in lines if "{" in l and "users" not in l]
        assert len(table_def_lines) == 0

    def test_connected_only(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--connected-only", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        assert "erDiagram" in content


class TestCLILayout:
    """Test CLI layout options."""

    def test_max_columns(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--max-columns", "2", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        assert "more columns" in content

    def test_group_by_schema(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--group-by-schema", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        assert "Schema: public" in content

    def test_title(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "--title", "My DB", "-o", str(out)])
        assert result == 0
        content = out.read_text()
        assert "title: My DB" in content

    def test_verbose(self, tmp_path: Path) -> None:
        out = tmp_path / "output.md"
        result = main([FIXTURE_PATH, "-v", "-o", str(out)])
        assert result == 0


class TestCLIImageExport:
    """Test image export argument validation."""

    def test_svg_requires_output_file(self) -> None:
        result = main([FIXTURE_PATH, "--svg"])
        assert result == 1

    def test_png_requires_output_file(self) -> None:
        result = main([FIXTURE_PATH, "--png"])
        assert result == 1

    def test_pdf_requires_output_file(self) -> None:
        result = main([FIXTURE_PATH, "--pdf"])
        assert result == 1
