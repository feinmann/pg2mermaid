"""Command-line interface for pg2mermaid."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pg2mermaid import __version__
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

Export to image:
  pg2mermaid schema.sql --svg -o diagram.svg    Export as SVG
  pg2mermaid schema.sql --png -o diagram.png    Export as PNG
  pg2mermaid schema.sql --pdf -o diagram.pdf    Export as PDF

Output modes:
  --compact    Show only primary key and foreign key columns
  --normal     Show all columns with simplified types (default)
  --full       Show all columns with full type information

Export methods:
  --export-method auto     Try local mermaid-cli, fall back to online (default)
  --export-method local    Use mermaid-cli (requires: npm i -g @mermaid-js/mermaid-cli)
  --export-method online   Use kroki.io API (no installation required)
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

    # Image export options
    export_group = parser.add_argument_group("image export")
    export_format = export_group.add_mutually_exclusive_group()
    export_format.add_argument(
        "--svg",
        action="store_true",
        help="Export as SVG image",
    )
    export_format.add_argument(
        "--png",
        action="store_true",
        help="Export as PNG image",
    )
    export_format.add_argument(
        "--pdf",
        action="store_true",
        help="Export as PDF document",
    )
    export_group.add_argument(
        "--export-method",
        type=str,
        choices=["auto", "local", "online"],
        default="auto",
        help="Export method: auto, local (mermaid-cli), or online (kroki.io)",
    )
    export_group.add_argument(
        "--theme",
        type=str,
        choices=["default", "dark", "forest", "neutral"],
        default="default",
        help="Mermaid theme for image export (default: default)",
    )
    export_group.add_argument(
        "--background",
        type=str,
        default="white",
        metavar="COLOR",
        help="Background color for PNG export (default: white)",
    )
    export_group.add_argument(
        "--scale",
        type=int,
        default=2,
        metavar="N",
        help="Scale factor for PNG export (default: 2)",
    )

    # Filtering
    filter_group = parser.add_argument_group("filtering")
    filter_group.add_argument(
        "--schema",
        "-s",
        action="append",
        dest="include_schemas",
        metavar="NAME",
        help="Include only these schemas (can be repeated)",
    )
    filter_group.add_argument(
        "--exclude-schema",
        action="append",
        dest="exclude_schemas",
        metavar="NAME",
        help="Exclude these schemas (can be repeated)",
    )
    filter_group.add_argument(
        "--table",
        "-t",
        action="append",
        dest="include_tables",
        metavar="PATTERN",
        help="Include only tables matching pattern (supports * wildcard)",
    )
    filter_group.add_argument(
        "--exclude",
        "-e",
        action="append",
        dest="exclude_tables",
        metavar="PATTERN",
        help="Exclude tables matching pattern (supports * wildcard)",
    )
    filter_group.add_argument(
        "--connected-only",
        "-c",
        action="store_true",
        help="Only show tables that have relationships",
    )

    # Layout options
    layout_group = parser.add_argument_group("layout")
    layout_group.add_argument(
        "--max-columns",
        type=int,
        default=20,
        metavar="N",
        help="Max columns per table, 0 for unlimited (default: 20)",
    )
    layout_group.add_argument(
        "--group-by-schema",
        "-g",
        action="store_true",
        help="Group tables by schema in output",
    )
    layout_group.add_argument(
        "--no-schema-prefix",
        action="store_true",
        help="Don't prefix table names with schema",
    )
    layout_group.add_argument(
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
        version=f"%(prog)s {__version__}",
    )

    return parser


def run(args: argparse.Namespace) -> int:
    """Run the conversion with parsed arguments."""
    # Check for image export
    export_image = args.svg or args.png or args.pdf

    # Validate output for image export
    if export_image and args.output == "-":
        print("Error: Image export requires an output file (-o FILE).", file=sys.stderr)
        return 1

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

    # Render mermaid
    if args.format == "json" and not export_image:
        output = render_json(db, options)
    else:
        output = render_mermaid(db, options)

    # Handle image export
    if export_image:
        from pg2mermaid.exporter import (
            ExportError,
            ExportFormat,
            ExportMethod,
            export_diagram,
        )

        # Determine export format
        if args.svg:
            export_fmt = ExportFormat.SVG
        elif args.png:
            export_fmt = ExportFormat.PNG
        else:
            export_fmt = ExportFormat.PDF

        # Determine export method
        method_map = {
            "auto": ExportMethod.AUTO,
            "local": ExportMethod.LOCAL,
            "online": ExportMethod.ONLINE,
        }
        export_method = method_map[args.export_method]

        if args.verbose:
            print(f"Exporting as {export_fmt.value.upper()}...", file=sys.stderr)

        try:
            result_path = export_diagram(
                mermaid_code=output,
                output_path=args.output,
                export_format=export_fmt,
                method=export_method,
                background=args.background,
                theme=args.theme,
                scale=args.scale,
            )
            if args.verbose:
                print(f"Written to {result_path}", file=sys.stderr)
        except ExportError as e:
            print(f"Export error: {e}", file=sys.stderr)
            return 1

        return 0

    # Write text output
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
