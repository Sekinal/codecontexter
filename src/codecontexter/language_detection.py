"""Language and file category detection utilities."""

import pathlib

from codecontexter.constants import FILE_CATEGORIES, LANGUAGE_MAP


def get_language_from_path(file_path: pathlib.Path) -> str | None:
    """Determines the language hint from the file path based on LANGUAGE_MAP.

    Args:
        file_path: Path to the file

    Returns:
        Language name string if detected, None otherwise

    Examples:
        >>> get_language_from_path(Path("test.py"))
        'python'
        >>> get_language_from_path(Path("Dockerfile"))
        'dockerfile'
    """
    name_lower = file_path.name.lower()

    # Check exact name first (case-insensitive)
    if name_lower in LANGUAGE_MAP:
        return LANGUAGE_MAP[name_lower]

    # Check exact name (case-sensitive) for files like Makefile
    if file_path.name in LANGUAGE_MAP:
        return LANGUAGE_MAP[file_path.name]

    # Check by extension
    if file_path.suffix.lower() in LANGUAGE_MAP:
        return LANGUAGE_MAP[file_path.suffix.lower()]

    # Special handling for files in .github/workflows
    if ".github" in file_path.parts and "workflows" in file_path.parts:
        if file_path.suffix in {".yml", ".yaml"}:
            return "yaml"

    # Include files with no extension as plain text if they appear to be text
    if not file_path.suffix:
        try:
            with open(file_path, encoding="utf-8") as f:
                f.read(512)
            return "text"
        except (OSError, UnicodeDecodeError):
            return None

    return None


def get_file_category(file_path: pathlib.Path) -> str:
    """Categorize file by its purpose.

    Args:
        file_path: Path to the file

    Returns:
        Category name ('source', 'config', 'docker', 'iac', 'ci_cd', 'build', 'docs', or 'other')

    Examples:
        >>> get_file_category(Path("main.py"))
        'source'
        >>> get_file_category(Path("config.json"))
        'config'
    """
    name_lower = file_path.name.lower()
    suffix_lower = file_path.suffix.lower()

    for category, extensions in FILE_CATEGORIES.items():
        if name_lower in extensions or suffix_lower in extensions:
            return category
    return "other"
