"""File system operations and file processing utilities."""

import hashlib
import os
import pathlib
import sys
from datetime import datetime

import pathspec

from codecontexter.constants import ALWAYS_IGNORE_PATTERNS
from codecontexter.language_detection import get_file_category, get_language_from_path
from codecontexter.models import FileMetadata

# For better user experience with progress tracking
try:
    import tqdm
except ImportError:

    class tqdm:  # type: ignore # noqa: N801
        """Fallback tqdm class if tqdm is not installed."""

        def __init__(self, iterable=None, **kwargs):
            self.iterable = iterable or []

        def __iter__(self):
            return iter(self.iterable)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def update(self, n=1):
            pass

        def close(self):
            pass


def count_lines(file_path: pathlib.Path) -> int:
    """Efficiently count lines in a file.

    Args:
        file_path: Path to the file

    Returns:
        Number of lines in the file, or 0 if error
    """
    try:
        with open(file_path, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def get_file_hash(file_path: pathlib.Path, hash_files: bool = False) -> str | None:
    """Get SHA-256 hash of file for verification.

    Args:
        file_path: Path to the file
        hash_files: Whether to compute hash (expensive operation)

    Returns:
        SHA-256 hash hex string if hash_files is True, None otherwise
    """
    if not hash_files:
        return None
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except OSError:
        return None


def process_file(
    file_path: pathlib.Path, start_path: pathlib.Path, include_hash: bool = False
) -> FileMetadata | None:
    """Process a single file and extract metadata.

    Args:
        file_path: Path to the file to process
        start_path: Root path for calculating relative paths
        include_hash: Whether to compute SHA-256 hash

    Returns:
        FileMetadata object if successful, None if file cannot be processed
    """
    try:
        lang = get_language_from_path(file_path)
        if lang is None:
            return None

        stat = file_path.stat()
        return FileMetadata(
            path=file_path,
            relative_path=file_path.relative_to(start_path),
            language=lang or "text",
            size=stat.st_size,
            lines=count_lines(file_path),
            modified=datetime.fromtimestamp(stat.st_mtime),
            category=get_file_category(file_path),
            file_hash=get_file_hash(file_path, include_hash),
        )
    except Exception as e:
        print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
        return None


def find_project_root(start_dir: pathlib.Path) -> pathlib.Path:
    """Find the nearest parent directory containing .git or return start_dir.

    Args:
        start_dir: Starting directory for search

    Returns:
        Path to project root (directory containing .git) or start_dir if not found
    """
    current = start_dir.resolve()
    while True:
        if (current / ".git").is_dir():
            return current
        parent = current.parent
        if parent == current:
            print(
                "Warning: .git directory not found. Using starting directory as project root.",
                file=sys.stderr,
            )
            return start_dir.resolve()
        current = parent


def get_combined_spec(root_dir: pathlib.Path) -> pathspec.PathSpec:
    """Combines ALWAYS_IGNORE_PATTERNS with patterns from .gitignore files.

    Loads .gitignore from project root and also checks .git/info/exclude.

    Args:
        root_dir: Project root directory

    Returns:
        PathSpec object combining hardcoded patterns and .gitignore patterns
    """
    all_patterns = list(ALWAYS_IGNORE_PATTERNS)

    # Load root .gitignore
    gitignore_path = root_dir / ".gitignore"
    if gitignore_path.is_file():
        try:
            with open(gitignore_path, encoding="utf-8", errors="ignore") as f:
                all_patterns.extend(f.readlines())
        except Exception as e:
            print(
                f"Warning: Could not read .gitignore at {gitignore_path}: {e}",
                file=sys.stderr,
            )

    # Load .git/info/exclude if it exists
    git_exclude_path = root_dir / ".git" / "info" / "exclude"
    if git_exclude_path.is_file():
        try:
            with open(git_exclude_path, encoding="utf-8", errors="ignore") as f:
                all_patterns.extend(f.readlines())
        except Exception as e:
            print(
                f"Warning: Could not read .git/info/exclude: {e}",
                file=sys.stderr,
            )

    return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, all_patterns)


def load_nested_gitignore(directory: pathlib.Path) -> list[str]:
    """Load .gitignore patterns from a specific directory.

    Args:
        directory: Directory to check for .gitignore

    Returns:
        List of pattern lines from the .gitignore file, or empty list if not found
    """
    gitignore_path = directory / ".gitignore"
    if gitignore_path.is_file():
        try:
            with open(gitignore_path, encoding="utf-8", errors="ignore") as f:
                return f.readlines()
        except OSError:
            pass
    return []


def collect_files(
    start_path: pathlib.Path,
    project_root: pathlib.Path,
    combined_spec: pathspec.PathSpec,
    output_path: pathlib.Path,
    script_path: pathlib.Path,
) -> list[pathlib.Path]:
    """Efficiently collect all files to process.

    Args:
        start_path: Directory to start scanning from
        project_root: Project root for calculating relative paths
        combined_spec: PathSpec with ignore patterns
        output_path: Output file path to exclude
        script_path: Script file path to exclude

    Returns:
        List of file paths that should be processed
    """
    files_to_process = []

    for root, dirs, files in os.walk(start_path, topdown=True):
        root_path = pathlib.Path(root)

        # Check for nested .gitignore and merge with base patterns
        nested_patterns = load_nested_gitignore(root_path)
        if nested_patterns:
            # Create a combined spec with nested patterns
            base_patterns = list(combined_spec.patterns)
            local_spec = pathspec.PathSpec.from_lines(
                pathspec.patterns.GitWildMatchPattern,
                [str(p) for p in base_patterns] + nested_patterns,
            )
        else:
            local_spec = combined_spec

        # Prune ignored directories
        for d in list(dirs):
            dir_path = root_path / d
            try:
                relative_dir = dir_path.relative_to(project_root)
                # Add trailing slash to match directory patterns like "node_modules/"
                relative_dir_str = str(relative_dir).replace(os.sep, "/") + "/"
                if local_spec.match_file(relative_dir_str):
                    dirs.remove(d)
            except ValueError:
                pass

        for filename in files:
            file_path = root_path / filename

            # Skip output and script
            try:
                if file_path.resolve() in (
                    output_path.resolve(),
                    script_path.resolve(),
                ):
                    continue
            except (OSError, ValueError):
                pass

            # Check against ignore patterns (including nested .gitignore)
            try:
                relative_file = file_path.relative_to(project_root)
                relative_file_str = str(relative_file).replace(os.sep, "/")
                if local_spec.match_file(relative_file_str):
                    continue
            except ValueError:
                pass

            # Check if file type is supported
            if get_language_from_path(file_path) is not None:
                files_to_process.append(file_path)

    return files_to_process
