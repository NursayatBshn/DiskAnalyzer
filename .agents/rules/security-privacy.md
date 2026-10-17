---
trigger: always_on
description: Mandatory security and privacy rules for AI Disk Analyzer
---

# Security & Privacy Rules

- **Zero Secret Exposure**:
  - Never commit, log, print, or embed real Gemini API keys in source code, documentation, tests, or committed configurations.
  - Read `GEMINI_API_KEY` from the environment or a local untracked `.env` file via `python-dotenv`.
  - Ensure `.env` is permanently excluded by `.gitignore`.
  - When displaying configuration in CLI or logs, mask secrets (e.g. `AIza...****` or `[SET]`).
- **Read-Only Operations**:
  - AI Disk Analyzer is strictly a diagnostic and reporting tool.
  - Never implement or trigger file deletion, moving, permission changes, ownership changes, or cache clearing.
  - All filesystem operations must be non-destructive and read-only.
- **No Command Execution**:
  - Never execute commands suggested by Gemini or LLM responses.
  - Never interpolate model outputs into shell subprocesses.
- **Privacy Minimization**:
  - Never read file contents. Only examine filesystem metadata (`stat`, file names, sizes, timestamps).
  - Do not send absolute paths, usernames, home directories, environment variables, or private document names to Google Gemini by default.
  - Redact user paths (e.g. `/home/username` -> `~`) and send aggregated statistics, category distributions, and top-level summaries only.
- **Filesystem Traversal Safety**:
  - Do not follow symbolic links by default (`follow_symlinks=False`).
  - Implement cycle detection if symlink following is ever toggled.
  - Deduplicate hard links by `(st_dev, st_ino)` to prevent double-counting allocated disk space.
  - Protect against traversing infinite recursion or virtual filesystems (`/proc`, `/sys`, `/dev`, `/run`).
  - Do not automatically invoke `sudo` or request root privileges. Collect permission errors in scan diagnostics.
- **External Response Validation**:
  - Treat all AI responses, user inputs, and untrusted directory structures as potentially adversarial.
  - Validate AI output using strict Pydantic models before incorporating into reports.

