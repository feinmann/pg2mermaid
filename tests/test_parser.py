"""Tests for the SQL parser."""

from pg2mermaid.parser import parse_sql


class TestBasicCreateTable:
    """Test basic CREATE TABLE parsing."""

    def test_simple_table(self) -> None:
        sql = """
        CREATE TABLE users (
            id serial PRIMARY KEY,
            name text NOT NULL,
            email varchar(255)
        );
        """
        db = parse_sql(sql)
        assert db.table_count() == 1

        table = db.get_table("public", "users")
        assert table is not None
        assert table.name == "users"
        assert table.schema == "public"
        assert len(table.columns) == 3

    def test_column_types_normalized(self) -> None:
        sql = """
        CREATE TABLE t (
            a CHARACTER VARYING(100),
            b INTEGER,
            c BOOLEAN,
            d DOUBLE PRECISION,
            e TIMESTAMP WITHOUT TIME ZONE,
            f TIMESTAMP WITH TIME ZONE
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None

        types = {c.name: c.data_type for c in table.columns}
        assert types["a"] == "varchar(100)"
        assert types["b"] == "int"
        assert types["c"] == "bool"
        assert types["d"] == "float8"
        assert types["e"] == "timestamp"
        assert types["f"] == "timestamptz"

    def test_inline_primary_key(self) -> None:
        sql = """
        CREATE TABLE t (
            id serial PRIMARY KEY,
            name text
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None

        id_col = table.get_column("id")
        assert id_col is not None
        assert id_col.is_primary_key is True

        name_col = table.get_column("name")
        assert name_col is not None
        assert name_col.is_primary_key is False

    def test_table_level_primary_key(self) -> None:
        sql = """
        CREATE TABLE t (
            post_id integer NOT NULL,
            tag_id integer NOT NULL,
            PRIMARY KEY (post_id, tag_id)
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert table.primary_key == ["post_id", "tag_id"]
        assert table.get_column("post_id") is not None
        assert table.get_column("post_id").is_primary_key is True  # type: ignore[union-attr]
        assert table.get_column("tag_id") is not None
        assert table.get_column("tag_id").is_primary_key is True  # type: ignore[union-attr]

    def test_not_null_constraint(self) -> None:
        sql = """
        CREATE TABLE t (
            a text NOT NULL,
            b text
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert table.get_column("a") is not None
        assert table.get_column("a").nullable is False  # type: ignore[union-attr]
        assert table.get_column("b") is not None
        assert table.get_column("b").nullable is True  # type: ignore[union-attr]

    def test_default_values(self) -> None:
        sql = """
        CREATE TABLE t (
            a boolean DEFAULT false,
            b timestamp DEFAULT now(),
            c text DEFAULT 'hello'
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert table.get_column("a") is not None
        assert table.get_column("a").default == "false"  # type: ignore[union-attr]
        assert table.get_column("b") is not None
        assert table.get_column("b").default == "now()"  # type: ignore[union-attr]
        assert table.get_column("c") is not None
        assert table.get_column("c").default == "'hello'"  # type: ignore[union-attr]

    def test_create_table_if_not_exists(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            id serial PRIMARY KEY
        );
        """
        db = parse_sql(sql)
        assert db.table_count() == 1
        assert db.get_table("public", "users") is not None

    def test_create_unlogged_table(self) -> None:
        sql = """
        CREATE UNLOGGED TABLE sessions (
            id serial PRIMARY KEY,
            data text
        );
        """
        db = parse_sql(sql)
        assert db.table_count() == 1
        assert db.get_table("public", "sessions") is not None

    def test_multiple_tables(self) -> None:
        sql = """
        CREATE TABLE a (id serial PRIMARY KEY);
        CREATE TABLE b (id serial PRIMARY KEY);
        CREATE TABLE c (id serial PRIMARY KEY);
        """
        db = parse_sql(sql)
        assert db.table_count() == 3


class TestSchemaQualifiedNames:
    """Test schema-qualified table names."""

    def test_schema_qualified_name(self) -> None:
        sql = """
        CREATE TABLE auth.users (
            id serial PRIMARY KEY,
            email text NOT NULL
        );
        """
        db = parse_sql(sql)
        table = db.get_table("auth", "users")
        assert table is not None
        assert table.schema == "auth"
        assert table.name == "users"

    def test_quoted_schema_qualified_name(self) -> None:
        sql = """
        CREATE TABLE "my_schema"."my_table" (
            id serial PRIMARY KEY
        );
        """
        db = parse_sql(sql)
        table = db.get_table("my_schema", "my_table")
        assert table is not None

    def test_multiple_schemas(self) -> None:
        sql = """
        CREATE TABLE public.users (id serial PRIMARY KEY);
        CREATE TABLE auth.sessions (id serial PRIMARY KEY);
        CREATE TABLE billing.invoices (id serial PRIMARY KEY);
        """
        db = parse_sql(sql)
        assert len(db.schemas) == 3
        assert db.get_table("public", "users") is not None
        assert db.get_table("auth", "sessions") is not None
        assert db.get_table("billing", "invoices") is not None


class TestForeignKeys:
    """Test foreign key parsing."""

    def test_table_level_foreign_key(self) -> None:
        sql = """
        CREATE TABLE posts (
            id serial PRIMARY KEY,
            user_id integer NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "posts")
        assert table is not None
        assert len(table.foreign_keys) == 1

        fk = table.foreign_keys[0]
        assert fk.columns == ["user_id"]
        assert fk.ref_table == "users"
        assert fk.ref_columns == ["id"]

    def test_table_level_foreign_key_with_actions(self) -> None:
        sql = """
        CREATE TABLE posts (
            id serial PRIMARY KEY,
            user_id integer NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE SET NULL
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "posts")
        assert table is not None
        fk = table.foreign_keys[0]
        assert fk.on_delete == "CASCADE"
        assert fk.on_update is not None
        assert "NULL" in fk.on_update.upper()

    def test_named_constraint_foreign_key(self) -> None:
        sql = """
        CREATE TABLE posts (
            id serial PRIMARY KEY,
            user_id integer NOT NULL,
            CONSTRAINT posts_user_fk FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "posts")
        assert table is not None
        assert len(table.foreign_keys) == 1
        assert table.foreign_keys[0].constraint_name == "posts_user_fk"

    def test_inline_references(self) -> None:
        sql = """
        CREATE TABLE posts (
            id serial PRIMARY KEY,
            user_id integer REFERENCES users(id) ON DELETE CASCADE
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "posts")
        assert table is not None
        assert len(table.foreign_keys) == 1

        fk = table.foreign_keys[0]
        assert fk.columns == ["user_id"]
        assert fk.ref_table == "users"
        assert fk.ref_columns == ["id"]
        assert fk.on_delete == "CASCADE"

    def test_inline_references_marks_column_as_fk(self) -> None:
        sql = """
        CREATE TABLE posts (
            id serial PRIMARY KEY,
            user_id integer REFERENCES users(id)
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "posts")
        assert table is not None
        col = table.get_column("user_id")
        assert col is not None
        assert col.is_foreign_key is True

    def test_foreign_key_marks_column(self) -> None:
        sql = """
        CREATE TABLE posts (
            id serial PRIMARY KEY,
            user_id integer NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "posts")
        assert table is not None
        col = table.get_column("user_id")
        assert col is not None
        assert col.is_foreign_key is True

    def test_schema_qualified_reference(self) -> None:
        sql = """
        CREATE TABLE billing.invoices (
            id serial PRIMARY KEY,
            user_id integer NOT NULL,
            FOREIGN KEY (user_id) REFERENCES auth.users(id)
        );
        """
        db = parse_sql(sql)
        table = db.get_table("billing", "invoices")
        assert table is not None
        fk = table.foreign_keys[0]
        assert fk.ref_schema == "auth"
        assert fk.ref_table == "users"


class TestAlterTable:
    """Test ALTER TABLE constraint parsing."""

    def test_alter_table_primary_key(self) -> None:
        sql = """
        CREATE TABLE t (
            id serial,
            name text
        );
        ALTER TABLE t ADD CONSTRAINT t_pkey PRIMARY KEY (id);
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert table.primary_key == ["id"]
        col = table.get_column("id")
        assert col is not None
        assert col.is_primary_key is True

    def test_alter_table_foreign_key(self) -> None:
        sql = """
        CREATE TABLE users (id serial PRIMARY KEY);
        CREATE TABLE posts (
            id serial PRIMARY KEY,
            user_id integer NOT NULL
        );
        ALTER TABLE posts ADD CONSTRAINT posts_user_fk
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        """
        db = parse_sql(sql)
        table = db.get_table("public", "posts")
        assert table is not None
        assert len(table.foreign_keys) == 1

        fk = table.foreign_keys[0]
        assert fk.columns == ["user_id"]
        assert fk.ref_table == "users"
        assert fk.on_delete == "CASCADE"

    def test_alter_table_only(self) -> None:
        sql = """
        CREATE TABLE t (id serial, name text);
        ALTER TABLE ONLY t ADD CONSTRAINT t_pkey PRIMARY KEY (id);
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert table.primary_key == ["id"]

    def test_alter_table_unique(self) -> None:
        sql = """
        CREATE TABLE t (id serial PRIMARY KEY, email text);
        ALTER TABLE t ADD CONSTRAINT t_email_unique UNIQUE (email);
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert ["email"] in table.unique_constraints


class TestUniqueConstraints:
    """Test UNIQUE constraint parsing."""

    def test_table_level_unique(self) -> None:
        sql = """
        CREATE TABLE t (
            a text,
            b text,
            UNIQUE (a, b)
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert ["a", "b"] in table.unique_constraints


class TestEdgeCases:
    """Test edge cases and robustness."""

    def test_empty_sql(self) -> None:
        db = parse_sql("")
        assert db.table_count() == 0

    def test_sql_without_tables(self) -> None:
        db = parse_sql("SELECT 1;")
        assert db.table_count() == 0

    def test_string_literal_with_escaped_quotes(self) -> None:
        """PostgreSQL uses '' for escaping single quotes in strings."""
        sql = """
        CREATE TABLE t (
            id serial PRIMARY KEY,
            name text DEFAULT 'it''s a test'
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert len(table.columns) == 2

    def test_string_literal_with_semicolon_paren(self) -> None:
        """CREATE TABLE with ); inside a string literal should not break parsing."""
        sql = """
        CREATE TABLE t (
            id serial PRIMARY KEY,
            pattern text DEFAULT 'abc);def'
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert len(table.columns) == 2

    def test_nested_parentheses_in_check(self) -> None:
        sql = """
        CREATE TABLE t (
            id serial PRIMARY KEY,
            age integer,
            CHECK (age >= 0 AND age <= 150)
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert len(table.columns) == 2

    def test_quoted_column_names(self) -> None:
        sql = """
        CREATE TABLE t (
            "order" serial PRIMARY KEY,
            "group" text
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        assert table.get_column("order") is not None
        assert table.get_column("group") is not None

    def test_array_type(self) -> None:
        sql = """
        CREATE TABLE t (
            id serial PRIMARY KEY,
            tags text[]
        );
        """
        db = parse_sql(sql)
        table = db.get_table("public", "t")
        assert table is not None
        col = table.get_column("tags")
        assert col is not None
        assert "[]" in col.data_type


class TestFixtureFile:
    """Test against the included fixture file."""

    def test_simple_fixture(self) -> None:
        from pathlib import Path

        fixture = Path(__file__).parent / "fixtures" / "simple.sql"
        sql = fixture.read_text()
        db = parse_sql(sql)

        assert db.table_count() == 5
        assert db.get_table("public", "users") is not None
        assert db.get_table("public", "posts") is not None
        assert db.get_table("public", "comments") is not None
        assert db.get_table("public", "tags") is not None
        assert db.get_table("public", "post_tags") is not None

    def test_simple_fixture_foreign_keys(self) -> None:
        from pathlib import Path

        fixture = Path(__file__).parent / "fixtures" / "simple.sql"
        sql = fixture.read_text()
        db = parse_sql(sql)

        posts = db.get_table("public", "posts")
        assert posts is not None
        assert len(posts.foreign_keys) == 1
        assert posts.foreign_keys[0].ref_table == "users"

        comments = db.get_table("public", "comments")
        assert comments is not None
        assert len(comments.foreign_keys) == 2

        post_tags = db.get_table("public", "post_tags")
        assert post_tags is not None
        assert len(post_tags.foreign_keys) == 2
        assert post_tags.primary_key == ["post_id", "tag_id"]
