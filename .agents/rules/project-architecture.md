---
trigger: always_on
description: Permanent architectural constraints for AI Disk Analyzer
---

# Architectural Constraints

- **Python Version & Packaging**: Target Python 3.11+ using a clean `src/`-based package layout (`src/disk_analyzer`).
- **Target Platform**: Linux-first command-line utility (Arch Linux, CachyOS, Ubuntu, Debian, Fedora, and portable Linux). Avoid introducing Windows-specific constraints or breaking portable design.
- **LLM Integration**: Google Gemini API is the sole planned LLM integration. Use the official `google-genai` Python SDK (`from google import genai`).
- **No Local LLMs**: Never introduce Ollama, llama.cpp, or local language models.
- **Separation of Concerns**:
  - `scanner`: Pure recursive filesystem traversal, metadata collection, symlink & hardlink handling, exclusion filtering, and error diagnostics.
  - `analysis`: Deterministic statistics, directory/file rankings, extension breakdown, heuristic categorization, and rule-based cleanup recommendations.
  - `ai`: Gemini client, prompt engineering, structured response validation, and AI summary orchestration.
  - `reporting`: Terminal (Rich), JSON, and Markdown report rendering.
  - `cli`: Typer interface wiring commands, flags, and configuration.
  - `config`: Configuration loading, validation, and defaults.
- **Independence from AI**: The core scanner and deterministic analysis engine MUST function completely without Gemini API access or credentials.
- **No Feature Stubs**: Never leave required features as empty placeholders, `pass` stubs, or unverified claims.
- **Dependencies**: Keep dependencies minimal and justified (Typer, Rich, google-genai, Pydantic, PyYAML, python-dotenv). Prefer standard library modules for filesystem operations.
- **Code Preservation**: Preserve existing working code when modifying or refactoring. Avoid circular imports and bloated modules.

