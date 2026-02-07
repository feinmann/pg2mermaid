"""Tests for the Mermaid renderer."""

from pg2mermaid.models import Database
from pg2mermaid.parser import parse_sql
from pg2mermaid.renderer import (
    OutputFormat,
    OutputMode,
    RenderOptions,
    render_json,
    render_mermaid,
)


def _simple_db() -> Database:
    """Create a simple test database."""
    sql = """
    CREATE TABLE users (
        id serial PRIMARY KEY,
        email varchar(255) NOT NULL,
        name text
    );
    CREATE TABLE posts (
        id serial PRIMARY KEY,
        user_id integer NOT NULL,
        title text NOT NULL,
        body text
    );
    ALTER TABLE posts ADD CONSTRAINT posts_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id);
    """
    return parse_sql(sql)


class TestBasicRendering:
    """Test basic Mermaid rendering."""

    def test_renders_erdiagram(self) -> None:
        db = _simple_db()
        output = render_mermaid(db)
        assert output.startswith("erDiagram")

    def test_renders_table_names(self) -> None:
        db = _simple_db()
        output = render_mermaid(db)
        assert "users {" in output
        assert "posts {" in output

    def test_renders_columns(self) -> None:
        db = _simple_db()
        output = render_mermaid(db)
        assert "serial id PK" in output
        assert "int user_id FK" in output
        assert "text title" in output

    def test_renders_relationships(self) -> None:
        db = _simple_db()
        output = render_mermaid(db)
        assert "Relationships" in output
        assert 'users ||--o{ posts : "user_id"' in output

    def test_empty_database(self) -> None:
        db = parse_sql("")
        output = render_mermaid(db)
        assert "No tables to display" in output


class TestOutputModes:
    """Test different output modes."""

    def test_compact_mode_only_pk_fk(self) -> None:
        db = _simple_db()
        options = RenderOptions(mode=OutputMode.COMPACT)
        output = render_mermaid(db, options)
        # Posts in compact: should have id (PK) and user_id (FK) but not title or body
        assert "serial id PK" in output
        assert "int user_id FK" in output
        assert "text title" not in output
        assert "text body" not in output

    def test_normal_mode_simplified_types(self) -> None:
        db = parse_sql("""
        CREATE TABLE t (
            a CHARACTER VARYING(255),
            b INTEGER
        );
        """)
        options = RenderOptions(mode=OutputMode.NORMAL)
        output = render_mermaid(db, options)
        # Normal mode simplifies types (removes size params)
        assert "varchar a" in output

    def test_full_mode_complete_types(self) -> None:
        db = parse_sql("""
        CREATE TABLE t (
            a varchar(255),
            b integer
        );
        """)
        options = RenderOptions(mode=OutputMode.FULL)
        output = render_mermaid(db, options)
        assert "varchar(255) a" in output


class TestOutputFormats:
    """Test different output formats."""

    def test_mermaid_format(self) -> None:
        db = _simple_db()
        options = RenderOptions(format=OutputFormat.MERMAID)
        output = render_mermaid(db, options)
        assert not output.startswith("```")

    def test_markdown_format(self) -> None:
        db = _simple_db()
        options = RenderOptions(format=OutputFormat.MARKDOWN)
        output = render_mermaid(db, options)
        assert output.startswith("```mermaid")
        assert output.endswith("```")

    def test_json_format(self) -> None:
        import json

        db = _simple_db()
        output = render_json(db)
        data = json.loads(output)
        assert "schemas" in data
        assert "relationships" in data
        assert "public" in data["schemas"]
        assert "users" in data["schemas"]["public"]["tables"]
        assert "posts" in data["schemas"]["public"]["tables"]

    def test_json_includes_relationships(self) -> None:
        import json

        db = _simple_db()
        output = render_json(db)
        data = json.loads(output)
        assert len(data["relationships"]) == 1
        rel = data["relationships"][0]
        assert rel["from_table"] == "public.posts"
        assert rel["from_columns"] == ["user_id"]
        assert rel["to_columns"] == ["id"]

    def test_json_includes_column_metadata(self) -> None:
        import json

        db = _simple_db()
        output = render_json(db)
        data = json.loads(output)
        users_cols = data["schemas"]["public"]["tables"]["users"]["columns"]
        id_col = next(c for c in users_cols if c["name"] == "id")
        assert id_col["is_primary_key"] is True
        assert id_col["is_foreign_key"] is False


