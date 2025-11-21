#!/usr/bin/env python3
"""
DeepContext: A production-grade codebase serializer for LLM Context Windows.
Generates a structured Markdown summary of a directory with metadata, trees, and token estimates.
"""

import argparse
import concurrent.futures
import logging
import os
import pathlib
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Generator

# Try to import pathspec, handle absence gracefully
try:
    import pathspec
except ImportError:
    print("Error: 'pathspec' module is required. Install with: pip install pathspec", file=sys.stderr)
    sys.exit(1)

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------

# Rough estimate for token calculation (4 chars ~= 1 token)
CHARS_PER_TOKEN = 4
MAX_FILE_SIZE_BYTES = 1_000_000  # 1 MB limit per file to prevent context flooding
MAX_WORKERS = os.cpu_count() or 4

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("DeepContext")

class LanguageConfig:
    """Static configuration for language detection and categorization."""
    
    EXTENSION_MAP: Dict[str, str] = {
        # Python
        '.py': 'python', '.pyi': 'python', '.pyx': 'python', '.ipynb': 'json',
        # Web
        '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
        '.html': 'html', '.css': 'css', '.scss': 'scss', '.vue': 'vue', '.svelte': 'svelte',
        # JVM
        '.java': 'java', '.kt': 'kotlin', '.scala': 'scala', '.gradle': 'groovy',
        # Native
        '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp', '.rs': 'rust', '.go': 'go',
        # Scripting
        '.sh': 'bash', '.bash': 'bash', '.zsh': 'zsh', '.lua': 'lua', '.rb': 'ruby', '.php': 'php',
        # Config/Data
        '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml', '.xml': 'xml',
        '.sql': 'sql', '.md': 'markdown', '.txt': 'text', 'Dockerfile': 'dockerfile',
        '.tf': 'hcl'
    }

    IGNORE_PATTERNS: Set[str] = {
        # SCM
        '.git', '.svn', '.hg',
        # Dependencies
        'node_modules', 'venv', '.venv', 'env', 'dist', 'build', 'target',
        '__pycache__', '.pytest_cache', '.mypy_cache', 'vendor',
        # Media/Binary
        '*.png', '*.jpg', '*.jpeg', '*.gif', '*.ico', '*.svg', '*.pdf',
        '*.zip', '*.tar', '*.gz', '*.7z', '*.rar',
        '*.exe', '*.dll', '*.so', '*.dylib', '*.class', '*.jar',
        '*.db', '*.sqlite', '*.sqlite3', '*.pyc',
        'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'Gemfile.lock'
    }

# -----------------------------------------------------------------------------
# Data Structures
# -----------------------------------------------------------------------------

@dataclass
class FileArtifact:
    """Immutable representation of a processed file."""
    path: pathlib.Path
    relative_path: str
    extension: str
    language: str
    size: int
    lines: int
    content: str
    token_estimate: int
    is_truncated: bool

@dataclass
class ProjectSummary:
    """Aggregated statistics for the project."""
    total_files: int
    total_lines: int
    total_tokens: int
    file_tree: str
    artifacts: List[FileArtifact]

# -----------------------------------------------------------------------------
# Component: Project Scanner (Discovery)
# -----------------------------------------------------------------------------

