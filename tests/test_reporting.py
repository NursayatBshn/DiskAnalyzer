"""Unit tests for reporting modules (Terminal, JSON, Markdown)."""

import json
from pathlib import Path

import pytest
from rich.console import Console

from disk_analyzer.domain.models import AnalysisResult
from disk_analyzer.exceptions import FileAlreadyExistsError
from disk_analyzer.reporting.json_report import JsonReporter
from disk_analyzer.reporting.markdown_report import MarkdownReporter
from disk_analyzer.reporting.terminal_report import TerminalReporter
from disk_analyzer.utils.formatting import (
    format_bytes,
    format_duration,
    mask_secret,
    redact_path,
)


def test_formatting_utils():
    """Verify byte and duration formatting."""
    assert format_bytes(0) == "0 B"
    assert format_bytes(512) == "512 B"
    assert format_bytes(1024) == "1.00 KiB"
    assert format_bytes(1024 * 1024) == "1.00 MiB"
    assert format_bytes(1024 * 1024 * 1024 * 2.5) == "2.50 GiB"
    assert format_bytes(-1024) == "-1.00 KiB"

    assert format_duration(0.123) == "123 ms"
    assert format_duration(2.5) == "2.50s"
    assert format_duration(75.5) == "1m 15.5s"

    assert mask_secret(None) == "(not set)"
    assert mask_secret("short") == "********"
    assert mask_secret("AIzaSyD1234567890XYZ") == "AIza...0XYZ"


def test_redact_path():
    """Verify path privacy redaction."""
    assert redact_path("/home/john/file.txt", redact=True) == "~/file.txt"
    assert redact_path("/home/john", redact=True) == "~"
    assert redact_path("/var/log/syslog", redact=True) == "/var/log/syslog"
    assert redact_path("/home/john/file.txt", redact=False) == "/home/john/file.txt"


def test_terminal_reporter_renders_cleanly(sample_analysis_result: AnalysisResult):
    """Verify TerminalReporter renders without throwing exceptions."""
    console = Console(record=True, width=120)
    reporter = TerminalReporter(console=console, redact_paths=True)
    reporter.render(sample_analysis_result)

    output = console.export_text()
    assert "AI Disk Analyzer" in output
    assert "Scan Summary" in output
    assert "Top 2 Largest Directories" in output
    assert "Build Artifacts" in output
    assert "Google Gemini AI Intelligent Assessment" in output


def test_json_reporter(sample_analysis_result: AnalysisResult, tmp_path: Path):
    """Verify JSON report generation and safe export."""
    reporter = JsonReporter(redact_paths=True)
    json_str = reporter.render(sample_analysis_result)
    parsed = json.loads(json_str)

    assert parsed["generator"] == "ai-disk-analyzer"
    assert parsed["summary"]["total_files"] == 24
    assert len(parsed["largest_files"]) == 3
    assert parsed["ai_summary"]["executive_summary"] != ""

    dest = tmp_path / "report.json"
    saved = reporter.save_to_file(sample_analysis_result, dest)
    assert saved.exists()

    # Overwrite protection
    with pytest.raises(FileAlreadyExistsError):
        reporter.save_to_file(sample_analysis_result, dest, overwrite=False)

    # Allow overwrite
    reporter.save_to_file(sample_analysis_result, dest, overwrite=True)
    assert dest.exists()


def test_markdown_reporter(sample_analysis_result: AnalysisResult, tmp_path: Path):
    """Verify Markdown report generation and safe export."""
    reporter = MarkdownReporter(redact_paths=True)
    md_str = reporter.render(sample_analysis_result)

    assert "# AI Disk Analyzer Report" in md_str
    assert "## 1. Storage Overview" in md_str
    assert "## 2. Top Largest Directories" in md_str
    assert "## 6. Deterministic Cleanup & Maintenance Recommendations" in md_str
    assert "## 7. Google Gemini AI Analysis" in md_str
    assert "> [!TIP]" in md_str
    assert "> [!WARNING]" in md_str

    dest = tmp_path / "report.md"
    saved = reporter.save_to_file(sample_analysis_result, dest)
    assert saved.exists()

    with pytest.raises(FileAlreadyExistsError):
        reporter.save_to_file(sample_analysis_result, dest, overwrite=False)
