"""Unit tests for SummaryService orchestration and degradation."""

from unittest.mock import MagicMock

from disk_analyzer.ai.gemini_provider import GeminiProvider
from disk_analyzer.ai.summary_service import SummaryService
from disk_analyzer.domain.models import AISummary, AnalysisResult
from disk_analyzer.exceptions import RateLimitError


def test_summary_service_disabled(sample_analysis_result: AnalysisResult):
    """Verify service returns disabled message when ai_enabled is False."""
    service = SummaryService(ai_enabled=False)
    summary, msg = service.generate_summary(sample_analysis_result)

    assert summary is None
    assert "disabled" in msg.lower()


def test_summary_service_missing_api_key(sample_analysis_result: AnalysisResult):
    """Verify service returns informational message when API key is missing."""
    provider = GeminiProvider(api_key=None)
    service = SummaryService(gemini_provider=provider, ai_enabled=True)
    summary, msg = service.generate_summary(sample_analysis_result)

    assert summary is None
    assert "not configured" in msg.lower()


def test_summary_service_success(sample_analysis_result: AnalysisResult):
    """Verify service returns AISummary when provider succeeds."""
    mock_provider = MagicMock(spec=GeminiProvider)
    mock_provider.api_key = "dummy-key"
    mock_summary = AISummary(
        executive_summary="Executive summary test",
        main_storage_consumers=[],
        significant_observations=[],
        cleanup_candidates=[],
        expected_benefits="None",
        risks_and_warnings=[],
        prioritized_next_steps=[],
        confidence_explanation="High",
    )
    mock_provider.generate_summary.return_value = mock_summary

    service = SummaryService(gemini_provider=mock_provider, ai_enabled=True)
    summary, msg = service.generate_summary(sample_analysis_result)

    assert summary == mock_summary
    assert "successfully" in msg.lower()


def test_summary_service_api_error_fallback(sample_analysis_result: AnalysisResult):
    """Verify service gracefully falls back on AIError."""
    mock_provider = MagicMock(spec=GeminiProvider)
    mock_provider.api_key = "dummy-key"
    mock_provider.generate_summary.side_effect = RateLimitError("Rate limit exceeded")

    service = SummaryService(gemini_provider=mock_provider, ai_enabled=True)
    summary, msg = service.generate_summary(sample_analysis_result)

    assert summary is None
    assert "could not be generated" in msg.lower()


def test_summary_service_unexpected_exception_fallback(sample_analysis_result: AnalysisResult):
    """Verify service gracefully falls back on unexpected exception."""
    mock_provider = MagicMock(spec=GeminiProvider)
    mock_provider.api_key = "dummy-key"
    mock_provider.generate_summary.side_effect = RuntimeError("Fatal hardware crash")

    service = SummaryService(gemini_provider=mock_provider, ai_enabled=True)
    summary, msg = service.generate_summary(sample_analysis_result)

    assert summary is None
    assert "failed unexpectedly" in msg.lower()
