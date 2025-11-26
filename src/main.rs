use anyhow::{Context, Result};
use clap::{Parser, ValueEnum};
use ignore::{overrides::OverrideBuilder, WalkBuilder};
use indicatif::{ProgressBar, ProgressStyle};
use rayon::prelude::*;
use regex::Regex;
use serde::Serialize;
use std::collections::HashSet;
use std::fs::File;
use std::io::{self, BufWriter, Write}; // Added BufWriter
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::Instant;

// --- Configuration & Constants ---
const CHARS_PER_TOKEN: usize = 4;
const MAX_FILE_SIZE_BYTES: u64 = 1_000_000; // 1MB Limit for full context

#[derive(ValueEnum, Clone, Debug, PartialEq)]
enum OutputFormat {
    Markdown,
    Json,
    Xml,
}

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Root directory to scan
    #[arg(default_value = ".")]
    path: PathBuf,

    /// Output file path
    #[arg(short, long, default_value = "codebase_context.md")]
    output: PathBuf,

    /// Output format (t for Type)
    #[arg(short = 't', long, value_enum, default_value_t = OutputFormat::Markdown)]
    format: OutputFormat,

    /// Copy result to clipboard
    #[arg(short, long)]
    clipboard: bool,

    /// Exclude file patterns (glob), e.g. --exclude "*.log"
    #[arg(short = 'e', long)]
    exclude: Vec<String>,

    /// Force overwrite of output file if it exists
    #[arg(short = 'f', long)]
    force: bool,

    /// Show verbose logging
    #[arg(short, long)]
    verbose: bool,
}

#[derive(Debug, Serialize)]
struct FileArtifact {
    relative_path: String,
    language: String,
    lines: usize,
    content: String,
    token_estimate: usize,
    is_truncated: bool,
}

#[derive(Serialize)]
struct CodebaseResult<'a> {
    metadata: Metadata,
    project_tree: &'a str,
    files: &'a [FileArtifact],
}

#[derive(Serialize)]
struct Metadata {
    root_path: String,
    generated_at: String,
    total_files: usize,
    total_tokens: usize,
    total_lines: usize,
}

// --- Safety & Security Logic ---

fn check_output_safety(output_path: &Path, force: bool) -> Result<()> {
    if output_path.exists() && !force {
        eprintln!("⚠️  Output file already exists: {}", output_path.display());
        eprint!("   Overwrite? [y/N]: ");
        io::stdout().flush()?;
        
        let mut input = String::new();
        io::stdin().read_line(&mut input)?;
        
        if !input.trim().eq_ignore_ascii_case("y") {
            eprintln!("❌ Aborted by user.");
            std::process::exit(0);
        }
    }
    Ok(())
}

