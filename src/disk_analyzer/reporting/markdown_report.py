"""Markdown report generation for documentation and export."""

from pathlib import Path

from disk_analyzer import __version__
from disk_analyzer.domain.models import AnalysisResult
from disk_analyzer.exceptions import FileAlreadyExistsError, ReportError
from disk_analyzer.utils.formatting import format_bytes, format_duration, redact_path


class MarkdownReporter:
    """Generates structured GitHub-Flavored Markdown reports."""

    def __init__(self, redact_paths: bool = True) -> None:
        """Initialize MarkdownReporter.

        Args:
            redact_paths: Whether to redact user home directories.
        """
        self.redact_paths = redact_paths

    def render(self, analysis: AnalysisResult) -> str:
        """Render complete Markdown document.

        Args:
            analysis: The AnalysisResult to format.

        Returns:
            Formatted Markdown string.
        """
        scan = analysis.scan_result
        root_repr = redact_path(scan.root_path, self.redact_paths)

        lines: list[str] = [
            "# AI Disk Analyzer Report",
            "",
            f"- **Scan Root:** `{root_repr}`",
            f"- **Tool Version:** `v{__version__}`",
            f"- **Scanned At:** `{scan.scanned_at.strftime('%Y-%m-%d %H:%M:%S UTC')}`",
            f"- **Scan Duration:** `{format_duration(scan.duration_seconds)}`",
            f"- **Path Privacy:** `{'Redacted' if self.redact_paths else 'Full Paths'}`",
            "",
            "## 1. Storage Overview",
            "",
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| Total Files Scanned | {scan.total_files:,} |",
            f"| Total Directories Scanned | {scan.total_directories:,} |",
            f"| Total Logical Size | **{format_bytes(scan.total_logical_size_bytes)}** |",
            f"| Total Allocated Disk Space | **{format_bytes(scan.total_allocated_size_bytes)}** |",
            f"| Inaccessible Paths / Diagnostics | {len(scan.diagnostics)} |",
        ]

        if analysis.disk_usage:
            du = analysis.disk_usage
            lines.extend(
                [
                    f"| Filesystem Total Capacity | {format_bytes(du.total_bytes)} |",
                    f"| Filesystem Used Space | {format_bytes(du.used_bytes)} ({du.percent_used}%) |",
                    f"| Filesystem Available Space | {format_bytes(du.free_bytes)} |",
                ]
            )

        lines.extend(["", "---", ""])

        # Top Directories
        if scan.largest_directories:
            lines.extend(
                [
                    "## 2. Top Largest Directories",
                    "",
                    "| # | Directory Path | Logical Size | Files | % of Scan |",
                    "| :---: | :--- | :---: | :---: | :---: |",
                ]
            )
            for idx, d in enumerate(scan.largest_directories, 1):
                pct = (
                    (d.logical_size_bytes / scan.total_logical_size_bytes * 100.0)
                    if scan.total_logical_size_bytes > 0
                    else 0.0
                )
                p_str = redact_path(d.path, self.redact_paths)
                lines.append(
                    f"| {idx} | `{p_str}` | {format_bytes(d.logical_size_bytes)} | {d.file_count:,} | {pct:.1f}% |"
                )
            lines.extend(["", "---", ""])

        # Top Files
        if scan.largest_files:
            lines.extend(
                [
                    "## 3. Top Largest Files",
                    "",
                    "| # | File Path | Logical Size | Allocated Size | Type |",
                    "| :---: | :--- | :---: | :---: | :---: |",
                ]
            )
            for idx, f in enumerate(scan.largest_files, 1):
                p_str = redact_path(f.path, self.redact_paths)
                lines.append(
                    f"| {idx} | `{p_str}` | {format_bytes(f.size_bytes)} | {format_bytes(f.allocated_bytes)} | `{f.extension or '(none)'}` |"
                )
            lines.extend(["", "---", ""])

        # Storage Categories
        if analysis.top_categories:
            lines.extend(
                [
                    "## 4. Storage Pattern Breakdown (Heuristic)",
                    "",
                    "| Category | Size | % Total | Files | Confidence | Potential Cleanup |",
                    "| :--- | :---: | :---: | :---: | :---: | :---: |",
                ]
            )
            for c in analysis.top_categories:
                cleanup_str = "Yes" if c.is_potential_cleanup else "No"
                lines.append(
                    f"| **{c.name}** | {format_bytes(c.total_size_bytes)} | {c.percentage_of_total:.1f}% | {c.file_count:,} | {c.confidence} | {cleanup_str} |"
                )
            lines.extend(["", "---", ""])

        # Extensions
        if analysis.top_extensions:
            lines.extend(
                [
                    "## 5. File Extension Distribution",
                    "",
                    "| Extension | Size | Files | % Total |",
                    "| :--- | :---: | :---: | :---: |",
                ]
            )
            for ext in analysis.top_extensions:
                lines.append(
                    f"| `{ext.extension}` | {format_bytes(ext.total_size_bytes)} | {ext.file_count:,} | {ext.percentage_of_total:.1f}% |"
                )
            lines.extend(["", "---", ""])

        # Deterministic Recommendations
        if analysis.recommendations:
            lines.extend(["## 6. Deterministic Cleanup & Maintenance Recommendations", ""])
            for rec in analysis.recommendations:
                lines.extend(
                    [
                        f"### [{rec.priority.upper()}] {rec.title}",
                        "",
                        rec.description,
                        "",
                    ]
                )
                if rec.estimated_reclaimable_bytes is not None:
                    lines.append(
                        f"> [!TIP]\n> **Estimated Potential Savings:** {format_bytes(rec.estimated_reclaimable_bytes)} (Confidence: {rec.confidence})"
                    )
                else:
                    lines.append(
                        "> [!NOTE]\n> **Estimated Potential Savings:** Not established without deeper manual audit."
                    )

                lines.extend(
                    [
                        "",
                        f"> [!WARNING]\n> **Risks & Precautions:** {rec.risks_and_caveats}",
                        "",
                        "**Suggested Verification Steps:**",
                    ]
                )
                for act in rec.suggested_actions:
                    lines.append(f"- {act}")
                lines.append("")
            lines.extend(["---", ""])

        # AI Summary
        if analysis.ai_summary:
            ai = analysis.ai_summary
            lines.extend(
                [
                    "## 7. Google Gemini AI Analysis",
                    "",
                    "### Executive Summary",
                    "",
                    ai.executive_summary,
                    "",
                ]
            )

            if ai.main_storage_consumers:
                lines.extend(["### Key Storage Consumers", ""])
                for item in ai.main_storage_consumers:
                    lines.append(f"- {item}")
                lines.append("")

            if ai.significant_observations:
                lines.extend(["### Notable Observations", ""])
                for item in ai.significant_observations:
                    lines.append(f"- {item}")
                lines.append("")

            if ai.cleanup_candidates:
                lines.extend(["### Potential Cleanup Candidates", ""])
                for item in ai.cleanup_candidates:
                    lines.append(f"- {item}")
                lines.append("")

            if ai.risks_and_warnings:
                lines.extend(["### Warnings & Risk Assessment", ""])
                for item in ai.risks_and_warnings:
                    lines.append(f"- {item}")
                lines.append("")

            if ai.prioritized_next_steps:
                lines.extend(["### Prioritized Next Steps", ""])
                for idx, step in enumerate(ai.prioritized_next_steps, 1):
                    lines.append(f"{idx}. {step}")
                lines.append("")

            lines.extend(
                [
                    f"> [!NOTE]\n> **Confidence & Limitations:** {ai.confidence_explanation}",
                    "",
                    "---",
                    "",
                ]
            )
        elif analysis.ai_status_message:
            lines.extend(
                [
                    "## 7. AI Analysis Status",
                    "",
                    f"> [!NOTE]\n> {analysis.ai_status_message}",
                    "",
                    "---",
                    "",
                ]
            )

        # Inaccessible Locations
        if scan.diagnostics:
            lines.extend(
                [
                    f"## 8. Scan Diagnostics & Inaccessible Locations ({len(scan.diagnostics)})",
                    "",
                    "| Type | Path | Details |",
                    "| :--- | :--- | :--- |",
                ]
            )
            for diag in scan.diagnostics:
                lines.append(
                    f"| `{diag.error_type}` | `{redact_path(diag.path, self.redact_paths)}` | {diag.message} |"
                )
            lines.append("")

        return "\n".join(lines)

    def save_to_file(
        self,
        analysis: AnalysisResult,
        target_path: Path | str,
        overwrite: bool = False,
    ) -> Path:
        """Export analysis report to a Markdown file safely.

        Args:
            analysis: The AnalysisResult to export.
            target_path: Destination path for Markdown report.
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
            raise ReportError(f"Failed to write Markdown report to {dest}: {exc}") from exc
