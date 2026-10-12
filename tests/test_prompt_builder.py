"""Unit tests for PromptBuilder ensuring privacy and concise aggregation."""

from disk_analyzer.ai.prompt_builder import PromptBuilder
from disk_analyzer.domain.models import AnalysisResult


def test_prompt_builder_redaction(sample_analysis_result: AnalysisResult):
    """Verify that user paths are redacted in generated prompts."""
    builder = PromptBuilder(redact_paths=True)
    prompt = builder.build_prompt(sample_analysis_result)

    # Prompt must contain instructions
    assert "MANDATORY CONSTRAINTS" in prompt
    assert "NEVER recommend deleting" in prompt
    assert "NEVER invent paths" in prompt

    # Aggregated metrics present
    assert "total_logical_size" in prompt
    assert "Build Artifacts & Compiled Output" in prompt
    assert "Trash & Recycled Items" in prompt

    # Path redaction: /home/testuser should be redacted to ~
    assert "/home/testuser" not in prompt
    assert "~" in prompt


def test_prompt_builder_no_redaction(sample_analysis_result: AnalysisResult):
    """Verify paths are preserved when redaction is explicitly disabled."""
    builder = PromptBuilder(redact_paths=False)
    prompt = builder.build_prompt(sample_analysis_result)

    assert "/home/testuser/workspace" in prompt
