"""CodeContexter: A tool for creating enhanced Markdown summaries of code files.

This package provides utilities to scan directories, analyze code files,
and generate comprehensive documentation in Markdown format.
"""

from codecontexter.cli import main
from codecontexter.models import FileMetadata

__version__ = "0.1.0"
__all__ = ["main", "FileMetadata"]
