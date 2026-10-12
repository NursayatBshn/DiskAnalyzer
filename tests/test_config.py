"""Unit tests for configuration schemas, loading, and environment overrides."""

from pathlib import Path
from unittest.mock import patch

import pytest

from disk_analyzer.config import (
    AppConfig,
    get_safe_config_dict,
    load_config,
)
from disk_analyzer.exceptions import ConfigError


def test_default_config():
    """Verify default AppConfig initialization."""
    cfg = AppConfig()
    assert cfg.general.top_items == 15
    assert cfg.general.follow_symlinks is False
    assert cfg.ai.model == "gemini-3.8-flash"
    assert cfg.reporting.redact_paths is True


def test_load_config_from_valid_yaml(tmp_path: Path):
    """Verify loading and overriding from YAML file."""
    yaml_file = tmp_path / "custom_config.yaml"
    yaml_file.write_text(
        """
general:
  top_items: 25
  follow_symlinks: true
ai:
  model: "gemini-2.0-flash"
  timeout_seconds: 45
"""
    )
    cfg = load_config(yaml_file)
    assert cfg.general.top_items == 25
    assert cfg.general.follow_symlinks is True
    assert cfg.ai.model == "gemini-2.0-flash"
    assert cfg.ai.timeout_seconds == 45.0


def test_load_config_nonexistent_file(tmp_path: Path):
    """Verify ConfigError when explicit configuration file is not found."""
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does_not_exist.yaml")


def test_load_config_malformed_yaml(tmp_path: Path):
    """Verify ConfigError on invalid YAML syntax."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("general: [unclosed list")
    with pytest.raises(ConfigError):
        load_config(bad_yaml)


def test_load_config_env_overrides():
    """Verify environment variables override defaults."""
    env = {
        "GEMINI_API_KEY": "secret-test-key",
        "GEMINI_MODEL": "custom-model",
        "GEMINI_TIMEOUT_SECONDS": "120",
        "GEMINI_MAX_RETRIES": "4",
    }
    with patch.dict("os.environ", env, clear=True):
        cfg = load_config()
        assert cfg.ai.api_key == "secret-test-key"
        assert cfg.ai.model == "custom-model"
        assert cfg.ai.timeout_seconds == 120.0
        assert cfg.ai.max_retries == 4


def test_load_config_invalid_env_types():
    """Verify ConfigError on non-numeric timeout or retries in env."""
    with patch.dict("os.environ", {"GEMINI_TIMEOUT_SECONDS": "not-a-number"}, clear=True):
        with pytest.raises(ConfigError):
            load_config()

    with patch.dict("os.environ", {"GEMINI_MAX_RETRIES": "not-an-int"}, clear=True):
        with pytest.raises(ConfigError):
            load_config()


def test_safe_config_dict_masks_api_key():
    """Verify get_safe_config_dict masks sensitive API key."""
    cfg = AppConfig()
    cfg.ai.api_key = "AIzaSyD_Secret_12345"
    safe_dict = get_safe_config_dict(cfg)

    assert safe_dict["ai"]["api_key"] != "AIzaSyD_Secret_12345"
    assert "..." in safe_dict["ai"]["api_key"]
