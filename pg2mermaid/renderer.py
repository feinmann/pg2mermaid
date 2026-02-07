"""Mermaid ER diagram renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pg2mermaid.models import Column, Database, ForeignKey, Table


class OutputMode(Enum):
    """Output detail level."""

    COMPACT = "compact"  # Only PK/FK columns
    NORMAL = "normal"  # All columns, simplified types
    FULL = "full"  # All columns with full type info


class OutputFormat(Enum):
    """Output format."""

    MERMAID = "mermaid"  # Raw mermaid code
    MARKDOWN = "markdown"  # Wrapped in markdown code block


@dataclass
class RenderOptions:
    """Options for rendering the diagram."""

    mode: OutputMode = OutputMode.NORMAL
    format: OutputFormat = OutputFormat.MERMAID
    include_schemas: list[str] | None = None
    exclude_schemas: list[str] | None = None
    include_tables: list[str] | None = None
    exclude_tables: list[str] | None = None
    connected_only: bool = False
    show_schema_prefix: bool = True
    max_columns: int = 20  # Max columns to show per table (0 = unlimited)
    group_by_schema: bool = False
    title: str | None = None


def render_mermaid(db: Database, options: RenderOptions | None = None) -> str:
    """
    Render a Database object as a Mermaid ER diagram.

    Args:
        db: The parsed database structure.
        options: Rendering options.

    Returns:
        Mermaid ER diagram as a string.
    """
    if options is None:
        options = RenderOptions()

    # Filter tables
    tables = list(_filter_tables(db, options))

    if not tables:
        return _wrap_output("erDiagram\n    %% No tables to display", options)

    # If connected_only, filter to tables with relationships
    if options.connected_only:
        tables = _filter_connected_tables(tables, db)

    if not tables:
        return _wrap_output("erDiagram\n    %% No connected tables to display", options)

    # Build the diagram
    lines: list[str] = []

    # Add title if specified
    if options.title:
        lines.append(f"---")
        lines.append(f"title: {options.title}")
        lines.append(f"---")

    lines.append("erDiagram")

    if options.group_by_schema:
        # Group tables by schema
        schemas: dict[str, list[Table]] = {}
        for table in tables:
            schemas.setdefault(table.schema, []).append(table)

        for schema_name, schema_tables in sorted(schemas.items()):
            lines.append(f"    %% Schema: {schema_name}")
            for table in sorted(schema_tables, key=lambda t: t.name):
                lines.extend(_render_table(table, options))
            lines.append("")
    else:
        # Render all tables
        for table in sorted(tables, key=lambda t: (t.schema, t.name)):
            lines.extend(_render_table(table, options))

    # Render relationships
    lines.append("")
    lines.append("    %% Relationships")
    relationships = _collect_relationships(tables, db, options)
    for rel in relationships:
        lines.append(f"    {rel}")

    result = "\n".join(lines)
    return _wrap_output(result, options)


def _wrap_output(content: str, options: RenderOptions) -> str:
    """Wrap output in markdown code block if requested."""
    if options.format == OutputFormat.MARKDOWN:
        return f"```mermaid\n{content}\n```"
    return content


def _filter_tables(db: Database, options: RenderOptions) -> list[Table]:
    """Filter tables based on options."""
    tables: list[Table] = []

    for table in db.all_tables():
        # Schema filter
        if options.include_schemas:
            if table.schema not in options.include_schemas:
                continue
        if options.exclude_schemas:
            if table.schema in options.exclude_schemas:
                continue

        # Table name filter
        if options.include_tables:
            if not _matches_any_pattern(table.name, options.include_tables):
                continue
        if options.exclude_tables:
            if _matches_any_pattern(table.name, options.exclude_tables):
                continue

        tables.append(table)

    return tables


def _matches_any_pattern(name: str, patterns: list[str]) -> bool:
    """Check if name matches any of the glob-like patterns."""
    for pattern in patterns:
        if _matches_pattern(name, pattern):
            return True
    return False


def _matches_pattern(name: str, pattern: str) -> bool:
    """Check if name matches a glob-like pattern (supports * wildcard)."""
    # Convert glob pattern to regex
    regex = pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
    return bool(re.match(f"^{regex}$", name, re.IGNORECASE))


def _filter_connected_tables(tables: list[Table], db: Database) -> list[Table]:
    """Filter to only tables that have relationships (FK in or out)."""
    # Collect all table names that are involved in relationships
    connected_names: set[str] = set()

    for table in tables:
        if table.foreign_keys:
            # This table has outgoing FKs
            connected_names.add(table.qualified_name)
            for fk in table.foreign_keys:
                # Add referenced table
                if fk.ref_schema:
                    connected_names.add(f"{fk.ref_schema}.{fk.ref_table}")
                else:
                    # Try to find the referenced table
                    ref_table = db.find_table_by_name(fk.ref_table, table.schema)
                    if ref_table:
                        connected_names.add(ref_table.qualified_name)

    return [t for t in tables if t.qualified_name in connected_names]


def _render_table(table: Table, options: RenderOptions) -> list[str]:
    """Render a single table definition."""
    lines: list[str] = []

    # Table name (sanitize for Mermaid)
    table_id = _sanitize_identifier(table, options)

    lines.append(f"    {table_id} {{")

    # Determine which columns to show
    columns = _select_columns(table, options)

    for col in columns:
        col_line = _render_column(col, options)
        lines.append(f"        {col_line}")

    # Show indicator if columns were truncated
    if options.max_columns > 0 and len(table.columns) > options.max_columns:
        remaining = len(table.columns) - options.max_columns
        lines.append(f"        %% ... {remaining} more columns")

    lines.append("    }")

    return lines


def _select_columns(table: Table, options: RenderOptions) -> list[Column]:
    """Select which columns to include based on mode."""
    if options.mode == OutputMode.COMPACT:
        # Only PK and FK columns
        return [c for c in table.columns if c.is_primary_key or c.is_foreign_key]

    # For normal and full modes, respect max_columns
    if options.max_columns > 0 and len(table.columns) > options.max_columns:
        # Prioritize PK/FK columns
        pk_fk = [c for c in table.columns if c.is_primary_key or c.is_foreign_key]
        other = [c for c in table.columns if not c.is_primary_key and not c.is_foreign_key]

        # Take all PK/FK, then fill remaining slots with other columns
        remaining_slots = max(0, options.max_columns - len(pk_fk))
        return pk_fk + other[:remaining_slots]

    return table.columns


def _render_column(col: Column, options: RenderOptions) -> str:
    """Render a single column definition."""
    # Simplify type for normal mode
    if options.mode == OutputMode.FULL:
        type_str = col.data_type
    else:
        type_str = _simplify_type(col.data_type)

    # Mermaid doesn't allow spaces in type, replace with underscore
    type_str = type_str.replace(" ", "_")

    # Build flags
    flags: list[str] = []
    if col.is_primary_key:
        flags.append("PK")
    if col.is_foreign_key:
        flags.append("FK")

    # Sanitize column name
    col_name = _sanitize_name(col.name)

    if flags:
        return f"{type_str} {col_name} {','.join(flags)}"
    return f"{type_str} {col_name}"


def _simplify_type(data_type: str) -> str:
    """Simplify data type for cleaner output."""
    # Remove size specifications for common types
    simplified = re.sub(r"\(\d+(?:,\s*\d+)?\)", "", data_type)

    # Common simplifications
    type_map = {
        "character varying": "varchar",
        "character": "char",
        "timestamp without time zone": "timestamp",
        "timestamp with time zone": "timestamptz",
        "time without time zone": "time",
        "time with time zone": "timetz",
        "double precision": "float8",
    }

    lower = simplified.lower()
    for long_form, short_form in type_map.items():
        if lower.startswith(long_form):
            return short_form

    return simplified


def _sanitize_identifier(table: Table, options: RenderOptions) -> str:
    """Create a valid Mermaid identifier for a table."""
    if options.show_schema_prefix and table.schema != "public":
        name = f"{table.schema}__{table.name}"
    else:
        name = table.name

    return _sanitize_name(name)


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use in Mermaid diagrams."""
    # Replace problematic characters
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    # Ensure doesn't start with a number
    if name and name[0].isdigit():
        name = "_" + name

    return name


