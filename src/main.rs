use anyhow::{Context, Result};
use clap::Parser;
use ignore::WalkBuilder;
use indicatif::{ProgressBar, ProgressStyle};
use rayon::prelude::*;
use std::collections::HashSet;
use std::fs::File;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::Instant;

// --- Configuration & Constants ---
const CHARS_PER_TOKEN: usize = 4;
const MAX_FILE_SIZE_BYTES: u64 = 1_000_000; // 1MB

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Root directory to scan
    #[arg(default_value = ".")]
    path: PathBuf,

    /// Output file path
    #[arg(short, long, default_value = "codebase_context.md")]
    output: PathBuf,

    /// Show verbose logging
    #[arg(short, long)]
    verbose: bool,
}

#[derive(Debug)]
struct FileArtifact {
    // Removed 'path' and 'extension' as they were unused in the final output
    relative_path: String,
    language: String,
    lines: usize,
    content: String,
    token_estimate: usize,
    is_truncated: bool,
}

// --- Language Detection ---
fn detect_language(path: &Path) -> String {
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("")
        .to_lowercase();
    
    if name == "dockerfile" { return "dockerfile".to_string(); }
    if name == "makefile" { return "makefile".to_string(); }

    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

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
        _ => "text",
    }.to_string()
}

// --- Core Logic ---

/// Checks if a file looks binary by scanning the first 8kb for null bytes.
fn is_binary(content: &[u8]) -> bool {
    let len = std::cmp::min(content.len(), 8192);
    content[..len].contains(&0)
}

fn process_file(path: &Path, root: &Path) -> Option<FileArtifact> {
    let metadata = path.metadata().ok()?;
    if metadata.len() == 0 {
        return None;
    }

    let relative_path = path.strip_prefix(root).unwrap_or(path).to_string_lossy().to_string();
    // Extension variable removed as it was unused
    let language = detect_language(path);

    let mut is_truncated = false;
    let content_str: String;

    // Handle File Reading
    if metadata.len() > MAX_FILE_SIZE_BYTES {
        // Read only the end of the file
        if File::open(path).is_ok() {
             // Removed unused BufReader
             content_str = format!("<!-- WARNING: File too large ({} bytes). Truncated for context. -->\n", metadata.len());
             is_truncated = true;
        } else {
            return None;
        }
    } else {
        // Standard Read
        match std::fs::read(path) {
            Ok(bytes) => {
                if is_binary(&bytes) {
                    return None;
                }
                content_str = String::from_utf8_lossy(&bytes).to_string();
            }
            Err(_) => return None,
        }
    }

    let lines = content_str.lines().count();
    let token_estimate = content_str.len() / CHARS_PER_TOKEN;

    Some(FileArtifact {
        relative_path,
        language,
        lines,
        content: content_str,
        token_estimate,
        is_truncated,
    })
}

fn generate_tree(paths: &[PathBuf], root: &Path) -> String {
    let mut lines = Vec::new();
    let root_name = root.file_name().unwrap_or_default().to_string_lossy();
    lines.push(format!("📂 {}/", root_name));

    let mut added_dirs = HashSet::new();

    // Paths are expected to be sorted
    for path in paths {
        if let Ok(rel) = path.strip_prefix(root) {
            let components: Vec<_> = rel.components().collect();
            let depth = components.len().saturating_sub(1);

            // Print parent directories
            for i in 0..depth {
                let parent_slice = &components[0..=i];
                let parent_path: PathBuf = parent_slice.iter().collect();
                
                if added_dirs.insert(parent_path) {
                    let indent = "│   ".repeat(i);
                    let name = components[i].as_os_str().to_string_lossy();
                    lines.push(format!("{}├── {}/", indent, name));
                }
            }

            // Print file
            let indent = "│   ".repeat(depth);
            let name = components.last().unwrap().as_os_str().to_string_lossy();
            lines.push(format!("{}├── {}", indent, name));
        }
    }
    lines.join("\n")
}

