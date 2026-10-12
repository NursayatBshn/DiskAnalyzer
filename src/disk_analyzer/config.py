"""Application configuration schemas, loaders, and environment management."""

import os
from pathlib import Path
from typing import Any

import dotenv
import yaml
from pydantic import BaseModel, Field, ValidationError

from disk_analyzer.exceptions import ConfigError
from disk_analyzer.utils.formatting import mask_secret

DEFAULT_EXCLUDES = [
    "**/.git/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/.venv/**",
    "**/node_modules/**",
]


class GeneralConfig(BaseModel):
    """General execution settings."""

    top_items: int = Field(default=15, ge=1, le=500, description="Number of top items to report")
    max_depth: int | None = Field(
        default=None, ge=1, description="Maximum directory traversal depth"
    )
    follow_symlinks: bool = Field(default=False, description="Whether to follow symbolic links")
    quiet: bool = Field(
        default=False, description="Suppress progress output and decorative banners"
    )
    verbose: bool = Field(default=False, description="Output verbose diagnostic logs")


class ScannerConfig(BaseModel):
    """Filesystem scanner settings."""

    exclude: list[str] = Field(
        default_factory=lambda: list(DEFAULT_EXCLUDES),
        description="Glob patterns to exclude from scanning",
    )
    exclude_system_virtual_fs: bool = Field(
        default=True,
        description="Automatically exclude virtual filesystems (/proc, /sys, /dev, /run)",
    )


class AnalysisConfig(BaseModel):
    """Deterministic analysis settings."""

    classify_storage: bool = Field(
        default=True, description="Enable heuristic storage pattern classification"
    )
    top_extensions_count: int = Field(
        default=10, ge=1, le=100, description="Number of top extensions to report"
    )
    estimate_reclaimable: bool = Field(
        default=True, description="Calculate evidence-based reclaimable estimates when available"
    )


class AIConfig(BaseModel):
    """Google Gemini AI integration settings."""

    enabled: bool = Field(default=True, description="Enable AI summary generation")
    model: str = Field(default="gemini-3.8-flash", description="Gemini model identifier")
    timeout_seconds: float = Field(
        default=60.0, ge=1.0, le=600.0, description="API request timeout in seconds"
    )
    max_retries: int = Field(
        default=2, ge=0, le=10, description="Maximum retry count for transient API failures"
    )
    api_key: str | None = Field(
        default=None, description="Gemini API Key (loaded from GEMINI_API_KEY env)"
    )


class ReportingConfig(BaseModel):
    """Reporting and export options."""

    redact_paths: bool = Field(
        default=True, description="Redact user home directory prefixes from reports and prompts"
    )
    default_format: str = Field(
        default="terminal", description="Default report format: terminal, json, or markdown"
    )


class AppConfig(BaseModel):
    """Consolidated application configuration."""

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """Load and validate configuration from YAML file and environment variables.

    Loading order:
    1. Built-in defaults.
    2. .env file loaded into environment.
    3. YAML configuration file (explicit or auto-detected `config.yaml`).
    4. Explicit environment variables (GEMINI_API_KEY, GEMINI_MODEL, etc.).

    Args:
        config_path: Optional path to YAML configuration file.

    Returns:
        Validated AppConfig instance.

    Raises:
        ConfigError: If configuration parsing or validation fails.
    """
    # 1. Load local .env if available
    dotenv.load_dotenv()

    data: dict[str, Any] = {}

    # 2. Check for YAML file
    target_yaml: Path | None = None
    if config_path:
        target_yaml = Path(config_path)
        if not target_yaml.is_file():
            raise ConfigError(f"Specified configuration file not found: {target_yaml}")
    else:
        for candidate in [Path("config.yaml"), Path("config.yml")]:
            if candidate.is_file():
                target_yaml = candidate
                break

    if target_yaml:
        try:
            with open(target_yaml, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except yaml.YAMLError as exc:
            raise ConfigError(f"Error parsing YAML configuration in {target_yaml}: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Error reading configuration file {target_yaml}: {exc}") from exc

    # 3. Apply environment variables overrides
    ai_data = data.setdefault("ai", {})
    if not isinstance(ai_data, dict):
        ai_data = {}
        data["ai"] = ai_data

    env_api_key = os.getenv("GEMINI_API_KEY")
    if env_api_key:
        ai_data["api_key"] = env_api_key

    env_model = os.getenv("GEMINI_MODEL")
    if env_model:
        ai_data["model"] = env_model

    env_timeout = os.getenv("GEMINI_TIMEOUT_SECONDS")
    if env_timeout:
        try:
            ai_data["timeout_seconds"] = float(env_timeout)
        except ValueError as exc:
            raise ConfigError(
                f"Invalid GEMINI_TIMEOUT_SECONDS environment value: {env_timeout}"
            ) from exc

    env_retries = os.getenv("GEMINI_MAX_RETRIES")
    if env_retries:
        try:
            ai_data["max_retries"] = int(env_retries)
        except ValueError as exc:
            raise ConfigError(
                f"Invalid GEMINI_MAX_RETRIES environment value: {env_retries}"
            ) from exc

    # 4. Validate with Pydantic
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Configuration validation failed:\n{exc}") from exc


def get_safe_config_dict(config: AppConfig) -> dict[str, Any]:
    """Return a dictionary representation of configuration with sensitive secrets masked.

    Args:
        config: The AppConfig instance.

    Returns:
        Dictionary safe for logging and terminal display.
    """
    dump = config.model_dump()
    if "ai" in dump and isinstance(dump["ai"], dict):
        raw_key = dump["ai"].get("api_key")
        dump["ai"]["api_key"] = mask_secret(raw_key)
    return dump