class TestFiltering:
    """Test schema and table filtering."""

    def _multi_schema_db(self) -> Database:
        sql = """
        CREATE TABLE public.users (id serial PRIMARY KEY);
        CREATE TABLE public.posts (id serial PRIMARY KEY);
        CREATE TABLE auth.sessions (id serial PRIMARY KEY);
        CREATE TABLE auth.tokens (id serial PRIMARY KEY);
        CREATE TABLE billing.invoices (id serial PRIMARY KEY);
        """
        return parse_sql(sql)

    def test_include_schema(self) -> None:
        db = self._multi_schema_db()
        options = RenderOptions(include_schemas=["auth"])
        output = render_mermaid(db, options)
        assert "sessions" in output
        assert "tokens" in output
        assert "users" not in output
        assert "invoices" not in output

    def test_exclude_schema(self) -> None:
        db = self._multi_schema_db()
        options = RenderOptions(exclude_schemas=["billing"])
        output = render_mermaid(db, options)
        assert "users" in output
        assert "sessions" in output
        assert "invoices" not in output

    def test_include_table_pattern(self) -> None:
        db = self._multi_schema_db()
        options = RenderOptions(include_tables=["user*"])
        output = render_mermaid(db, options)
        assert "users" in output
        assert "posts" not in output

    def test_exclude_table_pattern(self) -> None:
        db = self._multi_schema_db()
        options = RenderOptions(exclude_tables=["*s"])
        output = render_mermaid(db, options)
        # All tables ending in 's' should be excluded
        assert "users" not in output
        assert "posts" not in output

    def test_connected_only(self) -> None:
        sql = """
        CREATE TABLE users (id serial PRIMARY KEY);
        CREATE TABLE posts (id serial PRIMARY KEY, user_id integer);
        CREATE TABLE orphan (id serial PRIMARY KEY);
        ALTER TABLE posts ADD CONSTRAINT fk FOREIGN KEY (user_id) REFERENCES users(id);
        """
        db = parse_sql(sql)
        options = RenderOptions(connected_only=True)
        output = render_mermaid(db, options)
        assert "users" in output
        assert "posts" in output
        assert "orphan" not in output


class TestLayoutOptions:
    """Test layout-related options."""

    def test_max_columns(self) -> None:
        sql = """
        CREATE TABLE t (
            id serial PRIMARY KEY,
            a text, b text, c text, d text, e text
        );
        """
        db = parse_sql(sql)
        options = RenderOptions(max_columns=3)
        output = render_mermaid(db, options)
        # Should show PK first, then fill remaining
        assert "serial id PK" in output
        assert "more columns" in output

    def test_max_columns_zero_unlimited(self) -> None:
        sql = """
        CREATE TABLE t (
            a text, b text, c text, d text, e text,
            f text, g text, h text, i text, j text,
            k text, l text, m text, n text, o text,
            p text, q text, r text, s text, t text,
            u text
        );
        """
        db = parse_sql(sql)
        options = RenderOptions(max_columns=0)
        output = render_mermaid(db, options)
        assert "more columns" not in output

    def test_group_by_schema(self) -> None:
        sql = """
        CREATE TABLE public.users (id serial PRIMARY KEY);
        CREATE TABLE auth.sessions (id serial PRIMARY KEY);
        """
        db = parse_sql(sql)
        options = RenderOptions(group_by_schema=True)
        output = render_mermaid(db, options)
        assert "Schema: auth" in output
        assert "Schema: public" in output

    def test_no_schema_prefix(self) -> None:
        sql = """
        CREATE TABLE myschema.users (id serial PRIMARY KEY);
        """
        db = parse_sql(sql)
        # With prefix
        options_with = RenderOptions(show_schema_prefix=True)
        output_with = render_mermaid(db, options_with)
        assert "myschema__users" in output_with

        # Without prefix
        options_without = RenderOptions(show_schema_prefix=False)
        output_without = render_mermaid(db, options_without)
        assert "myschema__users" not in output_without
        assert "users {" in output_without

    def test_title(self) -> None:
        db = _simple_db()
        options = RenderOptions(title="My Database")
        output = render_mermaid(db, options)
        assert "title: My Database" in output

    def test_no_title_by_default(self) -> None:
        db = _simple_db()
        output = render_mermaid(db)
        assert "title:" not in output


class TestRelationships:
    """Test relationship rendering."""

    def test_multiple_fks_between_same_tables(self) -> None:
        """Two FKs from the same table to the same target should both appear."""
        sql = """
        CREATE TABLE users (id serial PRIMARY KEY);
        CREATE TABLE posts (
            id serial PRIMARY KEY,
            created_by integer NOT NULL,
            updated_by integer NOT NULL
        );
        ALTER TABLE posts ADD CONSTRAINT fk1
            FOREIGN KEY (created_by) REFERENCES users(id);
        ALTER TABLE posts ADD CONSTRAINT fk2
            FOREIGN KEY (updated_by) REFERENCES users(id);
        """
        db = parse_sql(sql)
        output = render_mermaid(db)
        assert '"created_by"' in output
        assert '"updated_by"' in output

    def test_relationship_only_shown_if_both_tables_visible(self) -> None:
        sql = """
        CREATE TABLE users (id serial PRIMARY KEY);
        CREATE TABLE posts (id serial PRIMARY KEY, user_id integer);
        ALTER TABLE posts ADD CONSTRAINT fk FOREIGN KEY (user_id) REFERENCES users(id);
        """
        db = parse_sql(sql)
        # Exclude users - relationship should not appear
        options = RenderOptions(exclude_tables=["users"])
        output = render_mermaid(db, options)
        assert "||--o{" not in output


class TestSanitization:
    """Test identifier sanitization."""

    def test_special_chars_in_table_name(self) -> None:
        sql = """
        CREATE TABLE "my-table" (id serial PRIMARY KEY);
        """
        db = parse_sql(sql)
        output = render_mermaid(db)
        # Hyphens should be replaced with underscores
        assert "my_table {" in output

    def test_table_name_starting_with_number(self) -> None:
        sql = """
        CREATE TABLE "123table" (id serial PRIMARY KEY);
        """
        db = parse_sql(sql)
        output = render_mermaid(db)
        # Should be prefixed with underscore
        assert "_123table {" in output
