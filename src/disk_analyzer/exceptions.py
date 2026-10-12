"""Custom exceptions for AI Disk Analyzer."""


class DiskAnalyzerError(Exception):
    """Base exception for all AI Disk Analyzer errors."""


class ScanError(DiskAnalyzerError):
    """Raised when an unrecoverable error occurs during filesystem scanning."""


class PathNotFoundError(ScanError):
    """Raised when the specified target path does not exist."""


class NotADirectoryError(ScanError):
    """Raised when the specified target path is not a directory."""


class PermissionScanError(ScanError):
    """Raised when a directory or file is completely inaccessible due to permissions."""


class ConfigError(DiskAnalyzerError):
    """Raised when configuration loading or validation fails."""


class AIError(DiskAnalyzerError):
    """Base exception for AI/Gemini-related errors."""


class MissingAPIKeyError(AIError):
    """Raised when Gemini API key is missing or not provided."""


class AuthenticationError(AIError):
    """Raised when the Gemini API returns an authentication or authorization failure."""


class RateLimitError(AIError):
    """Raised when the Gemini API returns a rate-limit or quota-exceeded error."""


class TimeoutError(AIError):
    """Raised when an API request to Gemini times out."""


class ServiceUnavailableError(AIError):
    """Raised when the Gemini API service is temporarily unavailable."""


class InvalidResponseError(AIError):
    """Raised when the Gemini API returns a response that cannot be parsed or validated."""


class ReportError(DiskAnalyzerError):
    """Raised when report generation or export fails."""


class FileAlreadyExistsError(ReportError):
    """Raised when attempting to write a report to an existing file without overwrite permission."""
