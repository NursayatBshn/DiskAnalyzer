"""Command-line interface for AI Disk Analyzer using Typer and Rich."""

import sys
from enum import StrEnum
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from disk_analyzer import __version__
from disk_analyzer.ai.gemini_provider import GeminiProvider
from disk_analyzer.ai.prompt_builder import PromptBuilder
from disk_analyzer.ai.summary_service import SummaryService
from disk_analyzer.analysis.analyzer import DiskAnalyzer
from disk_analyzer.config import get_safe_config_dict, load_config
from disk_analyzer.exceptions import (
    ConfigError,
    FileAlreadyExistsError,
    NotADirectoryError,
    PathNotFoundError,
    ScanError,
)
from disk_analyzer.reporting.json_report import JsonReporter
from disk_analyzer.reporting.markdown_report import MarkdownReporter
from disk_analyzer.reporting.terminal_report import TerminalReporter
from disk_analyzer.scanner.filesystem_scanner import FilesystemScanner

app = typer.Typer(
    name="disk-analyzer",
    help="Intelligent disk space analysis utility for Linux powered by Google Gemini.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
error_console = Console(stderr=True)


class OutputFormat(StrEnum):
    """Supported report output formats."""

    TERMINAL = "terminal"
    JSON = "json"
    MARKDOWN = "markdown"


def version_callback(value: bool) -> None:
    """Print the application version and exit."""
    if value:
        console.print(
            f"[bold cyan]AI Disk Analyzer[/bold cyan] version [bold white]{__version__}[/bold white]"
        )
        raise typer.Exit(code=0)


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show application version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """AI Disk Analyzer root callback."""


@app.command("scan")
def scan_command(
    path: Path = typer.Argument(
        Path("."),
        help="Directory path to scan and analyze.",
        show_default=True,
    ),
    top: int | None = typer.Option(
        None,
        "--top",
        "-t",
        help="Number of largest files and directories to display.",
    ),
    max_depth: int | None = typer.Option(
        None,
        "--max-depth",
        "-d",
        help="Maximum directory recursion depth limit.",
    ),
    exclude: list[str] | None = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Glob pattern to exclude from scan (can be repeated).",
    ),
    follow_symlinks: bool = typer.Option(
        False,
        "--follow-symlinks",
        help="Follow symbolic links (disabled by default for safety).",
    ),
    no_ai: bool = typer.Option(
        False,
        "--no-ai",
        help="Disable Gemini AI summary (run purely offline and deterministic).",
    ),
    format_: OutputFormat = typer.Option(
        OutputFormat.TERMINAL,
        "--format",
        "-f",
        help="Report format: terminal, json, or markdown.",
        case_sensitive=False,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file path to save exported report.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow overwriting destination report file if it already exists.",
    ),
    redact_paths: bool = typer.Option(
        True,
        "--redact-paths/--no-redact-paths",
        help="Redact user home directory prefixes from reports and prompts for privacy.",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress scan progress indicators and extra messages.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Display verbose diagnostics and stack traces on error.",
    ),
) -> None:
    """Scan a filesystem directory and produce an intelligent storage analysis report."""
    # 1. Load configuration
    try:
        cfg = load_config(config_file)
    except ConfigError as exc:
        error_console.print(f"[bold red]Configuration Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc

    # Merge CLI options with config defaults
    top_items = top if top is not None else cfg.general.top_items
    depth_limit = max_depth if max_depth is not None else cfg.general.max_depth
    symlinks = follow_symlinks or cfg.general.follow_symlinks
    ai_enabled = (not no_ai) and cfg.ai.enabled
    exclusions = list(cfg.scanner.exclude)
    if exclude:
        exclusions.extend(exclude)

    # 2. Filesystem scanning with progress indicator
    scanner = FilesystemScanner(
        top_items=top_items,
        max_depth=depth_limit,
        follow_symlinks=symlinks,
        exclude_patterns=exclusions,
        exclude_system_virtual_fs=cfg.scanner.exclude_system_virtual_fs,
    )

    try:
        if not quiet and format_ == OutputFormat.TERMINAL:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task_id = progress.add_task(f"Scanning [bold]{path}[/bold]...", total=None)

                def update_cb(files_count: int, dirs_count: int, current_path: str) -> None:
                    progress.update(
                        task_id,
                        description=f"Scanning: {files_count:,} files, {dirs_count:,} dirs ({current_path[:40]}...)",
                    )

                scanner.progress_callback = update_cb
                scan_result = scanner.scan(path)
        else:
            scan_result = scanner.scan(path)

    except PathNotFoundError as exc:
        error_console.print(f"[bold red]Path Not Found:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc
    except NotADirectoryError as exc:
        error_console.print(f"[bold red]Not a Directory:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc
    except ScanError as exc:
        error_console.print(f"[bold red]Filesystem Scan Error:[/bold red] {exc}")
        raise typer.Exit(code=3) from exc
    except Exception as exc:
        error_console.print(f"[bold red]Unexpected Scan Failure:[/bold red] {exc}")
        if verbose:
            error_console.print_exception()
        raise typer.Exit(code=1) from exc

    # 3. Deterministic Analysis
    analyzer = DiskAnalyzer(
        classify_storage=cfg.analysis.classify_storage,
        top_extensions_count=cfg.analysis.top_extensions_count,
        estimate_reclaimable=cfg.analysis.estimate_reclaimable,
    )
    analysis = analyzer.analyze(scan_result)

    # 4. AI Summary (optional)
    if ai_enabled:
        provider = GeminiProvider(
            api_key=cfg.ai.api_key,
            model=cfg.ai.model,
            timeout_seconds=cfg.ai.timeout_seconds,
            max_retries=cfg.ai.max_retries,
        )
        prompt_builder = PromptBuilder(redact_paths=redact_paths)
        summary_service = SummaryService(
            gemini_provider=provider,
            prompt_builder=prompt_builder,
            ai_enabled=True,
        )

        if not quiet and format_ == OutputFormat.TERMINAL:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Analyzing with Google Gemini AI...", total=None)
                summary, status_msg = summary_service.generate_summary(analysis)
        else:
            summary, status_msg = summary_service.generate_summary(analysis)

        analysis.ai_summary = summary
        analysis.ai_status_message = status_msg
    else:
        analysis.ai_status_message = "AI analysis disabled by user request (--no-ai)."

    # 5. Output Reporting
    if format_ == OutputFormat.TERMINAL and not output:
        reporter = TerminalReporter(console=console, redact_paths=redact_paths)
        reporter.render(analysis)
        return

    # Handle file export or non-terminal formats
    if format_ == OutputFormat.JSON:
        json_reporter = JsonReporter(redact_paths=redact_paths)
        if output:
            try:
                saved = json_reporter.save_to_file(analysis, output, overwrite=overwrite)
                console.print(
                    f"[bold green]✓[/bold green] JSON report saved to: [cyan]{saved}[/cyan]"
                )
            except FileAlreadyExistsError as exc:
                error_console.print(f"[bold red]File Exists Error:[/bold red] {exc}")
                raise typer.Exit(code=1) from exc
        else:
            sys.stdout.write(json_reporter.render(analysis) + "\n")
            sys.stdout.flush()

    elif format_ == OutputFormat.MARKDOWN:
        md_reporter = MarkdownReporter(redact_paths=redact_paths)
        if output:
            try:
                saved = md_reporter.save_to_file(analysis, output, overwrite=overwrite)
                console.print(
                    f"[bold green]✓[/bold green] Markdown report saved to: [cyan]{saved}[/cyan]"
                )
            except FileAlreadyExistsError as exc:
                error_console.print(f"[bold red]File Exists Error:[/bold red] {exc}")
                raise typer.Exit(code=1) from exc
        else:
            sys.stdout.write(md_reporter.render(analysis) + "\n")
            sys.stdout.flush()

    elif format_ == OutputFormat.TERMINAL and output:
        # Also allow saving markdown representation when terminal requested with output file
        md_reporter = MarkdownReporter(redact_paths=redact_paths)
        try:
            saved = md_reporter.save_to_file(analysis, output, overwrite=overwrite)
            console.print(f"[bold green]✓[/bold green] Report saved to: [cyan]{saved}[/cyan]")
        except FileAlreadyExistsError as exc:
            error_console.print(f"[bold red]File Exists Error:[/bold red] {exc}")
            raise typer.Exit(code=1) from exc


@app.command("analyze")
def analyze_command(
    path: Path = typer.Argument(Path("."), help="Directory path to scan and analyze."),
    top: int | None = typer.Option(None, "--top", "-t", help="Number of largest items to show."),
    no_ai: bool = typer.Option(False, "--no-ai", help="Disable AI summary."),
    format_: OutputFormat = typer.Option(
        OutputFormat.TERMINAL, "--format", "-f", help="Report format."
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing report file."),
) -> None:
    """Analyze storage consumption and categorize usage patterns (alias for scan)."""
    scan_command(
        path=path,
        top=top,
        max_depth=None,
        exclude=None,
        follow_symlinks=False,
        no_ai=no_ai,
        format_=format_,
        output=output,
        overwrite=overwrite,
        redact_paths=True,
        config_file=None,
        quiet=False,
        verbose=False,
    )


@app.command("config")
def config_command(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file to inspect.",
    ),
) -> None:
    """Display active configuration with API keys masked."""
    try:
        cfg = load_config(config_file)
    except ConfigError as exc:
        error_console.print(f"[bold red]Configuration Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc

    safe_dict = get_safe_config_dict(cfg)
    console.print(
        "[bold cyan]AI Disk Analyzer Active Configuration[/bold cyan] (API keys masked):\n"
    )
    console.print(yaml.dump(safe_dict, sort_keys=False))


@app.command("check-ai")
def check_ai_command(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file.",
    ),
) -> None:
    """Check Google Gemini API credentials and network connectivity."""
    try:
        cfg = load_config(config_file)
    except ConfigError as exc:
        error_console.print(f"[bold red]Configuration Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc

    if not cfg.ai.api_key:
        error_console.print(
            "[bold yellow]Warning:[/bold yellow] No Gemini API key detected.\n"
            "Set [cyan]GEMINI_API_KEY[/cyan] in your environment or in .env."
        )
        raise typer.Exit(code=1)

    provider = GeminiProvider(
        api_key=cfg.ai.api_key,
        model=cfg.ai.model,
        timeout_seconds=cfg.ai.timeout_seconds,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Verifying Gemini API connectivity...", total=None)
        success, message = provider.check_connectivity()

    if success:
        console.print(f"[bold green]✓ Success:[/bold green] {message}")
    else:
        error_console.print(f"[bold red]✗ Connectivity Failure:[/bold red] {message}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