fn sanitize_content(content: &str) -> String {
    static SECRET_PATTERNS: OnceLock<Vec<Regex>> = OnceLock::new();
    let patterns = SECRET_PATTERNS.get_or_init(|| vec![
        Regex::new(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----").unwrap(),
        Regex::new(r"AKIA[0-9A-Z]{16}").unwrap(),
        Regex::new(r"(?i)sk-[a-zA-Z0-9]{20,}").unwrap(),
        Regex::new(r"gh[pousr]-[a-zA-Z0-9]{36}").unwrap(),
        Regex::new(r#"(?i)(api_key|secret|token|password)\s*[:=]\s*["'][a-zA-Z0-9]{32,}["']"#).unwrap(),
    ]);

    let mut sanitized = content.to_string();
    for regex in patterns {
        sanitized = regex.replace_all(&sanitized, "[REDACTED SECRET]").to_string();
    }
    sanitized
}

// --- Language Detection ---
fn detect_language(path: &Path) -> String {
    let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("").to_lowercase();
    if name == "dockerfile" { return "dockerfile".to_string(); }
    if name == "makefile" { return "makefile".to_string(); }

    let ext = path.extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
    match ext.as_str() {
        "py" | "pyi" | "pyx" => "python",
        "js" | "jsx" => "javascript",
        "ts" | "tsx" => "typescript",
        "html" => "html",
        "css" | "scss" => "css",
        "rs" => "rust",
        "go" => "go",
        "java" => "java",
        "c" | "h" => "c",
        "cpp" | "hpp" => "cpp",
        "sh" | "bash" => "bash",
        "md" => "markdown",
        "json" => "json",
        "toml" => "toml",
        "yaml" | "yml" => "yaml",
        "sql" => "sql",
        "xml" => "xml",
        _ => "text",
    }.to_string()
}

// --- Core Logic ---

fn is_binary(content: &[u8]) -> bool {
    let len = std::cmp::min(content.len(), 8192);
    content[..len].contains(&0)
}

// UPDATED: Now returns Result to track errors, handles head/tail for large files, filters whitespace
fn process_file(path: &Path, root: &Path) -> Result<Option<FileArtifact>, String> {
    let metadata = path.metadata().map_err(|e| e.to_string())?;
    
    if metadata.len() == 0 {
        return Ok(None);
    }

    let relative_path = path.strip_prefix(root).unwrap_or(path).to_string_lossy().to_string();
    let language = detect_language(path);

    let mut is_truncated = false;
    let mut content_str: String;

    // 2. Large File Head/Tail Reading
    if metadata.len() > MAX_FILE_SIZE_BYTES {
        // Try to read as UTF-8 to get context
        match std::fs::read_to_string(path) {
            Ok(full_content) => {
                let lines: Vec<&str> = full_content.lines().collect();
                if lines.len() > 100 {
                    let head = lines[..50].join("\n");
                    let tail = lines[lines.len().saturating_sub(50)..].join("\n");
                    content_str = format!(
                        "<!-- TRUNCATED: File too large ({} bytes). Showing first 50 and last 50 lines. -->\n{}\n\n... [{} lines omitted] ...\n\n{}", 
                        metadata.len(), head, lines.len().saturating_sub(100), tail
                    );
                } else {
                    // Large size but few lines (very long lines?), just truncate message
                     content_str = format!("<!-- WARNING: File too large ({} bytes). Truncated. -->\n", metadata.len());
                }
                is_truncated = true;
            }
            Err(_) => {
                // If read_to_string fails (likely binary or encoding issue), skip
                return Ok(None);
            }
        }
    } else {
        // Normal file processing
        match std::fs::read(path) {
            Ok(bytes) => {
                if is_binary(&bytes) {
                    return Ok(None);
                }
                content_str = String::from_utf8_lossy(&bytes).to_string();
            }
            Err(e) => return Err(e.to_string()),
        }
    }

    // 4. Whitespace-Only Filter
    if content_str.trim().is_empty() {
        return Ok(None);
    }

    // Sanitize content (Redact secrets)
    // If truncated, we sanitized the parts we kept. If not, sanitize all.
    content_str = sanitize_content(&content_str);

    let lines = content_str.lines().count();
    let token_estimate = content_str.len() / CHARS_PER_TOKEN;

    Ok(Some(FileArtifact {
        relative_path,
        language,
        lines,
        content: content_str,
        token_estimate,
        is_truncated,
    }))
}

fn generate_tree(paths: &[PathBuf], root: &Path) -> String {
    let mut lines = Vec::new();
    let root_name = root.file_name().unwrap_or_default().to_string_lossy();
    lines.push(format!("📂 {}/", root_name));

    let mut added_dirs = HashSet::new();

    for path in paths {
        if let Ok(rel) = path.strip_prefix(root) {
            let components: Vec<_> = rel.components().collect();
            if components.is_empty() { continue; } // Handle root file case

            let depth = components.len().saturating_sub(1);

            for i in 0..depth {
                let parent_slice = &components[0..=i];
                let parent_path: PathBuf = parent_slice.iter().collect();
                
                if added_dirs.insert(parent_path) {
                    let indent = "│   ".repeat(i);
                    let name = components[i].as_os_str().to_string_lossy();
                    lines.push(format!("{}├── {}/", indent, name));
                }
            }

            let indent = "│   ".repeat(depth);
            let name = components.last().unwrap().as_os_str().to_string_lossy();
            lines.push(format!("{}├── {}", indent, name));
        }
    }
    lines.join("\n")
}

fn escape_xml(input: &str) -> String {
    input.replace('&', "&amp;")
         .replace('<', "&lt;")
         .replace('>', "&gt;")
         .replace('"', "&quot;")
         .replace('\'', "&apos;")
}

fn main() -> Result<()> {
    let args = Args::parse();
    
    // --- Security: Check output path safety ---
    let output_path_abs = if args.output.is_absolute() {
        args.output.clone()
    } else {
        std::env::current_dir()?.join(&args.output)
    };
    check_output_safety(&output_path_abs, args.force)?;

    let start_time = Instant::now();
    let root_path = args.path.canonicalize().context("Failed to resolve path")?;

    println!("🚀 Starting scan of: {}", root_path.display());

    // 1. Setup Excludes & Discovery
    let spinner = ProgressBar::new_spinner();
    spinner.set_style(ProgressStyle::default_spinner().template("{spinner:.green} {msg}").unwrap());
    spinner.set_message("Scanning directory structure...");
    spinner.enable_steady_tick(std::time::Duration::from_millis(100));

    let mut override_builder = OverrideBuilder::new(&root_path);
    let hard_coded_excludes = vec!["!*.env", "!*.env.*", "!*.pem", "!*.key", "!id_rsa", "!id_ed25519", "!*.p12", "!*.pfx"];

    for pattern in hard_coded_excludes {
        override_builder.add(pattern).context("Failed to add security exclude")?;
    }
    for pattern in &args.exclude {
        override_builder.add(&format!("!{}", pattern)).context("Invalid exclude pattern")?;
    }
    
    let overrides = override_builder.build().context("Failed to build exclude overrides")?;

    let mut collected_paths = Vec::new();
    // 3. Symlink Handling: explicitly disable following links
    let walker = WalkBuilder::new(&root_path)
        .hidden(false) 
        .git_ignore(true)
        .follow_links(false) // FIX: Prevent symlink loops/duplication
        .overrides(overrides) 
        .build();

    for result in walker {
        match result {
            Ok(entry) => {
                let path = entry.path();
                if path.is_file() {
                    // Self-ignore check
                    if let Ok(canon) = path.canonicalize() {
                        if canon == output_path_abs { continue; }
                    }
                    if !path.components().any(|c| c.as_os_str() == ".git") {
                        collected_paths.push(path.to_path_buf());
                    }
                }
            }
            Err(err) => if args.verbose { eprintln!("Error accessing file: {}", err); }
        }
    }
    
    collected_paths.sort();
    spinner.finish_and_clear();
    println!("📂 Found {} files.", collected_paths.len());

    // 2. Generate Tree
    let file_tree = generate_tree(&collected_paths, &root_path);

    // 3. Processing Phase (Parallel)
    let progress = ProgressBar::new(collected_paths.len() as u64);
    progress.set_style(ProgressStyle::default_bar()
        .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {pos}/{len} ({eta})")
        .unwrap()
        .progress_chars("#>-"));

    // 5. Better Error Tracking
    // We first map to a tuple of (path, result) to separate errors later
    let results: Vec<_> = collected_paths
        .par_iter()
        .map(|path| {
            let res = process_file(path, &root_path);
            progress.inc(1);
            (path, res)
        })
        .collect();
    progress.finish_with_message("Processing complete");

    let mut artifacts = Vec::with_capacity(results.len());
    let mut errors = Vec::new();

    for (path, res) in results {
        match res {
            Ok(Some(artifact)) => artifacts.push(artifact),
            Ok(None) => {} // Skipped (binary, empty, etc.)
            Err(e) => errors.push(format!("{}: {}", path.display(), e)),
        }
    }

    if !errors.is_empty() && args.verbose {
        eprintln!("⚠️  Encountered {} errors:", errors.len());
        for err in errors.iter().take(10) {
            eprintln!("   - {}", err);
        }
        if errors.len() > 10 { eprintln!("   ... and {} more.", errors.len() - 10); }
    }

    // 4. Aggregation & Output Streaming
    let total_tokens: usize = artifacts.iter().map(|a| a.token_estimate).sum();
    let total_lines: usize = artifacts.iter().map(|a| a.lines).sum();
    let total_files = artifacts.len();
    let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

    let file = File::create(&args.output)?;
    // 1. Memory Management: Use BufWriter to stream output
    let mut writer = BufWriter::new(file);

    match args.format {
        OutputFormat::Markdown => {
            writeln!(writer, "# 📦 Codebase Context: {}", root_path.file_name().unwrap_or_default().to_string_lossy())?;
            writeln!(writer, "> Generated on {} | Files: {} | Tokens: ~{}\n", timestamp, total_files, total_tokens)?;
            writeln!(writer, "## 🌲 Project Structure\n```text\n{}\n```\n", file_tree)?;
            writeln!(writer, "## 📄 File Contents")?;
            
            for artifact in &artifacts {
                writeln!(writer, "\n### `{}`", artifact.relative_path)?;
                let mut meta = format!("Language: {} | Lines: {} | Tokens: ~{}", artifact.language, artifact.lines, artifact.token_estimate);
                if artifact.is_truncated { meta.push_str(" | ⚠️ TRUNCATED"); }
                writeln!(writer, "_{}_\n```{}", meta, artifact.language)?;
                writer.write_all(artifact.content.as_bytes())?;
                if !artifact.content.ends_with('\n') { writeln!(writer)?; }
                writeln!(writer, "```\n---")?;
            }
        },
        OutputFormat::Json => {
            // Streaming JSON using Serde
            let result = CodebaseResult {
                metadata: Metadata {
                    root_path: root_path.to_string_lossy().to_string(),
                    generated_at: timestamp,
                    total_files,
                    total_tokens,
                    total_lines,
                },
                project_tree: &file_tree,
                files: &artifacts,
            };
            serde_json::to_writer_pretty(&mut writer, &result)?;
        },
        OutputFormat::Xml => {
            writeln!(writer, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<codebase>")?;
            writeln!(writer, "  <metadata>\n    <root_path>{}</root_path>", escape_xml(&root_path.to_string_lossy()))?;
            writeln!(writer, "    <generated_at>{}</generated_at>", timestamp)?;
            writeln!(writer, "    <total_files>{}</total_files>", total_files)?;
            writeln!(writer, "    <total_tokens>{}</total_tokens>\n  </metadata>", total_tokens)?;
            
            writeln!(writer, "  <project_tree>\n{}\n  </project_tree>", escape_xml(&file_tree))?;
            
            writeln!(writer, "  <files>")?;
            for artifact in &artifacts {
                writeln!(writer, "    <file>")?;
                writeln!(writer, "      <path>{}</path>", escape_xml(&artifact.relative_path))?;
                writeln!(writer, "      <language>{}</language>", escape_xml(&artifact.language))?;
                writeln!(writer, "      <lines>{}</lines>", artifact.lines)?;
                writeln!(writer, "      <tokens>{}</tokens>", artifact.token_estimate)?;
                if artifact.is_truncated { writeln!(writer, "      <truncated>true</truncated>")?; }
                writeln!(writer, "      <content>{}</content>", escape_xml(&artifact.content))?;
                writeln!(writer, "    </file>")?;
            }
            writeln!(writer, "  </files>\n</codebase>")?;
        }
    }
    
    writer.flush()?;

    println!("✅ Success! Output written to: {}", args.output.display());
    println!("📊 Stats: {} files, {} lines, ~{} tokens", total_files, total_lines, total_tokens);

    if args.clipboard {
        // For clipboard, we still need to read the file back or reconstruct the string. 
        // Since we streamed to file to save RAM, let's read the file back *if* the user wants clipboard.
        // This keeps the happy path (no clipboard) low memory.
        match std::fs::read_to_string(&args.output) {
            Ok(content) => {
                match arboard::Clipboard::new() {
                    Ok(mut clipboard) => {
                        if let Err(e) = clipboard.set_text(content) {
                            eprintln!("⚠️  Failed to copy to clipboard: {}", e);
                        } else {
                            println!("📋 Content copied to clipboard!");
                        }
                    },
                    Err(e) => eprintln!("⚠️  Failed to initialize clipboard: {}", e),
                }
            },
            Err(e) => eprintln!("⚠️  Failed to read output file for clipboard: {}", e),
        }
    }

    println!("⏱️  Time taken: {:.2?}", start_time.elapsed());
    Ok(())
}