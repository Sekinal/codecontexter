# 🚀 codecontexter

> A simple codebase serializer that generates structured Markdown summaries optimized for LLM context windows.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

## ✨ Features

- **🔍 Smart Discovery**: Automatically respects`.gitignore` patterns and skips common build artifacts
- **🌲 Visual Trees**: Generates clean ASCII directory trees for easy navigation
- **⚡ Parallel Processing**: Multi-core file processing for maximum performance
- **📏 Token Estimation**: Calculates approximate token counts to help manage context limits
- **🛡️ Safe Handling**: Automatically truncates large files (>1MB) and skips binary files
- **📝 Rich Markdown**: Syntax-highlighted code blocks with per-file metadata
- **🎯 LLM-Optimized**: Structured format designed specifically for AI assistant contexts

## 📦 Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast Python package management:

```bash
# Clone the repository
git clone <repository-url>
cd codecontexter

# Install dependencies
uv sync
```

## 🎯 Quick Start

### Basic Usage

Generate a markdown summary of your current directory:

```bash
uv run app.py .
```

### Custom Output

Specify a different output file:

```bash
uv run app.py /path/to/your/project -o my_context.md
```

### Command Options

```bash
uv run app.py --help
```

Output:
```
Serialize codebase for LLM context.

positional arguments:
  path                  Root directory to scan (default: .)

options:
  -o, --output OUTPUT   Output file path (default: codebase_context.md)
```

## 📊 Example Output

Running`uv run app.py .` generates a`codebase_context.md` file with:

```markdown
# 📦 Codebase Context: my-project
> Generated on 2025-11-21 00:09:57 | Files: 42 | Tokens: ~15,230

## 🌲 Project Structure
📂 my-project/
├── src/
│   └── main.py
└── tests/
    └── test_main.py

## 📄 File Contents

### `src/main.py`
_Language: python | Lines: 150 | Tokens: ~1,200_

```python
def hello():
    print("Hello, World!")
```

---
```

## 🔧 Configuration

### Language Support

Automatically detects and highlights:
- Python, JavaScript, TypeScript, HTML, CSS
- Java, Kotlin, C, C++, Rust, Go
- JSON, YAML, TOML, XML, SQL
- Shell scripts, Dockerfiles, and more

### Ignore Patterns

The scanner automatically ignores:
- Version control:`.git`,`.svn`,`.hg`
- Dependencies:`node_modules`,`venv`,`__pycache__`
- Build artifacts:`dist`,`build`,`target`
- Binary files:`*.png`,`*.pdf`,`*.zip`,`*.exe`
- Lock files:`package-lock.json`,`uv.lock`

**You can add custom patterns to your`.gitignore` file.**

### File Size Limits

- **Default limit**: 1MB per file
- Large files are truncated to the last 1000 lines (usually the most recent content)
- Binary files are automatically skipped

## 🏗️ Project Structure

```
codecontexter/
├── app.py                 # Main application (395 lines)
├── pyproject.toml         # Project configuration
├── uv.lock               # Dependency lock file
├── README.md             # This file
└── *.md                  # Generated documentation
```

## 🛠️ Development

### Requirements

- Python 3.12+
- uv package manager
-`pathspec>=0.12.1` (auto-installed)

### Running Tests

The project uses parallel processing with`concurrent.futures` for optimal performance. The number of workers automatically scales to your CPU count.

## 📝 License

MIT

---

**Pro Tip**: Run this tool before asking an AI assistant for help with your codebase to provide complete context!