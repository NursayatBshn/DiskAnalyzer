---
trigger: glob
globs:
  - "**/*.py"
description: Python code quality, typing, and style rules
---

# Python Code Quality Rules

- **Code Style & Formatting**: Follow PEP 8 and adhere to Ruff rules configured in `pyproject.toml`. Code must format cleanly and pass linting with zero warnings or errors.
- **Type Annotations**: Provide explicit type hints for all public functions, methods, and domain models. Avoid untyped `Any` unless interfacing with dynamic external boundaries.
- **Modularity & Complexity**: Keep functions small, single-purpose, and easy to reason about. Cyclomatic complexity should remain low.
- **Standard Library Utilization**: Use Python standard library modules (`pathlib`, `os`, `sys`, `shutil`, `stat`, `dataclasses`, `typing`) whenever possible rather than pulling in external dependencies.
- **Explicit Error Handling**: Catch specific exceptions. Never use bare `except:` or suppress unexpected errors silently. When capturing filesystem or API errors, record them in structured diagnostics.
- **Path Manipulation**: Use `pathlib.Path` or `os.scandir` safely. Normalise and resolve paths appropriately while preserving user perspective for reporting.
- **Pydantic Validation**: Use Pydantic models for configuration, AI response schemas, and exported data structures to guarantee type safety and schema validation.
- **Documentation**: Write clear docstrings for all modules, public classes, and functions. Maintain existing documentation integrity.
