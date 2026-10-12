# Developer & Contribution Guide

## 1. Prerequisites

- Python 3.11 or newer (tested on Python 3.11, 3.12, 3.13, 3.14).
- Linux environment (Arch Linux / CachyOS, Ubuntu, Fedora, Debian).
- Git.

---

## 2. Environment Setup

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/example/ai-disk-analyzer.git
cd ai-disk-analyzer

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install package in editable mode with development dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Verify that the CLI entry point is functional:

```bash
disk-analyzer --version
disk-analyzer --help
```

---

## 3. Running Automated Tests

AI Disk Analyzer uses `pytest` and `pytest-cov` for testing:

```bash
# Run all tests with coverage
pytest

# Run specific test modules
pytest tests/test_scanner.py
pytest tests/test_gemini_provider.py
pytest tests/test_cli.py
```

All tests run hermetically using synthetic temporary directories and mocked API calls; no internet access or real Gemini credentials are required.

---

## 4. Code Quality & Linting

We enforce PEP 8 standards using `ruff`:

```bash
# Check code style and lint rules
ruff check src tests

# Check code formatting
ruff format --check src tests

# Automatically format code
ruff format src tests
```

---

## 5. Development Conventions

1. **Follow Workspace Rules**: Review `.agents/rules/*.md` before making code changes.
2. **Never Commit Secrets**: Ensure `.env` is never committed.
3. **Keep AI Decoupled**: Deterministic scanning and analysis logic must never depend on the Gemini SDK.
4. **Isolated Filesystem Tests**: Use `tmp_path` fixtures in tests. Never access real user home directories during unit tests.
5. **No Breaking Changes to Read-Only Invariants**: Never add destructive deletion logic.
