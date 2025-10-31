"""Markdown output generation utilities."""

import pathlib
import re
import sys
from collections import defaultdict
from datetime import datetime

from codecontexter.file_operations import (
    collect_files,
    find_project_root,
    get_combined_spec,
    process_file,
    tqdm,
)
from codecontexter.models import FileMetadata


def generate_gfm_anchor(heading_text: str) -> str:
    """Generate a GitHub-Flavored Markdown anchor from heading text.

    Args:
        heading_text: The heading text (without # prefix)

    Returns:
        Anchor slug matching GFM behavior

    Examples:
        >>> generate_gfm_anchor("File: src/main.py")
        'file-srcmainpy'
    """
    # Remove backticks and lowercase
    slug = heading_text.replace("`", "").lower()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string like "1.5 MB"
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def generate_metadata_table(files_metadata: list[FileMetadata]) -> str:
    """Generate a markdown table with file metadata.

    Args:
        files_metadata: List of FileMetadata objects

    Returns:
        Markdown-formatted table as a string
    """
    table = "| File | Size | Lines | Type | Category | Last Modified |\n"
    table += "|------|------|-------|------|----------|---------------|\n"

    for meta in sorted(files_metadata, key=lambda x: str(x.relative_path)):
        size_str = format_size(meta.size)
        modified_str = meta.modified.strftime("%Y-%m-%d %H:%M")
        table += (
            f"| `{meta.relative_path}` | {size_str} | {meta.lines} | "
            f"{meta.language} | {meta.category} | {modified_str} |\n"
        )

    return table


def generate_statistics(files_metadata: list[FileMetadata]) -> str:
    """Generate statistics summary.

    Args:
        files_metadata: List of FileMetadata objects

    Returns:
        Markdown-formatted statistics section
    """
    total_files = len(files_metadata)
    total_lines = sum(m.lines for m in files_metadata)
    total_size = sum(m.size for m in files_metadata)

    # Group by category
    by_category = defaultdict(list)
    for meta in files_metadata:
        by_category[meta.category].append(meta)

    # Group by language
    by_language = defaultdict(list)
    for meta in files_metadata:
        by_language[meta.language].append(meta)

    stats = "## 📊 Statistics\n\n"
    stats += f"- **Total Files:** {total_files}\n"
    stats += f"- **Total Lines of Code:** {total_lines:,}\n"
    stats += f"- **Total Size:** {format_size(total_size)}\n\n"

    stats += "### By Category\n\n"
    for category, metas in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(metas)
        lines = sum(m.lines for m in metas)
        stats += f"- **{category}:** {count} files, {lines:,} lines\n"

    stats += "\n### By Language\n\n"
    for language, metas in sorted(by_language.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(metas)
        lines = sum(m.lines for m in metas)
        stats += f"- **{language}:** {count} files, {lines:,} lines\n"

    return stats


def create_markdown(
    target_dir: str,
    output_file: str,
    verbose: bool,
    include_metadata_table: bool,
    include_hash: bool,
):
    """Generates the enhanced Markdown file.

    Args:
        target_dir: Directory to scan for code files
        output_file: Path to output markdown file
        verbose: Whether to print detailed progress
        include_metadata_table: Whether to include metadata table
        include_hash: Whether to compute SHA-256 hashes
    """
    start_path = pathlib.Path(target_dir).resolve()
    output_path = pathlib.Path(output_file).resolve()

    try:
        script_path = pathlib.Path(__file__).resolve()
    except NameError:
        script_path = pathlib.Path.cwd() / "code_summarizer.py"

    if not start_path.is_dir():
        print(f"Error: Directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    project_root = find_project_root(start_path)
    combined_spec = get_combined_spec(project_root)

    print(f"📂 Scanning directory: {start_path}")
    print(f"🔍 Project root: {project_root}")
    if (project_root / ".gitignore").exists():
        print(f"✓ Using .gitignore from: {project_root / '.gitignore'}")

    # Collect files
    print("📑 Collecting files...")
    file_paths = collect_files(start_path, project_root, combined_spec, output_path, script_path)
    print(f"✓ Found {len(file_paths)} files to process")

    # Process files with metadata
    print("🔄 Processing files and extracting metadata...")
    files_metadata: list[FileMetadata] = []

    with tqdm(total=len(file_paths), desc="Processing", unit="file") as pbar:
        for file_path in file_paths:
            meta = process_file(file_path, start_path, include_hash)
            if meta:
                files_metadata.append(meta)
                if verbose:
                    print(
                        f"  ✓ {meta.relative_path} ({meta.lines} lines, {format_size(meta.size)})"
                    )
            pbar.update(1)

    # Write markdown
    print(f"📝 Writing to {output_path}...")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as md_file:
            # Header
            md_file.write(f"# 📦 Code Summary: {start_path.name}\n\n")
            md_file.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            md_file.write(f"**Source Directory:** `{start_path}`\n\n")
            md_file.write("---\n\n")

            # Statistics
            md_file.write(generate_statistics(files_metadata))
            md_file.write("\n---\n\n")

            # Metadata table
            if include_metadata_table:
                md_file.write("## 📋 File Metadata\n\n")
                md_file.write(generate_metadata_table(files_metadata))
                md_file.write("\n---\n\n")

            # Table of Contents
            md_file.write("## 📑 Table of Contents\n\n")
            for meta in sorted(files_metadata, key=lambda x: str(x.relative_path)):
                # Generate anchor matching the actual heading format
                heading_text = f"File: {meta.relative_path}"
                anchor = generate_gfm_anchor(heading_text)
                md_file.write(f"- [`{meta.relative_path}`](#{anchor})\n")
            md_file.write("\n---\n\n")

            # File contents
            md_file.write("## 📄 File Contents\n\n")
            with tqdm(total=len(files_metadata), desc="Writing", unit="file") as pbar:
                for meta in sorted(files_metadata, key=lambda x: str(x.relative_path)):
                    try:
                        with open(meta.path, encoding="utf-8", errors="ignore") as code_file:
                            content = code_file.read()

                        md_file.write(f"### File: `{meta.relative_path}`\n\n")
                        md_file.write(f"**Language:** {meta.language} | ")
                        md_file.write(f"**Size:** {format_size(meta.size)} | ")
                        md_file.write(f"**Lines:** {meta.lines} | ")
                        md_file.write(f"**Category:** {meta.category}\n\n")

                        if meta.file_hash:
                            md_file.write(f"**Hash (SHA-256):** `{meta.file_hash}`\n\n")

                        # Write code fence with language hint for syntax highlighting
                        md_file.write(f"```{meta.language}\n")
                        md_file.write(content)
                        if not content.endswith("\n"):
                            md_file.write("\n")
                        md_file.write("```\n\n")
                        md_file.write("---\n\n")
                    except (OSError, UnicodeDecodeError) as e:
                        print(
                            f"⚠ Warning: Could not read {meta.relative_path}: {e}",
                            file=sys.stderr,
                        )

                    pbar.update(1)

        print(f"\n✅ Success! Processed {len(files_metadata)} files")
        print(f"📊 Total lines: {sum(m.lines for m in files_metadata):,}")
        print(f"💾 Total size: {format_size(sum(m.size for m in files_metadata))}")
        print(f"📄 Output: {output_path}")

    except OSError as e:
        print(f"\n❌ Error: Could not write to {output_path}: {e}", file=sys.stderr)
        sys.exit(1)
