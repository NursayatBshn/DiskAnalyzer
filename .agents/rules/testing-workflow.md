---
trigger: always_on
description: Testing workflow and quality assurance standards
---

# Testing Workflow & QA Standards

- **Automated Test Suite**:
  - Run `pytest` and `ruff check` after every meaningful code change and before finalizing work.
  - Maintain high test coverage across domain logic, filesystem scanning, heuristic analysis, AI orchestration, reporting, and CLI interfaces.
- **Isolated Synthetic Filesystem Testing**:
  - Use `pytest`'s `tmp_path` fixture to construct synthetic directories and test files.
  - Never scan or modify real user files or system directories during tests.
  - Test boundary conditions: empty directories, single files, deeply nested trees, symlinks, broken symlinks, hardlinks, unicode names, filenames with spaces, simulated permission errors, and disappearing files.
- **Hermetic AI Testing**:
  - Mock all `google-genai` SDK interactions in tests.
  - Never make outbound network requests or require a real `GEMINI_API_KEY` to run test suites.
  - Explicitly test AI failure modes: missing credentials, 401 unauthorized, 429 rate limit, 504 timeout, connection errors, empty replies, and malformed JSON payloads.
  - Verify that deterministic scanning and analysis succeed even when AI fails.
- **CLI & Reporting Verification**:
  - Test CLI subcommands (`scan`, `analyze`, `config`, `check-ai`, `--version`) via Typer's `CliRunner`.
  - Validate JSON serialization schemas and Markdown generation against expected outputs.
  - Test path redaction and safe report writing (preventing accidental overwrites).
- **Verification Integrity**:
  - Report genuine measured test results and coverage numbers. Never fabricate or guess percentages.
  - Keep the GitHub Actions CI workflow in sync with local testing commands.
