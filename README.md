# 🚀 codecontexter

> A high-performance codebase serializer that generates structured Markdown summaries optimized for LLM context windows. Written in Rust for speed and safety.

[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange.svg)](https://www.rust-lang.org/)
[![Crates.io](https://img.shields.io/crates/v/clap.svg)](https://crates.io/crates/clap)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- **🔍 Smart Discovery**: Automatically respects `.gitignore` patterns using the robust `ignore` crate
- **🌲 Visual Trees**: Generates clean ASCII directory trees for easy navigation
- **⚡ Parallel Processing**: Multi-core file processing powered by Rayon for maximum performance
- **📏 Token Estimation**: Calculates approximate token counts to help manage context limits
- **🛡️ Safe Handling**: Automatically truncates large files (>1MB) and skips binary files
- **📝 Rich Markdown**: Syntax-highlighted code blocks with per-file metadata
- **🎯 LLM-Optimized**: Structured format designed specifically for AI assistant contexts
- **📊 Progress Tracking**: Real-time progress bars with `indicatif` for large codebases

## 📦 Installation

### From Source

Ensure you have Rust 1.70+ and Cargo installed.

```bash
# Clone the repository
git clone <repository-url>
cd codecontexter

# Build the release binary
cargo build --release

# The binary will be available at ./target/release/codecontexter
```

### Run Directly with Cargo

```bash
# Run without building separately
cargo run --release -- /path/to/your/project
```

## 🎯 Quick Start

### Basic Usage

Generate a markdown summary of your current directory:

```bash
./target/release/codecontexter
```

### Custom Output

Specify a different output file:

```bash
./target/release/codecontexter /path/to/your/project -o my_context.md
```

### Enable Verbose Logging

```bash
./target/release/codecontexter --verbose /path/to/project
```

### Command Options

```bash
./target/release/codecontexter --help
```

Output:
```
Serialize codebase for LLM context

Usage: codecontexter [OPTIONS] [PATH]

Arguments:
  [PATH]  Root directory to scan [default: .]

Options:
  -o, --output <OUTPUT>  Output file path [default: codebase_context.md]
  -v, --verbose Show verbose logging
  -h, --help Print help
  -V, --version Print version
```

## 📊 Example Output

Running `./target/release/codecontexter .` generates a `codebase_context.md` file with:

```markdown
# 📦 Codebase Context: my-project
> Generated on 2025-11-21 00:27:06 | Files: 42 | Tokens: ~15,230

## 🌲 Project Structure
```text
📂 my-project/
├── src/
│   └── main.rs
└── tests/
    └── test_main.rs
```

## 📄 File Contents

###`src/main.rs`
_Language: rust | Lines: 280 | Tokens: ~2,335_

```rust
use anyhow::Result;
use clap::Parser;

fn main() -> Result<()> {
    println!("Hello, Rust!");
    Ok(())
}
```

---
```

## 🔧 Configuration

### Language Support

The serializer automatically detects and highlights:
- **Systems**: Rust, C, C++, Go
- **Web**: JavaScript, TypeScript, HTML, CSS
- **JVM**: Java, Kotlin
- **Scripting**: Python, Bash, Lua, Ruby, PHP
- **Config**: JSON, YAML, TOML, XML, SQL
- **Docs**: Markdown, Dockerfiles, and more

### Ignore Patterns

The scanner automatically ignores:
- **Version control**: `.git`, `.svn`, `.hg`
- **Dependencies**: `node_modules`, `target/`, `vendor/`, `__pycache__`
- **Build artifacts**: `dist/`, `build/`, `*.class`, `*.jar`
- **Binary files**: `*.png`, `*.pdf`, `*.zip`, `*.exe`, `*.so`, `*.dll`
- **Lock files**: `package-lock.json`, `Cargo.lock`, `uv.lock`

**Custom patterns can be added to your `.gitignore` file— they will be respected automatically.**

### File Size Limits

- **Default limit**: 1MB per file
- Large files are truncated with a warning comment
- Binary files are automatically skipped using content detection

## 🏗️ Project Structure

```
codecontexter/
├── Cargo.toml # Rust project configuration
├── Cargo.lock # Dependency lock file
├── README.md # This file
├── .gitignore # Git ignore patterns
└── src/
    └── main.rs # Main application (~280 lines)
```

## 🛠️ Development

### Requirements

- Rust 1.70+ (or nightly for edition 2024)
- Cargo package manager

### Key Dependencies

- **[clap](https://docs.rs/clap)** - Derive-based CLI argument parsing
- **[ignore](https://docs.rs/ignore)** - Fast `.gitignore` application
- **[rayon](https://docs.rs/rayon)** - Data parallelism for concurrent file processing
- **[indicatif](https://docs.rs/indicatif)** - Progress bars and spinners
- **[anyhow](https://docs.rs/anyhow)** - Ergonomic error handling
- **[chrono](https://docs.rs/chrono)** - Date and time utilities

### Building and Testing

```bash
# Format code
cargo fmt

# Run linter
cargo clippy -- -D warnings

# Run debug build
cargo run -- /path/to/test/project

# Create release build
cargo build --release
```

## 📝 License

MIT

---

**Pro Tip**: Run this tool before asking an AI assistant for help with your codebase to provide complete context! The parallel processing makes it blazing fast even on large monorepos.