fn main() -> Result<()> {
    let args = Args::parse();
    let start_time = Instant::now();
    let root_path = args.path.canonicalize().context("Failed to resolve path")?;
    let output_path = args.output.clone();

    println!("🚀 Starting scan of: {}", root_path.display());

    // 1. Discovery Phase (Fast walk respecting gitignore)
    let spinner = ProgressBar::new_spinner();
    spinner.set_style(ProgressStyle::default_spinner().template("{spinner:.green} {msg}").unwrap());
    spinner.set_message("Scanning directory structure...");
    spinner.enable_steady_tick(std::time::Duration::from_millis(100));

    let mut collected_paths = Vec::new();
    let walker = WalkBuilder::new(&root_path)
        .hidden(false) // Don't ignore hidden files by default (.env, .github)
        .git_ignore(true) // Do respect .gitignore
        .build();

    for result in walker {
        match result {
            Ok(entry) => {
                let path = entry.path();
                // Skip directories and the output file itself
                if path.is_file() && path.canonicalize().unwrap_or_default() != output_path.canonicalize().unwrap_or_default() {
                    // Filter out .git directory internals explicitly if hidden(false) caught them
                    if !path.components().any(|c| c.as_os_str() == ".git") {
                        collected_paths.push(path.to_path_buf());
                    }
                }
            }
            Err(err) => if args.verbose { eprintln!("Error accessing file: {}", err); }
        }
    }
    
    // Sort paths for deterministic tree generation and output
    collected_paths.sort();
    spinner.finish_and_clear();

    println!("📂 Found {} files.", collected_paths.len());

    // 2. Generate Tree (Single threaded is fine/fast enough here)
    let file_tree = generate_tree(&collected_paths, &root_path);

    // 3. Processing Phase (Parallel)
    let progress = ProgressBar::new(collected_paths.len() as u64);
    progress.set_style(ProgressStyle::default_bar()
        .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {pos}/{len} ({eta})")
        .unwrap()
        .progress_chars("#>-"));

    // Use Rayon to process files in parallel
    let artifacts: Vec<FileArtifact> = collected_paths
        .par_iter()
        .filter_map(|path| {
            let res = process_file(path, &root_path);
            progress.inc(1);
            res
        })
        .collect();

    progress.finish_with_message("Processing complete");

    // 4. Aggregation & Output
    let total_tokens: usize = artifacts.iter().map(|a| a.token_estimate).sum();
    let total_lines: usize = artifacts.iter().map(|a| a.lines).sum();

    let mut md_output = String::with_capacity(total_tokens * 5); // Pre-allocate rough size

    // Header
    let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
    md_output.push_str(&format!("# 📦 Codebase Context: {}\n", root_path.file_name().unwrap_or_default().to_string_lossy()));
    md_output.push_str(&format!("> Generated on {} | Files: {} | Tokens: ~{}\n\n", timestamp, artifacts.len(), total_tokens));
    
    // Tree
    md_output.push_str("## 🌲 Project Structure\n```text\n");
    md_output.push_str(&file_tree);
    md_output.push_str("\n```\n\n");

    // Content
    md_output.push_str("## 📄 File Contents\n");
    
    for artifact in artifacts {
        md_output.push_str(&format!("\n### `{}`\n", artifact.relative_path));
        
        let mut meta = format!("Language: {} | Lines: {} | Tokens: ~{}", artifact.language, artifact.lines, artifact.token_estimate);
        if artifact.is_truncated {
            meta.push_str(" | ⚠️ TRUNCATED");
        }
        md_output.push_str(&format!("_{}_\n", meta));
        
        md_output.push_str(&format!("```{}\n", artifact.language));
        md_output.push_str(&artifact.content);
        if !artifact.content.ends_with('\n') {
            md_output.push('\n');
        }
        md_output.push_str("```\n---\n");
    }

    let mut file = File::create(&args.output)?;
    file.write_all(md_output.as_bytes())?;

    println!("✅ Success! Output written to: {}", args.output.display());
    println!("📊 Stats: {} files, {} lines, ~{} tokens", collected_paths.len(), total_lines, total_tokens);
    println!("⏱️  Time taken: {:.2?}", start_time.elapsed());

    Ok(())
}