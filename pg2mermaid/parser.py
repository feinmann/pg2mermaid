"""SQL parser for PostgreSQL dump files."""

from __future__ import annotations

import re
from typing import Iterator

from pg2mermaid.models import Column, Database, ForeignKey, Table


# Default schema when none specified
DEFAULT_SCHEMA = "public"


def parse_sql(sql: str) -> Database:
    """
    Parse a PostgreSQL dump and return a Database object.

    Args:
        sql: The SQL content from a pg_dump file.

    Returns:
        Database object containing all parsed schemas and tables.
    """
    db = Database()

    # Parse CREATE TABLE statements
    for table in _parse_create_tables(sql):
        db.add_table(table)

    # Parse ALTER TABLE statements for additional constraints
    _parse_alter_tables(sql, db)

    return db


def _parse_create_tables(sql: str) -> Iterator[Table]:
    """Extract and parse all CREATE TABLE statements."""
    # Pattern to match CREATE TABLE statements
    # Handles: CREATE TABLE, CREATE TABLE IF NOT EXISTS, CREATE UNLOGGED TABLE
    pattern = re.compile(
        r"CREATE\s+(?:UNLOGGED\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"([^\s(]+)\s*\(\s*"
        r"(.*?)"
        r"\)\s*;",
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(sql):
        table_name = match.group(1)
        body = match.group(2)

        table = _parse_table(table_name, body)
        if table:
            yield table


def _parse_table(qualified_name: str, body: str) -> Table | None:
    """Parse a single CREATE TABLE statement body."""
    schema, name = _parse_qualified_name(qualified_name)

    table = Table(name=name, schema=schema)

    # Split body into column/constraint definitions
    definitions = _split_definitions(body)

    table_constraints: list[str] = []

    for definition in definitions:
        definition = definition.strip()
        if not definition:
            continue

        # Check if this is a table-level constraint
        if _is_table_constraint(definition):
            table_constraints.append(definition)
        else:
            # It's a column definition
            column = _parse_column(definition)
            if column:
                table.add_column(column)

    # Process table-level constraints
    for constraint in table_constraints:
        _apply_table_constraint(table, constraint)

    return table


def _parse_qualified_name(name: str) -> tuple[str, str]:
    """
    Parse a potentially schema-qualified name.

    Returns (schema, table_name).
    """
    # Remove quotes if present
    name = name.replace('"', "")

    if "." in name:
        parts = name.split(".", 1)
        return parts[0], parts[1]

    return DEFAULT_SCHEMA, name


def _split_definitions(body: str) -> list[str]:
    """
    Split table body into individual column/constraint definitions.

    Handles nested parentheses (e.g., in CHECK constraints, type parameters).
    """
    definitions: list[str] = []
    current: list[str] = []
    paren_depth = 0
    in_string = False
    string_char = ""

    i = 0
    while i < len(body):
        char = body[i]

        # Handle string literals
        if char in ("'", '"') and (i == 0 or body[i - 1] != "\\"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False

        if not in_string:
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            elif char == "," and paren_depth == 0:
                definitions.append("".join(current).strip())
                current = []
                i += 1
                continue

        current.append(char)
        i += 1

    # Don't forget the last definition
    if current:
        definitions.append("".join(current).strip())

    return definitions


def _is_table_constraint(definition: str) -> bool:
    """Check if a definition is a table-level constraint (not a column)."""
    upper = definition.upper().lstrip()
    constraint_keywords = (
        "PRIMARY KEY",
        "FOREIGN KEY",
        "UNIQUE",
        "CHECK",
        "EXCLUDE",
        "CONSTRAINT",
    )
    return any(upper.startswith(kw) for kw in constraint_keywords)


def _parse_column(definition: str) -> Column | None:
    """Parse a column definition."""
    # Remove leading/trailing whitespace
    definition = definition.strip()

    if not definition:
        return None

    # Pattern to extract column name and type
    # Handles: name type, "name" type, name type(params), name type[]
    pattern = re.compile(
        r'^"?([^"\s]+)"?\s+'  # Column name (possibly quoted)
        r"(.+)$",  # Everything else (type + constraints)
        re.IGNORECASE | re.DOTALL,
    )

    match = pattern.match(definition)
    if not match:
        return None

    name = match.group(1)
    rest = match.group(2).strip()

    # Extract the data type and constraints
    data_type, constraints = _extract_type_and_constraints(rest)

    if not data_type:
        return None

    # Normalize the data type
    data_type = _normalize_type(data_type)

    # Parse constraints
    is_pk = "PRIMARY KEY" in constraints.upper()
    is_nullable = "NOT NULL" not in constraints.upper()
    default = _extract_default(constraints)

    return Column(
        name=name,
        data_type=data_type,
        nullable=is_nullable,
        default=default,
        is_primary_key=is_pk,
        is_foreign_key=False,  # Will be set later when parsing FKs
    )


def _extract_type_and_constraints(rest: str) -> tuple[str, str]:
    """
    Separate the data type from constraints in a column definition.

    Returns (data_type, constraints_string).
    """
    # Common constraint keywords that signal end of type
    constraint_keywords = [
        "NOT NULL",
        "NULL",
        "DEFAULT",
        "PRIMARY KEY",
        "UNIQUE",
        "REFERENCES",
        "CHECK",
        "COLLATE",
        "CONSTRAINT",
        "GENERATED",
    ]

    upper = rest.upper()
    min_pos = len(rest)

    for keyword in constraint_keywords:
        # Look for keyword as a whole word
        pattern = re.compile(r"\b" + keyword + r"\b", re.IGNORECASE)
        match = pattern.search(rest)
        if match and match.start() < min_pos:
            min_pos = match.start()

    data_type = rest[:min_pos].strip()
    constraints = rest[min_pos:].strip()

    return data_type, constraints


def _normalize_type(data_type: str) -> str:
    """Normalize PostgreSQL data type to a cleaner form."""
    # Remove extra whitespace
    data_type = " ".join(data_type.split())

    # Common type mappings for display
    type_map = {
        "CHARACTER VARYING": "varchar",
        "CHARACTER": "char",
        "INTEGER": "int",
        "BIGINT": "bigint",
        "SMALLINT": "smallint",
        "BOOLEAN": "bool",
        "DOUBLE PRECISION": "float8",
        "REAL": "float4",
        "TIMESTAMP WITHOUT TIME ZONE": "timestamp",
        "TIMESTAMP WITH TIME ZONE": "timestamptz",
        "TIME WITHOUT TIME ZONE": "time",
        "TIME WITH TIME ZONE": "timetz",
    }

    upper = data_type.upper()
    for long_form, short_form in type_map.items():
        if upper.startswith(long_form):
            # Preserve any parameters like (255)
            suffix = data_type[len(long_form) :]
            return short_form + suffix

    return data_type.lower()


def _extract_default(constraints: str) -> str | None:
    """Extract DEFAULT value from constraints string."""
    pattern = re.compile(
        r"DEFAULT\s+("
        r"'(?:[^']|'')*'"  # String literal
        r"|"
        r'"(?:[^"]|"")*"'  # Double-quoted string
        r"|"
        r"\([^)]+\)"  # Expression in parentheses
        r"|"
        r"[^\s,)]+"  # Simple value
        r")",
        re.IGNORECASE,
    )

    match = pattern.search(constraints)
    if match:
        return match.group(1)

    return None


def _apply_table_constraint(table: Table, constraint: str) -> None:
    """Apply a table-level constraint to a table."""
    upper = constraint.upper()

    if "PRIMARY KEY" in upper:
        _apply_primary_key_constraint(table, constraint)
    elif "FOREIGN KEY" in upper:
        _apply_foreign_key_constraint(table, constraint)
    elif "UNIQUE" in upper:
        _apply_unique_constraint(table, constraint)


def _apply_primary_key_constraint(table: Table, constraint: str) -> None:
    """Extract and apply PRIMARY KEY constraint."""
    # Pattern: PRIMARY KEY (col1, col2, ...)
    pattern = re.compile(
        r"PRIMARY\s+KEY\s*\(([^)]+)\)",
        re.IGNORECASE,
    )

    match = pattern.search(constraint)
    if match:
        columns = _parse_column_list(match.group(1))
        table.set_primary_key(columns)


def _apply_foreign_key_constraint(table: Table, constraint: str) -> None:
    """Extract and apply FOREIGN KEY constraint."""
    # Pattern: [CONSTRAINT name] FOREIGN KEY (cols) REFERENCES table(cols) [ON DELETE/UPDATE]
    pattern = re.compile(
        r"(?:CONSTRAINT\s+\"?(\w+)\"?\s+)?"
        r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*"
        r"REFERENCES\s+([^\s(]+)\s*\(([^)]+)\)"
        r"(?:\s+ON\s+DELETE\s+(\w+(?:\s+\w+)?))?"
        r"(?:\s+ON\s+UPDATE\s+(\w+(?:\s+\w+)?))?",
        re.IGNORECASE,
    )

    match = pattern.search(constraint)
    if match:
        constraint_name = match.group(1)
        columns = _parse_column_list(match.group(2))
        ref_table = match.group(3).replace('"', "")
        ref_columns = _parse_column_list(match.group(4))
        on_delete = match.group(5)
        on_update = match.group(6)

        ref_schema, ref_name = _parse_qualified_name(ref_table)

        fk = ForeignKey(
            columns=columns,
            ref_schema=ref_schema if ref_schema != DEFAULT_SCHEMA else None,
            ref_table=ref_name,
            ref_columns=ref_columns,
            constraint_name=constraint_name,
            on_delete=on_delete,
            on_update=on_update,
        )

        table.add_foreign_key(fk)


def _apply_unique_constraint(table: Table, constraint: str) -> None:
    """Extract and apply UNIQUE constraint."""
    # Pattern: UNIQUE (col1, col2, ...)
    pattern = re.compile(
        r"UNIQUE\s*\(([^)]+)\)",
        re.IGNORECASE,
    )

    match = pattern.search(constraint)
    if match:
        columns = _parse_column_list(match.group(1))
        table.unique_constraints.append(columns)


def _parse_column_list(columns_str: str) -> list[str]:
    """Parse a comma-separated list of column names."""
    columns = []
    for col in columns_str.split(","):
        col = col.strip().replace('"', "")
        if col:
            columns.append(col)
    return columns


def _parse_alter_tables(sql: str, db: Database) -> None:
    """Parse ALTER TABLE statements for additional constraints."""
    # PRIMARY KEY
    pk_pattern = re.compile(
        r"ALTER\s+TABLE\s+(?:ONLY\s+)?([^\s]+)\s+"
        r"ADD\s+CONSTRAINT\s+[^\s]+\s+"
        r"PRIMARY\s+KEY\s*\(([^)]+)\)",
        re.IGNORECASE,
    )

    for match in pk_pattern.finditer(sql):
        table_name = match.group(1).replace('"', "")
        columns = _parse_column_list(match.group(2))

        schema, name = _parse_qualified_name(table_name)
        table = db.get_table(schema, name)
        if table:
            table.set_primary_key(columns)

    # FOREIGN KEY
    fk_pattern = re.compile(
        r"ALTER\s+TABLE\s+(?:ONLY\s+)?([^\s]+)\s+"
        r"ADD\s+CONSTRAINT\s+\"?(\w+)\"?\s+"
        r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*"
        r"REFERENCES\s+([^\s(]+)\s*\(([^)]+)\)"
        r"(?:\s+ON\s+DELETE\s+(\w+(?:\s+\w+)?))?"
        r"(?:\s+ON\s+UPDATE\s+(\w+(?:\s+\w+)?))?",
        re.IGNORECASE,
    )

    for match in fk_pattern.finditer(sql):
        table_name = match.group(1).replace('"', "")
        constraint_name = match.group(2)
        columns = _parse_column_list(match.group(3))
        ref_table = match.group(4).replace('"', "")
        ref_columns = _parse_column_list(match.group(5))
        on_delete = match.group(6)
        on_update = match.group(7)

        schema, name = _parse_qualified_name(table_name)
        table = db.get_table(schema, name)
        if table:
            ref_schema, ref_name = _parse_qualified_name(ref_table)
            fk = ForeignKey(
                columns=columns,
                ref_schema=ref_schema if ref_schema != DEFAULT_SCHEMA else None,
                ref_table=ref_name,
                ref_columns=ref_columns,
                constraint_name=constraint_name,
                on_delete=on_delete,
                on_update=on_update,
            )
            table.add_foreign_key(fk)

    # UNIQUE
    unique_pattern = re.compile(
        r"ALTER\s+TABLE\s+(?:ONLY\s+)?([^\s]+)\s+"
        r"ADD\s+CONSTRAINT\s+[^\s]+\s+"
        r"UNIQUE\s*\(([^)]+)\)",
        re.IGNORECASE,
    )

    for match in unique_pattern.finditer(sql):
        table_name = match.group(1).replace('"', "")
        columns = _parse_column_list(match.group(2))

        schema, name = _parse_qualified_name(table_name)
        table = db.get_table(schema, name)
        if table:
            table.unique_constraints.append(columns)
