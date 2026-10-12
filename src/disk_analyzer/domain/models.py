"""Domain models representing filesystem entities, scan statistics, and AI analyses."""

from datetime import datetime

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """Information about an individual file discovered during scanning."""

    path: str = Field(description="Normalized path to the file")
    name: str = Field(description="File basename")
    size_bytes: int = Field(ge=0, description="Logical file size in bytes (st_size)")
    allocated_bytes: int = Field(
        ge=0, description="Allocated disk space in bytes (st_blocks * 512)"
    )
    extension: str = Field(default="", description="Lower-cased file extension, e.g. '.tar.gz'")
    is_symlink: bool = Field(default=False, description="Whether the file entry is a symlink")
    modified_at: datetime | None = Field(default=None, description="Last modification timestamp")


class DirectoryStats(BaseModel):
    """Aggregated statistics for a directory and its nested contents."""

    path: str = Field(description="Normalized directory path")
    name: str = Field(description="Directory basename")
    logical_size_bytes: int = Field(ge=0, description="Total logical size of files contained")
    allocated_size_bytes: int = Field(ge=0, description="Total allocated size of files contained")
    file_count: int = Field(ge=0, description="Total number of files in this directory subtree")
    dir_count: int = Field(
        ge=0, description="Total number of subdirectories in this directory subtree"
    )
    depth: int = Field(ge=0, description="Depth level relative to the scan root")


class ScanDiagnostic(BaseModel):
    """Diagnostic error or warning encountered during scanning."""

    path: str = Field(description="Filesystem path that generated the diagnostic")
    error_type: str = Field(
        description="Category of error, e.g., 'PermissionDenied', 'FileNotFound'"
    )
    message: str = Field(description="Human-readable error explanation")


class ScanResult(BaseModel):
    """Immutable result of a recursive filesystem scan."""

    root_path: str = Field(description="Absolute root directory of the scan")
    scanned_at: datetime = Field(description="Timestamp when the scan completed")
    duration_seconds: float = Field(ge=0.0, description="Total wall-clock duration of the scan")
    total_files: int = Field(ge=0, description="Total number of non-directory files inspected")
    total_directories: int = Field(ge=0, description="Total number of directories inspected")
    total_logical_size_bytes: int = Field(ge=0, description="Sum of logical file sizes")
    total_allocated_size_bytes: int = Field(
        ge=0, description="Sum of allocated disk space (deduplicated)"
    )
    largest_files: list[FileInfo] = Field(default_factory=list, description="Top N largest files")
    largest_directories: list[DirectoryStats] = Field(
        default_factory=list, description="Top N largest directories"
    )
    diagnostics: list[ScanDiagnostic] = Field(
        default_factory=list, description="Encountered errors and warnings"
    )
    excluded_patterns: list[str] = Field(
        default_factory=list, description="Exclusion patterns applied during scan"
    )


class StorageCategorySummary(BaseModel):
    """Summary of disk usage grouped by recognizable heuristic category."""

    category_id: str = Field(description="Machine-readable identifier for category")
    name: str = Field(description="Display name of category")
    description: str = Field(description="Explanation of what this category encompasses")
    total_size_bytes: int = Field(ge=0, description="Aggregated logical bytes in this category")
    file_count: int = Field(ge=0, description="Number of files categorized")
    percentage_of_total: float = Field(
        ge=0.0, le=100.0, description="Percentage of total scanned logical size"
    )
    sample_paths: list[str] = Field(
        default_factory=list, description="Sample paths representative of this category"
    )
    confidence: str = Field(
        default="medium", description="Confidence level: 'high', 'medium', or 'low'"
    )
    is_potential_cleanup: bool = Field(
        default=False,
        description="Whether this category may contain disposable or regenerable data",
    )
    rationale: str = Field(description="Heuristic basis for classification and cleanup potential")


class ExtensionSummary(BaseModel):
    """Aggregated usage for a specific file extension."""

    extension: str = Field(description="File extension (or '(no extension)')")
    total_size_bytes: int = Field(ge=0, description="Aggregated logical bytes for extension")
    file_count: int = Field(ge=0, description="Number of files with this extension")
    percentage_of_total: float = Field(
        ge=0.0, le=100.0, description="Percentage of total scanned logical size"
    )


class DiskUsageInfo(BaseModel):
    """Filesystem capacity and usage from statvfs / shutil.disk_usage."""

    total_bytes: int = Field(ge=0, description="Total filesystem capacity")
    used_bytes: int = Field(ge=0, description="Currently used filesystem space")
    free_bytes: int = Field(ge=0, description="Available filesystem space")
    percent_used: float = Field(ge=0.0, le=100.0, description="Used space percentage")


class RecommendationItem(BaseModel):
    """Deterministic, evidence-based cleanup or maintenance recommendation."""

    id: str = Field(description="Unique recommendation ID")
    title: str = Field(description="Short human-readable title")
    category: str = Field(description="Related storage category")
    priority: str = Field(description="Priority: 'high', 'medium', or 'low'")
    description: str = Field(description="Detailed explanation of the findings")
    estimated_reclaimable_bytes: int | None = Field(
        default=None,
        description="Conservative estimate of potential reclaimable bytes, if defensible",
    )
    confidence: str = Field(
        default="medium", description="Confidence level: 'high', 'medium', or 'low'"
    )
    target_paths: list[str] = Field(
        default_factory=list, description="Paths relevant to this recommendation"
    )
    risks_and_caveats: str = Field(description="Risks, side-effects, and precautions before action")
    suggested_actions: list[str] = Field(
        default_factory=list,
        description="Non-destructive informational next steps for user to inspect",
    )


class AISummary(BaseModel):
    """AI-generated executive summary and recommendations validated against schema."""

    executive_summary: str = Field(description="High-level overview of disk space utilization")
    main_storage_consumers: list[str] = Field(
        default_factory=list, description="Key directories or patterns occupying majority space"
    )
    significant_observations: list[str] = Field(
        default_factory=list, description="Notable patterns, anomalies, or caches"
    )
    cleanup_candidates: list[str] = Field(
        default_factory=list, description="Items that user might safely consider for manual review"
    )
    expected_benefits: str = Field(
        description="Potential space recovery explanation with explicit limitations"
    )
    risks_and_warnings: list[str] = Field(
        default_factory=list,
        description="Potential side-effects, warnings, and dependencies to verify",
    )
    prioritized_next_steps: list[str] = Field(
        default_factory=list, description="Clear, ordered steps for user to take"
    )
    confidence_explanation: str = Field(
        description="Explanation of AI confidence and verification boundaries"
    )


class AnalysisResult(BaseModel):
    """Complete consolidated analysis including deterministic metrics and optional AI summary."""

    scan_result: ScanResult = Field(description="Underlying raw scan result")
    disk_usage: DiskUsageInfo | None = Field(default=None, description="Filesystem volume stats")
    top_categories: list[StorageCategorySummary] = Field(
        default_factory=list, description="Categorized disk usage"
    )
    top_extensions: list[ExtensionSummary] = Field(
        default_factory=list, description="File extension distribution"
    )
    recommendations: list[RecommendationItem] = Field(
        default_factory=list, description="Deterministic recommendations"
    )
    ai_summary: AISummary | None = Field(
        default=None, description="AI-generated summary when available"
    )
    ai_status_message: str | None = Field(
        default=None, description="Status or error message concerning AI generation"
    )
    analyzed_at: datetime = Field(description="Timestamp when analysis completed")
