"""Prompt construction for Google Gemini with privacy filtering and structural constraints."""

import json
from typing import Any

from disk_analyzer.domain.models import AnalysisResult
from disk_analyzer.utils.formatting import format_bytes, redact_path


class PromptBuilder:
    """Builds privacy-safe, compact prompts for the Gemini model."""

    def __init__(self, redact_paths: bool = True) -> None:
        """Initialize PromptBuilder with redaction preferences.

        Args:
            redact_paths: Whether to redact user home directories from paths.
        """
        self.redact_paths = redact_paths

    def build_prompt(self, analysis: AnalysisResult) -> str:
        """Construct a structured prompt containing aggregated statistics and guidelines.

        Args:
            analysis: The deterministic analysis result.

        Returns:
            The complete prompt text formatted for Gemini.
        """
        payload = self._build_statistics_payload(analysis)
        payload_json = json.dumps(payload, indent=2)

        return f"""You are an expert Linux storage analyst and systems architect.
Analyze the following deterministic filesystem statistics collected by 'AI Disk Analyzer'.

### OBSERVED FILESYSTEM METRICS:
```json
{payload_json}
```

### INSTRUCTIONS AND MANDATORY CONSTRAINTS:
1. Base all observations strictly on the provided statistics.
2. Distinguish verified facts (measured sizes, extensions, paths) from heuristic classifications and hypotheses.
3. Identify the primary storage consumers and explain why they occupy space (e.g. package caches, compiler build trees, dependencies).
4. Highlight realistic cleanup candidates only when evidence supports it.
5. Provide explicit warnings, side-effects, and risks for every potential cleanup action.
6. Only estimate potential storage recovery when defensible from the data; otherwise explicitly state that savings are unestablished.
7. NEVER recommend deleting unknown directories, active personal documents, source code, or essential operating system paths.
8. NEVER claim you inspected file contents, lines of code, or file internals—you have only received filesystem metadata.
9. NEVER invent paths, sizes, file types, or nonexistent tools.
10. NEVER generate arbitrary shell commands or assume commands will be executed automatically. The application is strictly read-only.
11. Return a clear, objective analysis complying with the required response schema.
"""

    def _build_statistics_payload(self, analysis: AnalysisResult) -> dict[str, Any]:
        """Format analysis data into a minimal, redacted dictionary."""
        scan = analysis.scan_result

        # Redact root path
        root_repr = redact_path(scan.root_path, self.redact_paths)

        # Filesystem metrics
        fs_metrics = None
        if analysis.disk_usage:
            fs_metrics = {
                "total_capacity": format_bytes(analysis.disk_usage.total_bytes),
                "used_space": format_bytes(analysis.disk_usage.used_bytes),
                "free_space": format_bytes(analysis.disk_usage.free_bytes),
                "percent_used": f"{analysis.disk_usage.percent_used}%",
            }

        # Top largest files
        top_files = [
            {
                "path": redact_path(f.path, self.redact_paths),
                "size": format_bytes(f.size_bytes),
                "extension": f.extension,
            }
            for f in scan.largest_files[:10]
        ]

        # Top largest directories
        top_dirs = [
            {
                "path": redact_path(d.path, self.redact_paths),
                "logical_size": format_bytes(d.logical_size_bytes),
                "file_count": d.file_count,
            }
            for d in scan.largest_directories[:10]
        ]

        # Categories
        categories = [
            {
                "name": c.name,
                "size": format_bytes(c.total_size_bytes),
                "percentage_of_scan": f"{c.percentage_of_total}%",
                "file_count": c.file_count,
                "confidence": c.confidence,
                "is_potential_cleanup": c.is_potential_cleanup,
                "rationale": c.rationale,
                "sample_paths": [redact_path(p, self.redact_paths) for p in c.sample_paths[:2]],
            }
            for c in analysis.top_categories
        ]

        # Extensions
        extensions = [
            {
                "extension": e.extension,
                "size": format_bytes(e.total_size_bytes),
                "percentage_of_scan": f"{e.percentage_of_total}%",
                "file_count": e.file_count,
            }
            for e in analysis.top_extensions[:8]
        ]

        # Deterministic recommendations
        recommendations = [
            {
                "title": r.title,
                "category": r.category,
                "priority": r.priority,
                "description": r.description,
                "estimated_reclaimable": (
                    format_bytes(r.estimated_reclaimable_bytes)
                    if r.estimated_reclaimable_bytes is not None
                    else "Not established"
                ),
                "risks": r.risks_and_caveats,
            }
            for r in analysis.recommendations
        ]

        return {
            "scan_root": root_repr,
            "total_files_scanned": scan.total_files,
            "total_directories_scanned": scan.total_directories,
            "total_logical_size": format_bytes(scan.total_logical_size_bytes),
            "total_allocated_size": format_bytes(scan.total_allocated_size_bytes),
            "diagnostics_error_count": len(scan.diagnostics),
            "filesystem_volume": fs_metrics,
            "top_files": top_files,
            "top_directories": top_dirs,
            "storage_categories": categories,
            "file_extensions": extensions,
            "rule_based_recommendations": recommendations,
        }
