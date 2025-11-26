# 📦 CodeContexter

**CodeContexter** is a lightning-fast, safety-first CLI tool written in Rust. It aggregates your entire codebase into a single, structured file (Markdown, JSON, or XML). 

It is designed specifically for **providing context to Large Language Models (LLMs)** like ChatGPT, Claude, and GitHub Copilot without manual copy-pasting.

![Rust](https://img.shields.io/badge/built_with-Rust-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

## 🚀 Why CodeContexter?

When working with LLMs, you often need to share multiple files to explain a problem. Copying them one by one is tedious and prone to missing context. 

CodeContexter:
1.  **Walks your directory** (respecting `.gitignore`).
2.  **Generates a visual tree** of your project structure.
3.  **Aggregates file contents** into a single formatted output.
4.  **Redacts secrets** automatically to keep your keys safe.

## ✨ Key Features

-   **⚡ High Performance:** Parallel processing (Rayon) and streaming output for low memory usage on huge repos.
-   **🛡️ Security First:** Automatically detects and redacts private keys, API tokens, and secrets before they leave your machine.
-   **🧠 Smart Filtering:** Respects `.gitignore`, skips binary files, ignores whitespace-only files, and prevents symlink loops.
-   **📏 Large File Handling:** Smartly truncates files over 1MB (shows the first and last 50 lines) to preserve token limits while keeping context.
-   **📋 Clipboard Ready:** Optional flag to copy the output directly to your clipboard.
-   **🎨 Multiple Formats:** Output to **Markdown** (default), **JSON**, or **XML**.

## 🛠️ Installation

### From Source
Ensure you have Rust and Cargo installed.

```bash
# Clone the repository
git clone https://github.com/yourusername/codecontexter.git
cd codecontexter

# Install locally
cargo install --path .
```

## 📖 Usage

Navigate to your project root and run:

```bash
codecontexter
```

This generates a `codebase_context.md` file in the current directory.

### Common Options

**Copy directly to clipboard:**
```bash
codecontexter --clipboard
```

**Change output format (Markdown, JSON, XML):**
*Note: Use `-t` for format (type).*
```bash
codecontexter -t json --output context.json
```

**Exclude specific patterns:**
```bash
codecontexter --exclude "*.lock" --exclude "tests/*"
```

**Point to a specific directory:**
```bash
codecontexter ./src/my_component
```

### Full Help
```text
Usage: codecontexter [OPTIONS] [PATH]

Arguments:
  [PATH]  Root directory to scan [default: .]

Options:
  -o, --output <OUTPUT>    Output file path [default: codebase_context.md]
  -t, --format <FORMAT>    Output format [default: markdown] [possible values: markdown, json, xml]
  -c, --clipboard          Copy result to clipboard
  -e, --exclude <EXCLUDE>  Exclude file patterns (glob), e.g. --exclude "*.log"
  -f, --force              Force overwrite of output file if it exists
  -v, --verbose            Show verbose logging
  -h, --help               Print help
  -V, --version            Print version
```

## 📄 Output Example (Markdown)

The generated file looks like this, optimized for LLM prompting:

```markdown
# 📦 Codebase Context: my-project
> Generated on 2023-10-27 | Files: 12 | Tokens: ~4500

## 🌲 Project Structure
📂 my-project/
├── Cargo.toml
├── src/
│   ├── main.rs
│   ├── utils.rs

## 📄 File Contents

### `src/main.rs`
_Language: rust | Lines: 150 | Tokens: ~800_
```rust
fn main() {
    println!("Hello, world!");
}
```
---
```

## 🔒 Security & Redaction

CodeContexter includes a built-in sanitizer that scans file contents for sensitive patterns before writing to the output. It looks for and redacts:

*   RSA/DSA Private Keys
*   AWS Access Keys (`AKIA...`)
*   OpenAI/Stripe Keys (`sk-...`)
*   GitHub Personal Access Tokens
*   Generic "API Key" / "Secret" string assignments

*Note: While this feature catches common secrets, always review your output before sharing it with third-party AI services.*

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the repo
2.  Create your feature branch (`git checkout -b feature/amazing-feature`)
3.  Commit your changes (`git commit -m 'Add some amazing feature'`)
4.  Push to the branch (`git push origin feature/amazing-feature`)
5.  Open a Pull Request

## 📜 License

Distributed under the MIT License.