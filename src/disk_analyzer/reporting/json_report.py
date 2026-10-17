"""JSON report generation and export for machine-readable consumption."""

import json
from pathlib import Path
from typing import Any

from disk_analyzer import __version__
from disk_analyzer.domain.models import AnalysisResult
from disk_analyzer.exceptions import FileAlreadyExistsError, ReportError
from disk_analyzer.utils.formatting import redact_path


class JsonReporter:
    """Serializes analysis results to structured, machine-readable JSON."""

    def __init__(self, redact_paths: bool = True) -> None:
        """Initialize JsonReporter.

        Args:
            redact_paths: Whether to redact user home directories.
        """
        self.redact_paths = redact_paths

    def generate_dict(self, analysis: AnalysisResult) -> dict[str, Any]:
        """Convert AnalysisResult into a structured dictionary with numeric values.

        Args:
            analysis: The AnalysisResult to format.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        scan = analysis.scan_result

        # Dump base model
        raw = analysis.model_dump(mode="json")

        # Metadata wrapper
        report: dict[str, Any] = {
            "version": __version__,
            "generator": "ai-disk-analyzer",
            "redacted": self.redact_paths,
            "root_path": redact_path(scan.root_path, self.redact_paths),
            "scanned_at": scan.scanned_at.isoformat(),
            "analyzed_at": analysis.analyzed_at.isoformat(),
            "summary": {
                "total_files": scan.total_files,
                "total_directories": scan.total_directories,
                "total_logical_size_bytes": scan.total_logical_size_bytes,
                "total_allocated_size_bytes": scan.total_allocated_size_bytes,
                "duration_seconds": scan.duration_seconds,
                "diagnostics_count": len(scan.diagnostics),
            },
            "disk_usage": raw.get("disk_usage"),
            "largest_directories": [
                {
                    **d,
                    "path": redact_path(d["path"], self.redact_paths),
                }
                for d in raw.get("scan_result", {}).get("largest_directories", [])
            ],
            "largest_files": [
                {
                    **f,
                    "path": redact_path(f["path"], self.redact_paths),
                }
                for f in raw.get("scan_result", {}).get("largest_files", [])
            ],
            "top_categories": [
                {
                    **c,
                    "sample_paths": [
                        redact_path(p, self.redact_paths) for p in c.get("sample_paths", [])
                    ],
                }
                for c in raw.get("top_categories", [])
            ],
            "top_extensions": raw.get("top_extensions", []),
            "recommendations": [
                {
                    **r,
                    "target_paths": [
                        redact_path(p, self.redact_paths) for p in r.get("target_paths", [])
                    ],
                }
                for r in raw.get("recommendations", [])
            ],
            "ai_summary": raw.get("ai_summary"),
            "ai_status_message": raw.get("ai_status_message"),
            "diagnostics": [
                {
                    **diag,
                    "path": redact_path(diag["path"], self.redact_paths),
                }
                for diag in raw.get("scan_result", {}).get("diagnostics", [])
            ],
        }

        return report

    def render(self, analysis: AnalysisResult) -> str:
        """Render JSON string representation of analysis.

        Args:
            analysis: The AnalysisResult to format.

        Returns:
            Pretty-printed JSON string.
        """
        data = self.generate_dict(analysis)
        return json.dumps(data, indent=2, ensure_ascii=False)

    def save_to_file(
        self,
        analysis: AnalysisResult,
        target_path: Path | str,
        overwrite: bool = False,
    ) -> Path:
        """Export analysis report to a JSON file safely.

        Args:
            analysis: The AnalysisResult to export.
            target_path: Destination path for JSON report.
            overwrite: Whether to overwrite existing file.

        Returns:
            Resolved Path of the saved report.

        Raises:
            FileAlreadyExistsError: If target_path exists and overwrite is False.
            ReportError: If file writing fails.
        """
        dest = Path(target_path).expanduser().resolve()

        if dest.exists() and not overwrite:
            raise FileAlreadyExistsError(
                f"Report destination already exists: {dest}. "
                "Use --overwrite to allow replacing existing files."
            )

        content = self.render(analysis)

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)
            return dest
        except OSError as exc:
            raise ReportError(f"Failed to write JSON report to {dest}: {exc}") from exc