class ProjectScanner:
    """Responsible for file discovery and ignore logic."""

    def __init__(self, root_dir: pathlib.Path):
        self.root_dir = root_dir.resolve()
        self.git_ignore_spec = self._load_gitignore()

    def _load_gitignore(self) -> pathspec.PathSpec:
        """Loads .gitignore if present, otherwise returns empty spec."""
        gitignore_path = self.root_dir / '.gitignore'
        # Start with our default ignore patterns
        patterns = list(LanguageConfig.IGNORE_PATTERNS)
        
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    # Add lines from .gitignore
                    patterns.extend(f.readlines())
            except Exception as e:
                logger.warning(f"Could not read .gitignore: {e}")

        return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, patterns)

    def should_ignore(self, file_path: pathlib.Path) -> bool:
        """Check if a file matches global ignores or .gitignore."""
        try:
            # pathspec requires relative paths for matching
            rel_path = file_path.relative_to(self.root_dir).as_posix()
            
            # 1. Check base name against simple set (fast)
            if file_path.name in LanguageConfig.IGNORE_PATTERNS:
                return True
            
            # 2. Check against pathspec (handles globs like *.pyc or dir/file)
            if self.git_ignore_spec.match_file(rel_path):
                return True
                
            return False
        except ValueError:
            # If relative path cannot be computed, ignore it to be safe
            return True

    def scan(self) -> Generator[pathlib.Path, None, None]:
        """Yields valid files from the directory."""
        for root, dirs, files in os.walk(self.root_dir):
            # Modify dirs in-place to prune traversal (optimization)
            # We must check if the DIRECTORY itself is ignored
            dirs[:] = [d for d in dirs if not self.should_ignore(pathlib.Path(root) / d)]
            
            for file in files:
                path = pathlib.Path(root) / file
                if not self.should_ignore(path):
                    yield path

    def generate_tree(self) -> str:
        """Generates a visual tree structure for LLM context."""
        tree_lines = []
        
        # Retrieve all valid paths first
        paths = sorted(list(self.scan()), key=lambda p: str(p))
        if not paths:
            return "No files found."

        # Convert to relative strings
        rel_paths = [p.relative_to(self.root_dir) for p in paths]
        
        added_dirs = set()
        
        tree_lines.append(f"📂 {self.root_dir.name}/")
        
        for p in rel_paths:
            parts = p.parts
            depth = len(parts) - 1
            
            # Print directory structure leading to file
            for i in range(depth):
                parent_parts = parts[:i+1]
                parent_path = pathlib.Path(*parent_parts)
                if parent_path not in added_dirs:
                    indent = "│   " * i
                    tree_lines.append(f"{indent}├── {parent_parts[-1]}/")
                    added_dirs.add(parent_path)
            
            # Print file
            indent = "│   " * depth
            tree_lines.append(f"{indent}├── {parts[-1]}")

        return "\n".join(tree_lines)

# -----------------------------------------------------------------------------
# Component: File Processor (Extraction)
# -----------------------------------------------------------------------------

class FileProcessor:
    """Responsible for reading and metadata extraction."""

    @staticmethod
    def process(path: pathlib.Path, root: pathlib.Path) -> Optional[FileArtifact]:
        """Process a single file. Static method for ProcessPool serialization."""
        try:
            stat = path.stat()
            if stat.st_size == 0:
                return None

            rel_path = path.relative_to(root).as_posix()
            
            # Language Detection
            ext = path.suffix.lower()
            name = path.name.lower()
            lang = LanguageConfig.EXTENSION_MAP.get(ext, 'text')
            if name == 'dockerfile': lang = 'dockerfile'
            if name == 'makefile': lang = 'makefile'

            # Content Reading with safeguards
            content = ""
            is_truncated = False
            
            if stat.st_size > MAX_FILE_SIZE_BYTES:
                # For huge files, only read the tail (usually most recent logic/logs)
                content = (f"<!-- WARNING: File too large ({stat.st_size} bytes). "
                           f"Truncated to last 1000 lines for context. -->\n\n")
                try:
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        # Deque is more efficient for tails, but list slicing is fine here
                        lines = f.readlines()
                        content += "".join(lines[-1000:])
                    is_truncated = True
                except Exception:
                    return None
            else:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # Binary file detected during read
                    return None

            line_count = content.count('\n') + 1
            token_est = len(content) // CHARS_PER_TOKEN

            return FileArtifact(
                path=path,
                relative_path=rel_path,
                extension=ext,
                language=lang,
                size=stat.st_size,
                lines=line_count,
                content=content,
                token_estimate=token_est,
                is_truncated=is_truncated
            )
        except Exception as e:
            logger.error(f"Error processing {path}: {e}")
            return None

# -----------------------------------------------------------------------------
# Component: Report Generator (Output)
# -----------------------------------------------------------------------------

