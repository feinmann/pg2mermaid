"""Data models representing PostgreSQL schema structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Column:
    """Represents a table column."""

    name: str
    data_type: str
    nullable: bool = True
    default: str | None = None
    is_primary_key: bool = False
    is_foreign_key: bool = False

    def __repr__(self) -> str:
        flags = []
        if self.is_primary_key:
            flags.append("PK")
        if self.is_foreign_key:
            flags.append("FK")
        flag_str = f" [{','.join(flags)}]" if flags else ""
        return f"Column({self.name}: {self.data_type}{flag_str})"


@dataclass
class ForeignKey:
    """Represents a foreign key constraint."""

    columns: list[str]
    ref_schema: str | None
    ref_table: str
    ref_columns: list[str]
    constraint_name: str | None = None
    on_delete: str | None = None
    on_update: str | None = None

    @property
    def ref_qualified_name(self) -> str:
        """Return fully qualified reference table name."""
        if self.ref_schema:
            return f"{self.ref_schema}.{self.ref_table}"
        return self.ref_table

    def __repr__(self) -> str:
        cols = ", ".join(self.columns)
        refs = ", ".join(self.ref_columns)
        return f"FK({cols} -> {self.ref_qualified_name}({refs}))"


@dataclass
class Table:
    """Represents a database table."""

    name: str
    schema: str
    columns: list[Column] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    unique_constraints: list[list[str]] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        """Return fully qualified table name (schema.table)."""
        return f"{self.schema}.{self.name}"

    def get_column(self, name: str) -> Column | None:
        """Get a column by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def add_column(self, column: Column) -> None:
        """Add a column to the table."""
        self.columns.append(column)

    def set_primary_key(self, columns: list[str]) -> None:
        """Set the primary key columns and update column flags."""
        self.primary_key = columns
        for col_name in columns:
            col = self.get_column(col_name)
            if col:
                col.is_primary_key = True

    def add_foreign_key(self, fk: ForeignKey) -> None:
        """Add a foreign key and update column flags."""
        self.foreign_keys.append(fk)
        for col_name in fk.columns:
            col = self.get_column(col_name)
            if col:
                col.is_foreign_key = True

    def __repr__(self) -> str:
        return f"Table({self.qualified_name}, {len(self.columns)} columns)"


@dataclass
class Schema:
    """Represents a database schema (namespace)."""

    name: str
    tables: dict[str, Table] = field(default_factory=dict)

    def add_table(self, table: Table) -> None:
        """Add a table to the schema."""
        self.tables[table.name] = table

    def get_table(self, name: str) -> Table | None:
        """Get a table by name."""
        return self.tables.get(name)

    def __repr__(self) -> str:
        return f"Schema({self.name}, {len(self.tables)} tables)"


@dataclass
class Database:
    """Represents the entire database structure."""

    schemas: dict[str, Schema] = field(default_factory=dict)

    def add_schema(self, schema: Schema) -> None:
        """Add a schema to the database."""
        self.schemas[schema.name] = schema

    def get_schema(self, name: str) -> Schema:
        """Get or create a schema by name."""
        if name not in self.schemas:
            self.schemas[name] = Schema(name=name)
        return self.schemas[name]

    def get_table(self, schema: str, name: str) -> Table | None:
        """Get a table by schema and name."""
        schema_obj = self.schemas.get(schema)
        if schema_obj:
            return schema_obj.get_table(name)
        return None

    def add_table(self, table: Table) -> None:
        """Add a table, creating the schema if needed."""
        schema = self.get_schema(table.schema)
        schema.add_table(table)

    def all_tables(self) -> Iterator[Table]:
        """Iterate over all tables in all schemas."""
        for schema in self.schemas.values():
            yield from schema.tables.values()

    def table_count(self) -> int:
        """Return total number of tables."""
        return sum(len(s.tables) for s in self.schemas.values())

    def find_table_by_name(self, name: str, preferred_schema: str | None = None) -> Table | None:
        """
        Find a table by name, optionally preferring a specific schema.

        Useful for resolving foreign key references that may not include schema.
        """
        # Try preferred schema first
        if preferred_schema:
            table = self.get_table(preferred_schema, name)
            if table:
                return table

        # Search all schemas
        for schema in self.schemas.values():
            if name in schema.tables:
                return schema.tables[name]

        return None

    def __repr__(self) -> str:
        return f"Database({len(self.schemas)} schemas, {self.table_count()} tables)"
