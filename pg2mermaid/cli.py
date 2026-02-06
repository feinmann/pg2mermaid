"""Command-line interface for pg2mermaid."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pg2mermaid.parser import parse_sql
from pg2mermaid.renderer import (
    OutputFormat,
    OutputMode,
    RenderOptions,
    render_json,
    render_mermaid,
)


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    try:
        return run(parsed)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if parsed.verbose:
            import traceback

            traceback.print_exc()
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pg2mermaid",
        description="Convert PostgreSQL dump files to Mermaid ER diagrams.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pg2mermaid schema.sql                    Convert and print to stdout
  pg2mermaid schema.sql -o diagram.md      Convert and save to file
  pg_dump mydb | pg2mermaid                Read from stdin
  pg2mermaid dump.sql --schema public      Only include 'public' schema
  pg2mermaid dump.sql --exclude '*_old'    Exclude tables ending in '_old'
  pg2mermaid dump.sql --compact            Show only PK/FK columns
  pg2mermaid dump.sql --connected-only     Only show tables with relationships

Output modes:
  --compact    Show only primary key and foreign key columns
  --normal     Show all columns with simplified types (default)
  --full       Show all columns with full type information
""",
    )

    # Input/Output
    parser.add_argument(
        "input",
        nargs="?",
        type=str,
        default="-",
        help="Input SQL file (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="-",
        help="Output file (default: stdout)",
    )

    # Output mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--compact",
        action="store_const",
        const=OutputMode.COMPACT,
        dest="mode",
        help="Show only PK/FK columns",
    )
    mode_group.add_argument(
        "--normal",
        action="store_const",
        const=OutputMode.NORMAL,
        dest="mode",
        help="Show all columns with simplified types (default)",
    )
    mode_group.add_argument(
        "--full",
        action="store_const",
        const=OutputMode.FULL,
        dest="mode",
        help="Show all columns with full type information",
    )
    parser.set_defaults(mode=OutputMode.NORMAL)

    # Output format
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["mermaid", "markdown", "json"],
        default="mermaid",
        help="Output format (default: mermaid)",
    )

    # Filtering
    parser.add_argument(
        "--schema",
        "-s",
        action="append",
        dest="include_schemas",
        metavar="NAME",
        help="Include only these schemas (can be repeated)",
    )
    parser.add_argument(
        "--exclude-schema",
        action="append",
        dest="exclude_schemas",
        metavar="NAME",
        help="Exclude these schemas (can be repeated)",
    )
    parser.add_argument(
        "--table",
        "-t",
        action="append",
        dest="include_tables",
        metavar="PATTERN",
        help="Include only tables matching pattern (supports * wildcard)",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        action="append",
        dest="exclude_tables",
        metavar="PATTERN",
        help="Exclude tables matching pattern (supports * wildcard)",
    )
    parser.add_argument(
        "--connected-only",
        "-c",
        action="store_true",
        help="Only show tables that have relationships",
    )

    # Layout options
    parser.add_argument(
        "--max-columns",
        type=int,
        default=20,
        metavar="N",
        help="Max columns per table, 0 for unlimited (default: 20)",
    )
    parser.add_argument(
        "--group-by-schema",
        "-g",
        action="store_true",
        help="Group tables by schema in output",
    )
    parser.add_argument(
        "--no-schema-prefix",
        action="store_true",
        help="Don't prefix table names with schema",
    )
    parser.add_argument(
        "--title",
        type=str,
        help="Add a title to the diagram",
    )

    # Other
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output (show stats and debugging info)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return parser


def run(args: argparse.Namespace) -> int:
    """Run the conversion with parsed arguments."""
    # Read input
    if args.input == "-":
        if sys.stdin.isatty():
            print("Error: No input provided. Use a file or pipe data to stdin.", file=sys.stderr)
            print("Try 'pg2mermaid --help' for usage information.", file=sys.stderr)
            return 1
        sql = sys.stdin.read()
        input_name = "<stdin>"
    else:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: File not found: {args.input}", file=sys.stderr)
            return 1
        sql = input_path.read_text(encoding="utf-8")
        input_name = args.input

    if not sql.strip():
        print("Error: Input is empty.", file=sys.stderr)
        return 1

    # Parse SQL
    if args.verbose:
        print(f"Parsing {input_name}...", file=sys.stderr)

    db = parse_sql(sql)

    if args.verbose:
        print(
            f"Found {db.table_count()} tables in {len(db.schemas)} schema(s).",
            file=sys.stderr,
        )
        for schema in db.schemas.values():
            print(f"  {schema.name}: {len(schema.tables)} tables", file=sys.stderr)

    if db.table_count() == 0:
        print("Warning: No tables found in input.", file=sys.stderr)

    # Build render options
    options = RenderOptions(
        mode=args.mode,
        format=OutputFormat.MARKDOWN if args.format == "markdown" else OutputFormat.MERMAID,
        include_schemas=args.include_schemas,
        exclude_schemas=args.exclude_schemas,
        include_tables=args.include_tables,
        exclude_tables=args.exclude_tables,
        connected_only=args.connected_only,
        show_schema_prefix=not args.no_schema_prefix,
        max_columns=args.max_columns,
        group_by_schema=args.group_by_schema,
        title=args.title,
    )

    # Render output
    if args.format == "json":
        output = render_json(db, options)
    else:
        output = render_mermaid(db, options)

    # Write output
    if args.output == "-":
        print(output)
    else:
        output_path = Path(args.output)
        output_path.write_text(output, encoding="utf-8")
        if args.verbose:
            print(f"Written to {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
