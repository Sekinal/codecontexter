"""Command-line interface for codecontexter."""

import argparse

from codecontexter.output_generators import create_markdown


def main():
    """Main entry point for the codecontexter CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Create an enhanced Markdown summary of code files "
            "with rich metadata and Docker support."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="The target directory to scan for code files.")
    parser.add_argument(
        "-o",
        "--output",
        default="code_summary.md",
        help="The path for the output Markdown file.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed processing information.",
    )
    parser.add_argument(
        "--no-metadata-table",
        action="store_true",
        help="Skip generating the metadata table.",
    )
    parser.add_argument(
        "--include-hash",
        action="store_true",
        help="Include SHA-256 hash for each file (slower).",
    )

    args = parser.parse_args()

    create_markdown(
        args.directory,
        args.output,
        args.verbose,
        not args.no_metadata_table,
        args.include_hash,
    )


if __name__ == "__main__":
    main()
