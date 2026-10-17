# AI Disk Analyzer Security & Privacy Policy

## 1. Security Principles

**AI Disk Analyzer** is engineered with strict read-only and privacy-first guarantees.

### Non-Destructive Operation
- **Strictly Read-Only**: The application never modifies, moves, renames, truncates, or deletes any files or directories on your system.
- **No Automatic Cleanup**: Suggestions provided by deterministic rules or Gemini are purely advisory. The utility does not perform automatic cache clearing or file deletion.
- **No Command Execution**: Shell commands suggested in AI summaries or recommendations are never executed automatically. They are never piped into `subprocess`, `os.system`, or any shell execution environment.
- **No Root Requirement**: Ordinary filesystem scans do not require `sudo` or elevated privileges. Inaccessible directories (e.g. system directories restricted to `root`) are recorded as diagnostic errors without crashing.

---

## 2. Privacy & Data Minimization

### What is Sent to Google Gemini:
When AI analysis is enabled, only aggregated statistical data is transmitted:
- Scan duration and total file/directory counts.
- Total aggregated logical size and allocated size.
- Top 10 largest files and top 10 largest directories, with **user home directories redacted** (e.g. `/home/username/project` -> `~/project`).
- Storage category totals and percentage shares (e.g. "Package Manager Caches: 250 MiB").
- File extension distributions (e.g. ".py: 45 files, 12 MiB").
- Deterministic heuristic observations.

### What is NEVER Sent to Google Gemini:
- **File Contents**: The analyzer only reads filesystem metadata via `stat` and `scandir`. File contents are never opened or read.
- **Usernames & Home Paths**: Home directory prefixes are redacted to `~` by default.
- **Full File Listings**: Entire directory trees are not dumped to the API.
- **Environment Variables & Credentials**: Secrets, API keys, and environment variables are strictly excluded from API prompts.
- **Document Names in Private Directories**: Only top-level aggregated summaries are included.

### Running Completely Offline (No-AI Mode):
If you do not wish to contact Google's API, use the `--no-ai` flag:
```bash
disk-analyzer scan ~/ --no-ai
```
In this mode, no network connections are opened, and all scanning and reporting are executed entirely locally.

---

## 3. Credential & Secret Management

- **API Key Storage**: The Google Gemini API key is read from the `GEMINI_API_KEY` environment variable or a local `.env` file via `python-dotenv`.
- **Git Exclusion**: `.env` is permanently listed in `.gitignore` to prevent accidental credential commits.
- **Secret Masking**: When viewing configuration with `disk-analyzer config`, keys are masked (e.g. `AIza...3f1a` or `(not set)`).
- **Log Sanitation**: Exception logs and diagnostic dumps never expose raw API keys.

---

## 4. Filesystem Safety Guardrails

- **Symlinks**: Symbolic links are not followed by default (`follow_symlinks=False`). If explicitly enabled, loop detection prevents infinite recursion.
- **Virtual Filesystems**: Paths under `/proc`, `/sys`, `/dev`, and `/run` are automatically skipped when traversing the filesystem root to avoid blocking on pseudo-files.
- **Report Writing**: Generated reports will not silently overwrite existing destination files unless the user explicitly passes `--overwrite`.

