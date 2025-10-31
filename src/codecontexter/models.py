"""Data models for codecontexter."""

import pathlib
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FileMetadata:
    """Metadata for a single file.

    Attributes:
        path: Absolute path to the file
        relative_path: Path relative to the scan root
        language: Detected programming language
        size: File size in bytes
        lines: Number of lines in the file
        modified: Last modification timestamp (local time, no timezone)
        category: File category (source, config, etc.)
        file_hash: Optional SHA-256 hash of file contents
    """

    path: pathlib.Path
    relative_path: pathlib.Path
    language: str
    size: int
    lines: int
    modified: datetime
    category: str
    file_hash: str | None = None