def _collect_relationships(
    tables: list[Table], db: Database, options: RenderOptions
) -> list[str]:
    """Collect all relationships between tables."""
    relationships: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    # Build a set of table names we're showing
    shown_tables = {t.qualified_name for t in tables}
    shown_names = {t.name for t in tables}

    for table in tables:
        source_id = _sanitize_identifier(table, options)

        for fk in table.foreign_keys:
            # Find target table
            if fk.ref_schema:
                target_qualified = f"{fk.ref_schema}.{fk.ref_table}"
            else:
                # Try to find in same schema first
                ref_table = db.find_table_by_name(fk.ref_table, table.schema)
                if ref_table:
                    target_qualified = ref_table.qualified_name
                else:
                    target_qualified = f"{table.schema}.{fk.ref_table}"

            # Only show relationship if target is in our diagram
            if target_qualified not in shown_tables and fk.ref_table not in shown_names:
                continue

            # Get target table for proper naming
            target_table = db.find_table_by_name(fk.ref_table, fk.ref_schema or table.schema)
            if target_table:
                target_id = _sanitize_identifier(target_table, options)
            else:
                target_id = _sanitize_name(fk.ref_table)

            # Build relationship string
            # For now, assume one-to-many (most common)
            # target ||--o{ source : "fk_name"
            label = fk.columns[0] if len(fk.columns) == 1 else ",".join(fk.columns)

            # Avoid duplicate relationships (include label to allow multiple FKs between same tables)
            rel_key = (source_id, target_id, label)
            if rel_key in seen:
                continue
            seen.add(rel_key)

            relationships.append(f'{target_id} ||--o{{ {source_id} : "{label}"')

    return relationships


def render_json(db: Database, options: RenderOptions | None = None) -> str:
    """
    Render a Database object as JSON for programmatic use.

    Args:
        db: The parsed database structure.
        options: Rendering options (for filtering).

    Returns:
        JSON string representing the schema.
    """
    import json

    if options is None:
        options = RenderOptions()

    tables = list(_filter_tables(db, options))

    result: dict[str, Any] = {
        "schemas": {},
        "relationships": [],
    }

    for table in tables:
        schema_name = table.schema
        if schema_name not in result["schemas"]:
            result["schemas"][schema_name] = {"tables": {}}

        result["schemas"][schema_name]["tables"][table.name] = {
            "columns": [
                {
                    "name": c.name,
                    "type": c.data_type,
                    "nullable": c.nullable,
                    "is_primary_key": c.is_primary_key,
                    "is_foreign_key": c.is_foreign_key,
                }
                for c in table.columns
            ],
            "primary_key": table.primary_key,
            "foreign_keys": [
                {
                    "columns": fk.columns,
                    "ref_table": fk.ref_qualified_name,
                    "ref_columns": fk.ref_columns,
                }
                for fk in table.foreign_keys
            ],
        }

        for fk in table.foreign_keys:
            result["relationships"].append(
                {
                    "from_table": table.qualified_name,
                    "from_columns": fk.columns,
                    "to_table": fk.ref_qualified_name,
                    "to_columns": fk.ref_columns,
                }
            )

    return json.dumps(result, indent=2)
