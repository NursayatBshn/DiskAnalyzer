"""Deterministic analysis engine that aggregates metrics, categories, and recommendations."""

import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from disk_analyzer.analysis.categories import aggregate_categories
from disk_analyzer.analysis.recommendations import generate_recommendations
from disk_analyzer.domain.models import (
    AnalysisResult,
    DiskUsageInfo,
    ExtensionSummary,
    ScanResult,
    StorageCategorySummary,
)


class DiskAnalyzer:
    """Performs deterministic analysis on raw scan results without invoking AI models."""

    def __init__(
        self,
        classify_storage: bool = True,
        top_extensions_count: int = 10,
        estimate_reclaimable: bool = True,
    ) -> None:
        """Initialize the analyzer with options.

        Args:
            classify_storage: Whether to run heuristic pattern classification.
            top_extensions_count: Maximum number of file extensions to include in summary.
            estimate_reclaimable: Whether to include conservative reclaimable estimates.
        """
        self.classify_storage = classify_storage
        self.top_extensions_count = max(1, top_extensions_count)
        self.estimate_reclaimable = estimate_reclaimable

    def analyze(self, scan_result: ScanResult) -> AnalysisResult:
        """Perform comprehensive deterministic analysis on the provided ScanResult.

        Args:
            scan_result: The raw filesystem scan result.

        Returns:
            An AnalysisResult containing aggregated statistics, categories, and recommendations.
        """
        # 1. Inspect overall filesystem volume usage
        disk_usage = self._get_disk_usage(scan_result.root_path)

        # 2. Categorize storage usage
        categories: list[StorageCategorySummary] = []
        if self.classify_storage:
            categories = aggregate_categories(
                scan_result.largest_files,
                scan_result.total_logical_size_bytes,
            )

        # 3. Aggregate file extension distributions
        extensions = self._aggregate_extensions(
            scan_result.largest_files,
            scan_result.total_logical_size_bytes,
        )

        # 4. Generate deterministic recommendations
        recommendations = []
        if self.estimate_reclaimable and categories:
            recommendations = generate_recommendations(
                categories,
                scan_result.total_logical_size_bytes,
            )

        return AnalysisResult(
            scan_result=scan_result,
            disk_usage=disk_usage,
            top_categories=categories,
            top_extensions=extensions,
            recommendations=recommendations,
            ai_summary=None,
            ai_status_message=None,
            analyzed_at=datetime.now(UTC),
        )

    def _get_disk_usage(self, root_path: str) -> DiskUsageInfo | None:
        """Obtain underlying filesystem storage metrics via shutil.disk_usage."""
        try:
            resolved = Path(root_path).resolve()
            # If path doesn't exist anymore or is special, fallback to parent
            target = resolved if resolved.exists() else resolved.parent
            usage = shutil.disk_usage(str(target))
            percent = (usage.used / usage.total * 100.0) if usage.total > 0 else 0.0
            return DiskUsageInfo(
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent_used=round(percent, 1),
            )
        except (OSError, ValueError):
            return None

    def _aggregate_extensions(self, files: list, total_logical_size: int) -> list[ExtensionSummary]:
        """Group files by extension and compute cumulative size and count."""
        ext_sizes: dict[str, int] = defaultdict(int)
        ext_counts: dict[str, int] = defaultdict(int)

        for file in files:
            ext = file.extension if file.extension else "(no extension)"
            ext_sizes[ext] += file.size_bytes
            ext_counts[ext] += 1

        summaries: list[ExtensionSummary] = []
        for ext, size in ext_sizes.items():
            pct = (size / total_logical_size * 100.0) if total_logical_size > 0 else 0.0
            summaries.append(
                ExtensionSummary(
                    extension=ext,
                    total_size_bytes=size,
                    file_count=ext_counts[ext],
                    percentage_of_total=round(pct, 2),
                )
            )

        summaries.sort(key=lambda e: e.total_size_bytes, reverse=True)
        return summaries[: self.top_extensions_count]
