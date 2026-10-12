"""Provider component responsible for communicating with Google Gemini API."""

import logging
import time

import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError

from disk_analyzer.domain.models import AISummary
from disk_analyzer.exceptions import (
    AuthenticationError,
    InvalidResponseError,
    MissingAPIKeyError,
    RateLimitError,
    ServiceUnavailableError,
    TimeoutError,
)

logger = logging.getLogger(__name__)


class GeminiProvider:
    """Encapsulates interaction with the official google-genai SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.8-flash",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        """Initialize provider with configuration.

        Args:
            api_key: Google Gemini API key.
            model: Model identifier (default: 'gemini-3.8-flash').
            timeout_seconds: HTTP request timeout in seconds.
            max_retries: Maximum attempts for transient network or rate-limit failures.
        """
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def _get_client(self) -> genai.Client:
        """Create and return an initialized genai.Client instance."""
        if not self.api_key or not self.api_key.strip():
            raise MissingAPIKeyError(
                "Gemini API key is missing. Set GEMINI_API_KEY environment variable "
                "or define it in .env or config.yaml."
            )
        return genai.Client(api_key=self.api_key.strip())

    def generate_summary(self, prompt: str) -> AISummary:
        """Submit prompt to Gemini and validate the structured response against AISummary schema.

        Args:
            prompt: Text prompt prepared by PromptBuilder.

        Returns:
            Validated AISummary instance.

        Raises:
            MissingAPIKeyError: If API key is not configured.
            AuthenticationError: On 401/403 invalid credentials.
            RateLimitError: If quota or rate limits are exceeded.
            TimeoutError: If request times out repeatedly.
            ServiceUnavailableError: If service is down.
            InvalidResponseError: If response body cannot be parsed or validated.
        """
        client = self._get_client()

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AISummary,
            http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
        )

        attempts = 0
        backoff_delay = 1.0

        try:
            while attempts <= self.max_retries:
                attempts += 1
                try:
                    response = client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=config,
                    )
                    return self._parse_and_validate_response(response)

                except APIError as exc:
                    code = getattr(exc, "code", 0)
                    msg = getattr(exc, "message", str(exc))

                    # Non-retryable authentication failure
                    if code in (401, 403):
                        raise AuthenticationError(
                            f"Gemini API authentication failed (HTTP {code}): {msg}"
                        ) from exc

                    # Rate limits (429)
                    if code == 429:
                        if attempts > self.max_retries:
                            raise RateLimitError(
                                f"Gemini API rate limit exceeded after {attempts} attempts: {msg}"
                            ) from exc
                        logger.warning(
                            "Rate limit hit. Retrying in %.1fs (attempt %d/%d)...",
                            backoff_delay,
                            attempts,
                            self.max_retries,
                        )
                        time.sleep(backoff_delay)
                        backoff_delay *= 2
                        continue

                    # Transient server errors (500, 502, 503, 504)
                    if 500 <= code < 600:
                        if attempts > self.max_retries:
                            raise ServiceUnavailableError(
                                f"Gemini API server error (HTTP {code}) after {attempts} attempts: {msg}"
                            ) from exc
                        logger.warning(
                            "Server error %d. Retrying in %.1fs (attempt %d/%d)...",
                            code,
                            backoff_delay,
                            attempts,
                            self.max_retries,
                        )
                        time.sleep(backoff_delay)
                        backoff_delay *= 2
                        continue

                    # Other 4xx client errors (bad request, invalid parameters)
                    raise InvalidResponseError(
                        f"Gemini API request error (HTTP {code}): {msg}"
                    ) from exc

                except (httpx.TimeoutException, TimeoutError) as exc:
                    if attempts > self.max_retries:
                        raise TimeoutError(
                            f"Gemini API request timed out after {self.timeout_seconds}s "
                            f"(attempted {attempts} times)."
                        ) from exc
                    logger.warning("Request timed out. Retrying in %.1fs...", backoff_delay)
                    time.sleep(backoff_delay)
                    backoff_delay *= 2
                    continue

                except httpx.NetworkError as exc:
                    if attempts > self.max_retries:
                        raise ServiceUnavailableError(
                            f"Network error communicating with Gemini API: {exc}"
                        ) from exc
                    logger.warning("Network failure. Retrying in %.1fs...", backoff_delay)
                    time.sleep(backoff_delay)
                    backoff_delay *= 2
                    continue

        finally:
            self._close_client(client)

        raise ServiceUnavailableError("Failed to receive a valid response from Gemini API.")

    def check_connectivity(self) -> tuple[bool, str]:
        """Test API credentials and connectivity with a lightweight request.

        Returns:
            Tuple of (is_successful, message).
        """
        try:
            client = self._get_client()
        except MissingAPIKeyError as exc:
            return False, str(exc)

        try:
            # Minimal verification request
            response = client.models.generate_content(
                model=self.model,
                contents="Respond with 'OK' only.",
                config=types.GenerateContentConfig(
                    http_options=types.HttpOptions(
                        timeout=int(min(self.timeout_seconds, 15) * 1000)
                    ),
                ),
            )
            if response and response.text:
                return True, f"Successfully connected to Gemini API using model '{self.model}'."
            return False, "Connected, but received empty response from Gemini API."
        except AuthenticationError as exc:
            return False, f"Authentication error: {exc}"
        except APIError as exc:
            return False, f"API error (HTTP {exc.code}): {exc.message}"
        except Exception as exc:
            return False, f"Connection failed: {exc}"
        finally:
            self._close_client(client)

    @staticmethod
    def _parse_and_validate_response(response: types.GenerateContentResponse) -> AISummary:
        """Extract and validate AISummary from Gemini response object."""
        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise InvalidResponseError("Gemini API returned an empty response.")

        clean_text = text.strip()
        # Handle cases where model wraps output in markdown code fence
        if clean_text.startswith("```json"):
            clean_text = clean_text[len("```json") :].strip()
        elif clean_text.startswith("```"):
            clean_text = clean_text[len("```") :].strip()
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3].strip()

        try:
            return AISummary.model_validate_json(clean_text)
        except ValidationError as exc:
            raise InvalidResponseError(
                f"Gemini response could not be validated against AISummary schema: {exc}"
            ) from exc

    @staticmethod
    def _close_client(client: genai.Client) -> None:
        """Safely release client resources if client exposes close method."""
        try:
            if hasattr(client, "close") and callable(client.close):
                client.close()
        except Exception:
            pass
