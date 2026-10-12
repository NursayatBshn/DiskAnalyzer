"""Rich terminal reporter for AI Disk Analyzer."""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from disk_analyzer import __version__
from disk_analyzer.domain.models import AnalysisResult
from disk_analyzer.utils.formatting import format_bytes, format_duration, redact_path


class TerminalReporter:
    """Renders comprehensive, stylized terminal reports using Rich."""

    def __init__(self, console: Console | None = None, redact_paths: bool = True) -> None:
        """Initialize TerminalReporter.

        Args:
            console: Optional custom Rich Console instance.
            redact_paths: Whether to redact user home directories.
        """
        self.console = console or Console()
        self.redact_paths = redact_paths

    def render(self, analysis: AnalysisResult) -> None:
        """Render the complete analysis report to the terminal.

        Args:
            analysis: The AnalysisResult to display.
        """
        scan = analysis.scan_result

        # 1. Header Banner
        banner_text = Text()
        banner_text.append("AI Disk Analyzer ", style="bold cyan")
        banner_text.append(f"v{__version__}\n", style="dim cyan")
        banner_text.append(
            f"Scan Root: {redact_path(scan.root_path, self.redact_paths)}", style="bold white"
        )
        self.console.print(Panel(banner_text, box=box.ROUNDED, border_style="cyan"))

        # 2. Filesystem Volume Status (if available)
        if analysis.disk_usage:
            du = analysis.disk_usage
            fs_table = Table.grid(padding=(0, 2))
            fs_table.add_column(style="bold")
            fs_table.add_column()
            fs_table.add_column(style="bold")
            fs_table.add_column()
            fs_table.add_column(style="bold")
            fs_table.add_column()

            fs_table.add_row(
                "Total Capacity:",
                format_bytes(du.total_bytes),
                "Used Space:",
                f"{format_bytes(du.used_bytes)} ({du.percent_used}%)",
                "Available Space:",
                f"[green]{format_bytes(du.free_bytes)}[/green]",
            )
            self.console.print(
                Panel(
                    fs_table,
                    title="[bold blue]Filesystem Volume Capacity[/bold blue]",
                    border_style="blue",
                    box=box.ROUNDED,
                )
            )

        # 3. Scan Summary Metrics Table
        summary_table = Table(
            title="Scan Summary",
            box=box.SIMPLE_HEAVY,
            header_style="bold magenta",
        )
        summary_table.add_column("Scanned Files", justify="right")
        summary_table.add_column("Scanned Directories", justify="right")
        summary_table.add_column("Logical Size", justify="right")
        summary_table.add_column("Allocated Size", justify="right")
        summary_table.add_column("Duration", justify="right")
        summary_table.add_column("Diagnostics/Errors", justify="right")

        err_style = "[red]" if scan.diagnostics else "[green]"
        summary_table.add_row(
            f"{scan.total_files:,}",
            f"{scan.total_directories:,}",
            format_bytes(scan.total_logical_size_bytes),
            format_bytes(scan.total_allocated_size_bytes),
            format_duration(scan.duration_seconds),
            f"{err_style}{len(scan.diagnostics)}[/]",
        )
        self.console.print(summary_table)

        # 4. Top Directories Table
        if scan.largest_directories:
            dirs_table = Table(
                title=f"Top {len(scan.largest_directories)} Largest Directories",
                box=box.ROUNDED,
                header_style="bold cyan",
            )
            dirs_table.add_column("#", justify="right", style="dim", width=4)
            dirs_table.add_column("Directory Path", style="bold white")
            dirs_table.add_column("Size", justify="right", style="yellow")
            dirs_table.add_column("Files", justify="right")
            dirs_table.add_column("% Scan", justify="right", style="green")

            for idx, d in enumerate(scan.largest_directories, start=1):
                pct = (
                    (d.logical_size_bytes / scan.total_logical_size_bytes * 100.0)
                    if scan.total_logical_size_bytes > 0
                    else 0.0
                )
                dirs_table.add_row(
                    str(idx),
                    redact_path(d.path, self.redact_paths),
                    format_bytes(d.logical_size_bytes),
                    f"{d.file_count:,}",
                    f"{pct:.1f}%",
                )
            self.console.print(dirs_table)

        # 5. Top Largest Files Table
        if scan.largest_files:
            files_table = Table(
                title=f"Top {len(scan.largest_files)} Largest Files",
                box=box.ROUNDED,
                header_style="bold cyan",
            )
            files_table.add_column("#", justify="right", style="dim", width=4)
            files_table.add_column("File Path", style="white")
            files_table.add_column("Size", justify="right", style="yellow")
            files_table.add_column("Allocated", justify="right", style="dim")
            files_table.add_column("Type", justify="center", style="cyan")

            for idx, f in enumerate(scan.largest_files, start=1):
                files_table.add_row(
                    str(idx),
                    redact_path(f.path, self.redact_paths),
                    format_bytes(f.size_bytes),
                    format_bytes(f.allocated_bytes),
                    f.extension or "(none)",
                )
            self.console.print(files_table)

        # 6. Storage Categories Breakdown Table
        if analysis.top_categories:
            cat_table = Table(
                title="Storage Pattern Breakdown (Heuristic)",
                box=box.ROUNDED,
                header_style="bold green",
            )
            cat_table.add_column("Category", style="bold")
            cat_table.add_column("Size", justify="right", style="yellow")
            cat_table.add_column("% Total", justify="right", style="green")
            cat_table.add_column("Files", justify="right")
            cat_table.add_column("Confidence", justify="center")
            cat_table.add_column("Cleanup Candidate?", justify="center")

            for c in analysis.top_categories:
                cleanup_badge = (
                    "[bold green]Yes[/bold green]" if c.is_potential_cleanup else "[dim]No[/dim]"
                )
                conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(
                    c.confidence, "white"
                )
                cat_table.add_row(
                    c.name,
                    format_bytes(c.total_size_bytes),
                    f"{c.percentage_of_total:.1f}%",
                    f"{c.file_count:,}",
                    f"[{conf_color}]{c.confidence}[/{conf_color}]",
                    cleanup_badge,
                )
            self.console.print(cat_table)

        # 7. File Extensions Table
        if analysis.top_extensions:
            ext_table = Table(
                title="File Extension Distribution",
                box=box.SIMPLE,
                header_style="bold cyan",
            )
            ext_table.add_column("Extension", style="cyan")
            ext_table.add_column("Total Size", justify="right", style="yellow")
            ext_table.add_column("Files", justify="right")
            ext_table.add_column("% Total", justify="right", style="green")

            for ext in analysis.top_extensions:
                ext_table.add_row(
                    ext.extension,
                    format_bytes(ext.total_size_bytes),
                    f"{ext.file_count:,}",
                    f"{ext.percentage_of_total:.1f}%",
                )
            self.console.print(ext_table)

        # 8. Deterministic Recommendations Panel
        if analysis.recommendations:
            self.console.print("\n[bold yellow]═══ Deterministic Recommendations ═══[/bold yellow]")
            for rec in analysis.recommendations:
                p_color = {"high": "bold red", "medium": "bold yellow", "low": "bold cyan"}.get(
                    rec.priority, "white"
                )
                rec_content = Text()
                rec_content.append(f"[{rec.priority.upper()}] ", style=p_color)
                rec_content.append(f"{rec.title}\n", style="bold white")
                rec_content.append(f"{rec.description}\n\n", style="white")

                if rec.estimated_reclaimable_bytes is not None:
                    rec_content.append(
                        f"• Potential Reclaimable: {format_bytes(rec.estimated_reclaimable_bytes)} "
                        f"(Confidence: {rec.confidence})\n",
                        style="green",
                    )
                else:
                    rec_content.append(
                        "• Potential Reclaimable: Not established without deeper audit\n",
                        style="dim",
                    )

                rec_content.append(
                    f"• Risks & Precautions: {rec.risks_and_caveats}\n", style="yellow"
                )
                rec_content.append("• Suggested Actions:\n", style="bold")
                for act in rec.suggested_actions:
                    rec_content.append(f"    - {act}\n", style="cyan")

                self.console.print(
                    Panel(
                        rec_content,
                        border_style="yellow" if rec.priority == "high" else "dim yellow",
                        box=box.ROUNDED,
                    )
                )

        # 9. AI Summary Panel (if available or note status)
        if analysis.ai_summary:
            ai = analysis.ai_summary
            ai_text = Text()
            ai_text.append(f"{ai.executive_summary}\n\n", style="italic white")

            if ai.main_storage_consumers:
                ai_text.append("Main Storage Consumers:\n", style="bold cyan")
                for item in ai.main_storage_consumers:
                    ai_text.append(f"  • {item}\n", style="white")
                ai_text.append("\n")

            if ai.significant_observations:
                ai_text.append("Significant Observations:\n", style="bold cyan")
                for item in ai.significant_observations:
                    ai_text.append(f"  • {item}\n", style="white")
                ai_text.append("\n")

            if ai.cleanup_candidates:
                ai_text.append("Potential Cleanup Candidates:\n", style="bold green")
                for item in ai.cleanup_candidates:
                    ai_text.append(f"  • {item}\n", style="green")
                ai_text.append("\n")

            if ai.risks_and_warnings:
                ai_text.append("Risks & Warnings:\n", style="bold red")
                for item in ai.risks_and_warnings:
                    ai_text.append(f"  ! {item}\n", style="yellow")
                ai_text.append("\n")

            if ai.prioritized_next_steps:
                ai_text.append("Prioritized Next Steps:\n", style="bold yellow")
                for idx, step in enumerate(ai.prioritized_next_steps, 1):
                    ai_text.append(f"  {idx}. {step}\n", style="white")
                ai_text.append("\n")

            ai_text.append(f"Confidence Assessment: {ai.confidence_explanation}", style="dim")

            self.console.print(
                Panel(
                    ai_text,
                    title="[bold magenta]Google Gemini AI Intelligent Assessment[/bold magenta]",
                    border_style="magenta",
                    box=box.ROUNDED,
                )
            )
        elif analysis.ai_status_message:
            self.console.print(
                Panel(
                    f"[dim]{analysis.ai_status_message}[/dim]",
                    title="[dim]AI Summary Status[/dim]",
                    border_style="dim",
                    box=box.ROUNDED,
                )
            )

        # 10. Diagnostics & Warnings (if any)
        if scan.diagnostics:
            diag_table = Table(
                title=f"Scan Diagnostics & Inaccessible Locations ({len(scan.diagnostics)})",
                box=box.ROUNDED,
                header_style="bold red",
            )
            diag_table.add_column("Type", style="red", width=18)
            diag_table.add_column("Path", style="white")
            diag_table.add_column("Details", style="dim")

            for diag in scan.diagnostics[:10]:
                diag_table.add_row(
                    diag.error_type,
                    redact_path(diag.path, self.redact_paths),
                    diag.message,
                )
            if len(scan.diagnostics) > 10:
                diag_table.add_row(
                    "...",
                    f"... and {len(scan.diagnostics) - 10} more inaccessible locations",
                    "Run with --verbose or check exported report for full list",
                )
            self.console.print(diag_table)
