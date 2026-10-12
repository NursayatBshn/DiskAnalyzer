"""Unit and integration tests for the CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from disk_analyzer import __version__
from disk_analyzer.cli import app

runner = CliRunner()


def test_cli_help():
    """Verify help command displays usage and available commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Intelligent disk space analysis utility for Linux" in result.output
    assert "scan" in result.output
    assert "config" in result.output
    assert "check-ai" in result.output


def test_cli_version():
    """Verify version flag outputs current version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_config():
    """Verify config command displays active config safely."""
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "AI Disk Analyzer Active Configuration" in result.output
    assert "general:" in result.output
    assert "api_key: (not set)" in result.output


def test_cli_scan_no_ai(synthetic_fs: Path):
    """Verify scanning directory with --no-ai produces expected tables and status."""
    result = runner.invoke(app, ["scan", str(synthetic_fs), "--no-ai"])
    assert result.exit_code == 0
    assert "AI Disk Analyzer" in result.output
    assert "Scan Summary" in result.output
    assert "Largest Directories" in result.output
    assert "AI analysis disabled by user request (--no-ai)" in result.output


def test_cli_scan_json_output(synthetic_fs: Path):
    """Verify scanning with --format json outputs valid JSON to stdout."""
    result = runner.invoke(app, ["scan", str(synthetic_fs), "--no-ai", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["generator"] == "ai-disk-analyzer"
    assert data["summary"]["total_files"] > 0


def test_cli_scan_markdown_output(synthetic_fs: Path):
    """Verify scanning with --format markdown outputs valid Markdown."""
    result = runner.invoke(app, ["scan", str(synthetic_fs), "--no-ai", "--format", "markdown"])
    assert result.exit_code == 0
    assert "# AI Disk Analyzer Report" in result.output
    assert "## 1. Storage Overview" in result.output


def test_cli_scan_export_to_file(synthetic_fs: Path, tmp_path: Path):
    """Verify export to destination file with --output."""
    report_file = tmp_path / "custom_report.json"
    result = runner.invoke(
        app,
        ["scan", str(synthetic_fs), "--no-ai", "--format", "json", "--output", str(report_file)],
    )
    assert result.exit_code == 0
    assert report_file.exists()
    data = json.loads(report_file.read_text(encoding="utf-8"))
    assert data["generator"] == "ai-disk-analyzer"

    # Attempting to export without --overwrite should fail
    fail_result = runner.invoke(
        app,
        ["scan", str(synthetic_fs), "--no-ai", "--format", "json", "--output", str(report_file)],
    )
    assert fail_result.exit_code == 1

    # With --overwrite should succeed
    overwrite_result = runner.invoke(
        app,
        [
            "scan",
            str(synthetic_fs),
            "--no-ai",
            "--format",
            "json",
            "--output",
            str(report_file),
            "--overwrite",
        ],
    )
    assert overwrite_result.exit_code == 0


def test_cli_scan_nonexistent_path(tmp_path: Path):
    """Verify non-existent target path returns exit code 2."""
    missing = tmp_path / "does_not_exist"
    result = runner.invoke(app, ["scan", str(missing)])
    assert result.exit_code == 2
    assert "Path Not Found" in result.output


def test_cli_scan_file_target(tmp_path: Path):
    """Verify targeting a file instead of directory returns exit code 2."""
    target_file = tmp_path / "some_file.txt"
    target_file.write_text("hello")
    result = runner.invoke(app, ["scan", str(target_file)])
    assert result.exit_code == 2
    assert "Not a Directory" in result.output


def test_cli_analyze_alias(synthetic_fs: Path):
    """Verify analyze command works as an alias for scan."""
    result = runner.invoke(app, ["analyze", str(synthetic_fs), "--no-ai"])
    assert result.exit_code == 0
    assert "Scan Summary" in result.output


def test_cli_check_ai_missing_key():
    """Verify check-ai fails with exit code 1 when no key is set."""
    with patch.dict("os.environ", {}, clear=True):
        result = runner.invoke(app, ["check-ai"])
        assert result.exit_code == 1
        assert "No Gemini API key detected" in result.output


@patch("disk_analyzer.ai.gemini_provider.GeminiProvider.check_connectivity")
def test_cli_check_ai_success(mock_check):
    """Verify check-ai reports success when API check passes."""
    mock_check.return_value = (True, "Connected OK to gemini-3.8-flash")
    with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_test_key"}):
        result = runner.invoke(app, ["check-ai"])
        assert result.exit_code == 0
        assert "Connected OK" in result.output
