"""Unit tests for GeminiProvider with mocked official google-genai SDK."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from google.genai.errors import ClientError

from disk_analyzer.ai.gemini_provider import GeminiProvider
from disk_analyzer.domain.models import AISummary
from disk_analyzer.exceptions import (
    AuthenticationError,
    InvalidResponseError,
    MissingAPIKeyError,
    RateLimitError,
    TimeoutError,
)

SAMPLE_AI_JSON = json.dumps(
    {
        "executive_summary": "Storage is mostly used by compiler outputs and caches.",
        "main_storage_consumers": ["target/", ".cache/"],
        "significant_observations": ["Build artifacts occupy 40% of disk."],
        "cleanup_candidates": ["Empty trash", "Clean target/"],
        "expected_benefits": "Up to 500 MB recoverable.",
        "risks_and_warnings": ["Recompilation will be needed."],
        "prioritized_next_steps": ["1. Review trash", "2. Run cargo clean"],
        "confidence_explanation": "High confidence based on standard build patterns.",
    }
)


def test_missing_api_key_raises_error():
    """Verify MissingAPIKeyError when API key is None or empty."""
    provider = GeminiProvider(api_key=None)
    with pytest.raises(MissingAPIKeyError):
        provider.generate_summary("test prompt")

    provider_empty = GeminiProvider(api_key="   ")
    with pytest.raises(MissingAPIKeyError):
        provider_empty.generate_summary("test prompt")


@patch("disk_analyzer.ai.gemini_provider.genai.Client")
def test_successful_summary_generation(mock_client_cls):
    """Verify successful AI generation and Pydantic validation."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = SAMPLE_AI_JSON
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="test-api-key")
    summary = provider.generate_summary("prompt text")

    assert isinstance(summary, AISummary)
    assert summary.executive_summary == "Storage is mostly used by compiler outputs and caches."
    assert len(summary.main_storage_consumers) == 2
    mock_client.models.generate_content.assert_called_once()


@patch("disk_analyzer.ai.gemini_provider.genai.Client")
def test_fenced_json_parsing(mock_client_cls):
    """Verify handling of markdown code-fenced JSON responses."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = f"```json\n{SAMPLE_AI_JSON}\n```"
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="test-api-key")
    summary = provider.generate_summary("prompt text")

    assert isinstance(summary, AISummary)
    assert summary.executive_summary == "Storage is mostly used by compiler outputs and caches."


@patch("disk_analyzer.ai.gemini_provider.genai.Client")
def test_authentication_error_no_retries(mock_client_cls):
    """Verify HTTP 401/403 raises AuthenticationError immediately without retrying."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    err = ClientError(401, {"error": {"code": 401, "message": "API_KEY_INVALID"}})
    mock_client.models.generate_content.side_effect = err

    provider = GeminiProvider(api_key="bad-key", max_retries=2)
    with pytest.raises(AuthenticationError):
        provider.generate_summary("prompt")

    # Should have executed only 1 attempt
    assert mock_client.models.generate_content.call_count == 1


@patch("disk_analyzer.ai.gemini_provider.time.sleep")
@patch("disk_analyzer.ai.gemini_provider.genai.Client")
def test_rate_limit_bounded_retries(mock_client_cls, mock_sleep):
    """Verify HTTP 429 retries up to max_retries and raises RateLimitError."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    err = ClientError(429, {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}})
    mock_client.models.generate_content.side_effect = err

    provider = GeminiProvider(api_key="test-key", max_retries=2)
    with pytest.raises(RateLimitError):
        provider.generate_summary("prompt")

    # Initial attempt + 2 retries = 3 calls
    assert mock_client.models.generate_content.call_count == 3
    assert mock_sleep.call_count == 2


@patch("disk_analyzer.ai.gemini_provider.time.sleep")
@patch("disk_analyzer.ai.gemini_provider.genai.Client")
def test_timeout_bounded_retries(mock_client_cls, mock_sleep):
    """Verify timeout retries up to max_retries and raises TimeoutError."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_client.models.generate_content.side_effect = httpx.TimeoutException("Timed out")

    provider = GeminiProvider(api_key="test-key", timeout_seconds=5.0, max_retries=1)
    with pytest.raises(TimeoutError):
        provider.generate_summary("prompt")

    assert mock_client.models.generate_content.call_count == 2
    assert mock_sleep.call_count == 1


@patch("disk_analyzer.ai.gemini_provider.genai.Client")
def test_empty_response_raises_invalid_response(mock_client_cls):
    """Verify empty response text raises InvalidResponseError."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = ""
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="test-key")
    with pytest.raises(InvalidResponseError):
        provider.generate_summary("prompt")


@patch("disk_analyzer.ai.gemini_provider.genai.Client")
def test_malformed_json_raises_invalid_response(mock_client_cls):
    """Verify non-JSON response raises InvalidResponseError."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = "This is not valid json content!"
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="test-key")
    with pytest.raises(InvalidResponseError):
        provider.generate_summary("prompt")


@patch("disk_analyzer.ai.gemini_provider.genai.Client")
def test_check_connectivity_success(mock_client_cls):
    """Verify check_connectivity succeeds when minimal request returns."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = "OK"
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="valid-key")
    success, message = provider.check_connectivity()

    assert success is True
    assert "Successfully connected" in message


def test_check_connectivity_missing_key():
    """Verify check_connectivity reports failure when API key is missing."""
    provider = GeminiProvider(api_key=None)
    success, message = provider.check_connectivity()

    assert success is False
    assert "missing" in message.lower()