class ReportGenerator:
    """Responsible for formatting the final Markdown output."""

    @staticmethod
    def generate(summary: ProjectSummary) -> str:
        md = []
        md.append(f"# 📦 Codebase Context: {os.path.basename(os.getcwd())}\n")
        md.append(f"> Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                  f"Files: {summary.total_files} | "
                  f"Tokens: ~{summary.total_tokens:,}\n")
        
        md.append("\n## 🌲 Project Structure\n")
        md.append("```text\n") # Added newline
        md.append(summary.file_tree)
        if not summary.file_tree.endswith('\n'):
            md.append("\n")
        md.append("```\n")

        md.append("\n## 📄 File Contents\n")
        
        # Sort artifacts by path for consistent output
        sorted_artifacts = sorted(summary.artifacts, key=lambda x: x.relative_path)

        for artifact in sorted_artifacts:
            md.append(f"\n### `{artifact.relative_path}`\n")
            
            meta_tags = []
            if artifact.is_truncated: meta_tags.append("⚠️ TRUNCATED")
            meta_info = f"Language: {artifact.language} | Lines: {artifact.lines} | Tokens: ~{artifact.token_estimate}"
            if meta_tags:
                meta_info += f" | {' '.join(meta_tags)}"
            
            md.append(f"_{meta_info}_\n")
            
            # Use fence with language for syntax highlighting
            md.append(f"```{artifact.language}\n") # Added newline
            md.append(artifact.content)
            if not artifact.content.endswith('\n'):
                md.append("\n")
            md.append("```\n")
            
            md.append("---\n")

        return "".join(md)

# -----------------------------------------------------------------------------
# Main Execution Controller
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Serialize codebase for LLM context.")
    parser.add_argument("path", nargs="?", default=".", help="Root directory to scan")
    parser.add_argument("-o", "--output", default="codebase_context.md", help="Output file path")
    args = parser.parse_args()

    root_path = pathlib.Path(args.path).resolve()
    output_path = pathlib.Path(args.output).resolve()

    if not root_path.exists():
        logger.error(f"Path does not exist: {root_path}")
        sys.exit(1)

    logger.info(f"🚀 Starting scan of: {root_path}")
    
    # 1. Scan & Tree Generation
    scanner = ProjectScanner(root_path)
    
    # Generate the tree first (fast)
    logger.info("Building directory tree...")
    file_tree = scanner.generate_tree()
    
    # Collect files for processing
    logger.info("Collecting files...")
    files_to_process = list(scanner.scan())
    
    # Filter out the output file itself if it's inside the scan target
    files_to_process = [f for f in files_to_process if f.resolve() != output_path]

    logger.info(f"Found {len(files_to_process)} potential files.")

    # 2. Parallel Processing
    artifacts: List[FileArtifact] = []
    
    # Use ProcessPoolExecutor for CPU/IO mixed workload
    if files_to_process:
        print(f"Processing {len(files_to_process)} files using {MAX_WORKERS} workers...", file=sys.stderr)
        with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Create futures mapping
            future_to_file = {
                executor.submit(FileProcessor.process, f, root_path): f 
                for f in files_to_process
            }
            
            # Process as they complete
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_file):
                result = future.result()
                if result:
                    artifacts.append(result)
                completed_count += 1
                if completed_count % 10 == 0 or completed_count == len(files_to_process):
                    # Simple text progress bar
                    print(f"Progress: {completed_count}/{len(files_to_process)}", end='\r', file=sys.stderr)
        print("", file=sys.stderr) # Clear progress line

    # 3. Aggregation
    summary = ProjectSummary(
        total_files=len(artifacts),
        total_lines=sum(a.lines for a in artifacts),
        total_tokens=sum(a.token_estimate for a in artifacts),
        file_tree=file_tree,
        artifacts=artifacts
    )

    # 4. Generation
    report_content = ReportGenerator.generate(summary)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        logger.info(f"✅ Success! Output written to: {output_path}")
        logger.info(f"📊 Stats: {summary.total_files} files, {summary.total_lines} lines, ~{summary.total_tokens} tokens")
    except IOError as e:
        logger.error(f"Failed to write output: {e}")

if __name__ == "__main__":
    # Windows/MP support
    import multiprocessing
    multiprocessing.freeze_support()
    main()