"""pg2mermaid - Convert PostgreSQL dump files to Mermaid ER diagrams."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pg2mermaid")
except PackageNotFoundError:
    __version__ = "0.1.0"

from pg2mermaid.models import Column, ForeignKey, Table, Schema, Database
from pg2mermaid.parser import parse_sql
from pg2mermaid.renderer import render_mermaid, render_json, RenderOptions, OutputMode, OutputFormat
from pg2mermaid.exporter import export_diagram, ExportFormat, ExportMethod, ExportError

__all__ = [
    # Models
    "Column",
    "ForeignKey",
    "Table",
    "Schema",
    "Database",
    # Parser
    "parse_sql",
    # Renderer
    "render_mermaid",
    "render_json",
    "RenderOptions",
    "OutputMode",
    "OutputFormat",
    # Exporter
    "export_diagram",
    "ExportFormat",
    "ExportMethod",
    "ExportError",
]
