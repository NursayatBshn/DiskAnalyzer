"""Service orchestrating AI summary generation and graceful fallback."""

import logging

from disk_analyzer.ai.gemini_provider import GeminiProvider
from disk_analyzer.ai.prompt_builder import PromptBuilder
from disk_analyzer.domain.models import AISummary, AnalysisResult
from disk_analyzer.exceptions import (
    AIError,
    MissingAPIKeyError,
)

logger = logging.getLogger(__name__)


class SummaryService:
    """Orchestrates AI prompt creation, generation, and safe degradation."""

    def __init__(
        self,
        gemini_provider: GeminiProvider | None = None,
        prompt_builder: PromptBuilder | None = None,
        ai_enabled: bool = True,
    ) -> None:
        """Initialize SummaryService.

        Args:
            gemini_provider: Configured GeminiProvider instance.
            prompt_builder: Configured PromptBuilder instance.
            ai_enabled: Whether AI generation is requested.
        """
        self.provider = gemini_provider or GeminiProvider()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.ai_enabled = ai_enabled

    def generate_summary(self, analysis: AnalysisResult) -> tuple[AISummary | None, str]:
        """Attempt to generate an AI summary for the analysis.

        If AI is disabled or fails, preserves all deterministic data and returns
        an informative status message.

        Args:
            analysis: Deterministic analysis result.

        Returns:
            Tuple of (AISummary or None, status_explanation_string).
        """
        if not self.ai_enabled:
            return None, "AI summary disabled by configuration (--no-ai)."

        if not self.provider.api_key or not self.provider.api_key.strip():
            return (
                None,
                "Gemini API key is not configured. "
                "Set GEMINI_API_KEY in your environment or .env file to enable AI-powered summaries.",
            )

        try:
            prompt = self.prompt_builder.build_prompt(analysis)
            summary = self.provider.generate_summary(prompt)
            return summary, "AI summary generated successfully via Google Gemini."

        except MissingAPIKeyError as exc:
            return None, str(exc)

        except AIError as exc:
            logger.warning("AI generation failed gracefully: %s", exc)
            return None, f"AI summary could not be generated: {exc}"

        except Exception as exc:
            logger.exception("Unexpected error during AI summary generation: %s", exc)
            return None, f"AI summary generation failed unexpectedly: {exc}"
