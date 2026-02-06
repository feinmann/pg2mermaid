# pg2mermaid

Convert PostgreSQL dump files to Mermaid ER diagrams, with optional export to SVG, PNG, or PDF.

## Installation

```bash
# From the project directory
pip install -e .

# Or run directly
python -m pg2mermaid
```

## Quick Start

```bash
# Convert a pg_dump file to Mermaid
pg2mermaid schema.sql

# Save to file
pg2mermaid schema.sql -o diagram.md

# Export directly to SVG
pg2mermaid schema.sql --svg -o diagram.svg

# Pipe from pg_dump
pg_dump mydb --schema-only | pg2mermaid -o diagram.md
```

## Usage

```
pg2mermaid [OPTIONS] [INPUT]

Arguments:
  INPUT    Input SQL file (default: stdin)

Options:
  -o, --output FILE      Output file (default: stdout)
  --compact              Show only PK/FK columns
  --normal               Show all columns, simplified types (default)
  --full                 Show all columns with full type info
  -f, --format FORMAT    Output: mermaid, markdown, or json
  -s, --schema NAME      Include only these schemas (repeatable)
  --exclude-schema NAME  Exclude these schemas (repeatable)
  -t, --table PATTERN    Include tables matching pattern (supports *)
  -e, --exclude PATTERN  Exclude tables matching pattern (supports *)
  -c, --connected-only   Only show tables with relationships
  --max-columns N        Max columns per table (default: 20, 0=unlimited)
  -g, --group-by-schema  Group tables by schema in output
  --no-schema-prefix     Don't prefix table names with schema
  --title TEXT           Add a title to the diagram
  -v, --verbose          Show parsing statistics
  --help                 Show help message

Image Export:
  --svg                  Export as SVG image
  --png                  Export as PNG image
  --pdf                  Export as PDF document
  --export-method TYPE   auto (default), local, or online
  --theme THEME          default, dark, forest, or neutral
  --background COLOR     Background color for PNG (default: white)
  --scale N              Scale factor for PNG (default: 2)
```

## Examples

### Basic Conversion

```bash
pg2mermaid database.sql
```

Output:
```mermaid
erDiagram
    users {
        serial id PK
        varchar email
        text name
    }
    posts {
        serial id PK
        int user_id FK
        text title
    }
    users ||--o{ posts : "user_id"
```

### Export to SVG

```bash
# Using online API (no installation required)
pg2mermaid schema.sql --svg -o diagram.svg

# Using local mermaid-cli (if installed)
pg2mermaid schema.sql --svg -o diagram.svg --export-method local
```

### Export to PNG

```bash
# High-resolution PNG with dark theme
pg2mermaid schema.sql --png -o diagram.png --theme dark --scale 3
```

### Filter by Schema

```bash
# Only include 'public' and 'auth' schemas
pg2mermaid dump.sql --schema public --schema auth
```

### Exclude Tables

```bash
# Exclude backup and staging tables
pg2mermaid dump.sql --exclude "*_backup" --exclude "*_staging" --exclude "*_old"
```

### Compact Mode (Large Schemas)

For schemas with many tables, show only primary and foreign keys:

```bash
pg2mermaid dump.sql --compact
```

### Connected Tables Only

Show only tables that have foreign key relationships:

```bash
pg2mermaid dump.sql --connected-only
```

### JSON Output

For programmatic processing:

```bash
pg2mermaid dump.sql --format json > schema.json
```

### Markdown Output

Wrap diagram in markdown code block:

```bash
pg2mermaid dump.sql --format markdown -o schema.md
```

## Image Export Methods

pg2mermaid supports two methods for exporting to image formats:

### Online (kroki.io) - Default

Uses the free [kroki.io](https://kroki.io) API. No installation required, works out of the box.

```bash
pg2mermaid schema.sql --svg -o diagram.svg --export-method online
```

### Local (mermaid-cli)

Uses the official Mermaid CLI tool. Requires Node.js installation but works offline.

```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Use local rendering
pg2mermaid schema.sql --svg -o diagram.svg --export-method local
```

### Auto (Default Behavior)

By default (`--export-method auto`), pg2mermaid tries local mermaid-cli first and falls back to the online API if not available.

## Viewing Diagrams

The generated Mermaid diagrams can be viewed in:

- **GitHub/GitLab**: Renders Mermaid in markdown files automatically
- **VS Code**: Install the "Mermaid Preview" extension
- **Online**: Paste into [mermaid.live](https://mermaid.live)
- **Documentation**: Works with MkDocs, Docusaurus, etc.

## Features

- **Zero dependencies**: Pure Python, no external packages required
- **Image export**: SVG, PNG, PDF via online API or local mermaid-cli
- **Full PostgreSQL support**: Handles all standard data types
- **Smart filtering**: Include/exclude by schema, table name, or pattern
- **Scalable output**: Compact mode and column limits for large schemas
- **Relationship detection**: Parses both inline and ALTER TABLE foreign keys
- **Multiple formats**: Mermaid, Markdown-wrapped, JSON, SVG, PNG, PDF

## Supported SQL Features

- `CREATE TABLE` with all PostgreSQL data types
- `PRIMARY KEY` (inline and table-level)
- `FOREIGN KEY` with `REFERENCES` (inline and via `ALTER TABLE`)
- `UNIQUE` constraints
- `NOT NULL` and `DEFAULT` values
- Schema-qualified table names
- Quoted identifiers

## Requirements

- Python 3.10 or higher
- For local image export: Node.js and `@mermaid-js/mermaid-cli`

## License

MIT
