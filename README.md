# CodeContexter

CodeContexter is a command-line tool that walks a source tree, filters files through `.gitignore` rules, and emits a single Markdown report (`code_summary.md`) with file metadata, statistics, and inline source listings.

## Features
- Reuses project ignore rules, combines them with the built-in `ALWAYS_IGNORE_PATTERNS`, and supports nested `.gitignore` files discovered during traversal.
- Detects file language and category using the tables in `codecontexter/constants.py`, then reports totals by both dimensions.
- Shows progress with `tqdm` when available; falls back to a simple iterator when the dependency is missing.
- Optionally appends per-file SHA-256 hashes for audit trails.
- Ships a `codecontexter` console script for Python 3.12+ via the `pyproject.toml` entry point.

## Installation
```bash
pip install codecontexter
# or
uv tool install codecontexter
```

Runtime dependency: `pathspec`. Optional dependency: `tqdm` for progress bars.

## Command-line usage
```bash
codecontexter DIRECTORY \
  --output OUTPUT_PATH \
  [--verbose] \
  [--no-metadata-table] \
  [--include-hash]
```

| Option | Description |
| --- | --- |
| `DIRECTORY` | Directory to scan (required positional argument). |
| `-o, --output` | Output Markdown path. Defaults to `code_summary.md`. |
| `-v, --verbose` | Print each processed file with size and line count. |
| `--no-metadata-table` | Skip the per-file overview table. |
| `--include-hash` | Compute SHA-256 for each file before writing the report. |

The CLI reports the resolved project root, the `.gitignore` file in use, and displays progress for scanning and writing when `tqdm` is present.

## Report layout
- **Header** – Repository name, generation timestamp, and source directory path.
- **Statistics** – Total files, total lines, total size, plus breakdowns by category and language.
- **File Metadata table** *(optional)* – File path, size, lines, language, category, and last modification timestamp.
- **Table of Contents** – Links to each file section using GitHub-Flavoured Markdown anchors.
- **File sections** – For each file: language label, size, line count, category, optional SHA-256, and a fenced code block with the exact file contents.

## Configuration points
- Language detection and categorisation live in `codecontexter/constants.py` (`LANGUAGE_MAP` and `FILE_CATEGORIES`). Extend these tables if your project relies on additional file types.
- Permanent ignore rules are defined in `ALWAYS_IGNORE_PATTERNS`. Add directories or patterns there to exclude them globally.
- Hashing is disabled by default; enable `--include-hash` when you need verifiable snapshots.

## Development
```bash
uv sync
source .venv/bin/activate
ruff check
python -m codecontexter.cli .
```

The project currently ships without automated tests. Use the CLI against a fixture project when verifying changes. `pytest` is listed in the `dev` extra for adding coverage.

## Roadmap ideas
- Allow size limits per file to avoid embedding large binaries.
- Offer an HTML writer alongside the Markdown generator.
- Group files by package or module to provide higher-level structure summaries.
