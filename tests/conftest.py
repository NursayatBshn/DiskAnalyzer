"""Shared test fixtures for AI Disk Analyzer."""

from pathlib import Path

import pytest

from disk_analyzer.domain.models import (
    AISummary,
    AnalysisResult,
    DirectoryStats,
    DiskUsageInfo,
    ExtensionSummary,
    FileInfo,
    RecommendationItem,
    ScanResult,
    StorageCategorySummary,
)


@pytest.fixture
def synthetic_fs(tmp_path: Path) -> Path:
    """Create a realistic synthetic directory hierarchy for scanner and analysis testing.

    Structure:
    ├── file_root.txt (1000 bytes)
    ├── unicode_файл_🚀.dat (500 bytes)
    ├── file with spaces.log (2000 bytes)
    ├── empty.txt (0 bytes)
    ├── .cache/
    │   └── app/
    │       └── cache.bin (5000 bytes)
    ├── .venv/
    │   └── lib/
    │       └── package.py (1500 bytes)
    ├── node_modules/
    │   └── pkg/
    │       └── index.js (3000 bytes)
    ├── target/
    │   └── debug/
    │       └── app.bin (8000 bytes)
    ├── .local/
    │   └── share/
    │       └── Trash/
    │           └── files/
    │               └── deleted.doc (4000 bytes)
    └── nested/
        ├── depth1/
        │   └── depth2/
        │       └── deep.txt (250 bytes)
        └── ignored_git/
            └── .git/
                └── config (100 bytes)
    """
    root = tmp_path / "synthetic_root"
    root.mkdir()

    # Plain root files
    (root / "file_root.txt").write_bytes(b"A" * 1000)
    (root / "unicode_файл_🚀.dat").write_bytes(b"B" * 500)
    (root / "file with spaces.log").write_bytes(b"C" * 2000)
    (root / "empty.txt").write_bytes(b"")

    # Cache folder
    cache_dir = root / ".cache" / "app"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache.bin").write_bytes(b"D" * 5000)

    # Venv folder
    venv_dir = root / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "package.py").write_bytes(b"E" * 1500)

    # Node modules folder
    nm_dir = root / "node_modules" / "pkg"
    nm_dir.mkdir(parents=True)
    (nm_dir / "index.js").write_bytes(b"F" * 3000)

    # Build target
    target_dir = root / "target" / "debug"
    target_dir.mkdir(parents=True)
    (target_dir / "app.bin").write_bytes(b"G" * 8000)

    # Trash folder
    trash_dir = root / ".local" / "share" / "Trash" / "files"
    trash_dir.mkdir(parents=True)
    (trash_dir / "deleted.doc").write_bytes(b"H" * 4000)

    # Deep nesting
    deep_dir = root / "nested" / "depth1" / "depth2"
    deep_dir.mkdir(parents=True)
    (deep_dir / "deep.txt").write_bytes(b"I" * 250)

    # Git directory to test exclusions
    git_dir = root / "nested" / "ignored_git" / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_bytes(b"J" * 100)

    return root


@pytest.fixture
def sample_scan_result() -> ScanResult:
    """Fixture providing a mock ScanResult."""
    return ScanResult(
        root_path="/home/testuser/workspace",
        scanned_at="2026-10-12T12:00:00Z",
        duration_seconds=1.23,
        total_files=24,
        total_directories=8,
        total_logical_size_bytes=25350,
        total_allocated_size_bytes=32768,
        largest_files=[
            FileInfo(
                path="/home/testuser/workspace/target/debug/app.bin",
                name="app.bin",
                size_bytes=8000,
                allocated_bytes=8192,
                extension=".bin",
            ),
            FileInfo(
                path="/home/testuser/workspace/.cache/app/cache.bin",
                name="cache.bin",
                size_bytes=5000,
                allocated_bytes=8192,
                extension=".bin",
            ),
            FileInfo(
                path="/home/testuser/workspace/.local/share/Trash/files/deleted.doc",
                name="deleted.doc",
                size_bytes=4000,
                allocated_bytes=4096,
                extension=".doc",
            ),
        ],
        largest_directories=[
            DirectoryStats(
                path="/home/testuser/workspace/target",
                name="target",
                logical_size_bytes=8000,
                allocated_size_bytes=8192,
                file_count=1,
                dir_count=1,
                depth=1,
            ),
            DirectoryStats(
                path="/home/testuser/workspace/.cache",
                name=".cache",
                logical_size_bytes=5000,
                allocated_size_bytes=8192,
                file_count=1,
                dir_count=1,
                depth=1,
            ),
        ],
        diagnostics=[],
        excluded_patterns=["**/.git/**"],
    )


@pytest.fixture
def sample_analysis_result(sample_scan_result: ScanResult) -> AnalysisResult:
    """Fixture providing a complete mock AnalysisResult."""
    return AnalysisResult(
        scan_result=sample_scan_result,
        disk_usage=DiskUsageInfo(
            total_bytes=100_000_000_000,
            used_bytes=45_000_000_000,
            free_bytes=55_000_000_000,
            percent_used=45.0,
        ),
        top_categories=[
            StorageCategorySummary(
                category_id="build_artifacts",
                name="Build Artifacts & Compiled Output",
                description="Compiler output",
                total_size_bytes=8000,
                file_count=1,
                percentage_of_total=31.56,
                sample_paths=["/home/testuser/workspace/target/debug/app.bin"],
                confidence="high",
                is_potential_cleanup=True,
                rationale="Compiler generated artifacts.",
            ),
            StorageCategorySummary(
                category_id="trash",
                name="Trash & Recycled Items",
                description="Deleted items",
                total_size_bytes=4000,
                file_count=1,
                percentage_of_total=15.78,
                sample_paths=["/home/testuser/workspace/.local/share/Trash/files/deleted.doc"],
                confidence="high",
                is_potential_cleanup=True,
                rationale="Trash bin items.",
            ),
        ],
        top_extensions=[
            ExtensionSummary(
                extension=".bin",
                total_size_bytes=13000,
                file_count=2,
                percentage_of_total=51.28,
            ),
            ExtensionSummary(
                extension=".doc",
                total_size_bytes=4000,
                file_count=1,
                percentage_of_total=15.78,
            ),
        ],
        recommendations=[
            RecommendationItem(
                id="rec-trash-cleanup",
                title="Empty desktop trash (3.91 KiB)",
                category="Trash & Recycled Items",
                priority="high",
                description="Found items in trash.",
                estimated_reclaimable_bytes=4000,
                confidence="high",
                target_paths=["/home/testuser/workspace/.local/share/Trash/files/deleted.doc"],
                risks_and_caveats="Permanently deletes files in trash.",
                suggested_actions=["Empty trash manually."],
            ),
        ],
        ai_summary=AISummary(
            executive_summary="Target directory primarily contains build outputs and cached data.",
            main_storage_consumers=["target/ directory", ".cache/ directory"],
            significant_observations=["Compiled binaries account for over 30% of scanned bytes."],
            cleanup_candidates=["Emptying desktop trash", "Cleaning target/ build folder"],
            expected_benefits="Potentially recovering up to 12 KiB.",
            risks_and_warnings=["Clean builds will require full recompilation."],
            prioritized_next_steps=[
                "Verify trash items and empty.",
                "Run cargo clean if finished with build.",
            ],
            confidence_explanation="High confidence based on standard build patterns.",
        ),
        ai_status_message="AI summary generated successfully via Google Gemini.",
        analyzed_at="2026-10-12T12:00:01Z",
    )
