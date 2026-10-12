"""Unit tests for deterministic disk analysis and storage categorization."""

from unittest.mock import patch

from disk_analyzer.analysis.analyzer import DiskAnalyzer
from disk_analyzer.analysis.categories import (
    aggregate_categories,
    classify_file_into_category,
)
from disk_analyzer.domain.models import FileInfo, ScanResult


def test_classify_file_into_category():
    """Verify individual file categorization based on path patterns and extensions."""
    cache_file = FileInfo(
        path="/home/user/.cache/myapp/cache.db",
        name="cache.db",
        size_bytes=1024,
        allocated_bytes=1024,
        extension=".db",
    )
    rule = classify_file_into_category(cache_file)
    assert rule is not None
    assert rule.category_id == "general_cache"

    node_file = FileInfo(
        path="/home/user/project/node_modules/lodash/index.js",
        name="index.js",
        size_bytes=2048,
        allocated_bytes=2048,
        extension=".js",
    )
    rule = classify_file_into_category(node_file)
    assert rule is not None
    assert rule.category_id == "node_modules"

    build_file = FileInfo(
        path="/home/user/project/target/debug/build.bin",
        name="build.bin",
        size_bytes=4096,
        allocated_bytes=4096,
        extension=".bin",
    )
    rule = classify_file_into_category(build_file)
    assert rule is not None
    assert rule.category_id == "build_artifacts"

    trash_file = FileInfo(
        path="/home/user/.local/share/Trash/files/old.png",
        name="old.png",
        size_bytes=512,
        allocated_bytes=512,
        extension=".png",
    )
    rule = classify_file_into_category(trash_file)
    assert rule is not None
    assert rule.category_id == "trash"

    media_file = FileInfo(
        path="/home/user/videos/movie.mp4",
        name="movie.mp4",
        size_bytes=500000000,
        allocated_bytes=500000000,
        extension=".mp4",
    )
    rule = classify_file_into_category(media_file)
    assert rule is not None
    assert rule.category_id == "media"

    vm_file = FileInfo(
        path="/home/user/images/archlinux.iso",
        name="archlinux.iso",
        size_bytes=1000000000,
        allocated_bytes=1000000000,
        extension=".iso",
    )
    rule = classify_file_into_category(vm_file)
    assert rule is not None
    assert rule.category_id == "virtual_machines_disk_images"


def test_aggregate_categories():
    """Verify category summaries calculation and percentages."""
    files = [
        FileInfo(
            path="/home/user/.cache/file1.bin",
            name="file1.bin",
            size_bytes=6000,
            allocated_bytes=6000,
            extension=".bin",
        ),
        FileInfo(
            path="/home/user/node_modules/file2.js",
            name="file2.js",
            size_bytes=4000,
            allocated_bytes=4000,
            extension=".js",
        ),
    ]
    summaries = aggregate_categories(files, total_logical_size=10000)

    assert len(summaries) >= 2
    top = summaries[0]
    assert top.category_id == "general_cache"
    assert top.total_size_bytes == 6000
    assert top.percentage_of_total == 60.0
    assert top.file_count == 1

    second = summaries[1]
    assert second.category_id == "node_modules"
    assert second.total_size_bytes == 4000
    assert second.percentage_of_total == 40.0


def test_analyzer_on_empty_scan():
    """Verify analyzer gracefully handles empty scan results."""
    empty_scan = ScanResult(
        root_path="/tmp/empty",
        scanned_at="2026-10-12T12:00:00Z",
        duration_seconds=0.01,
        total_files=0,
        total_directories=1,
        total_logical_size_bytes=0,
        total_allocated_size_bytes=0,
    )
    analyzer = DiskAnalyzer()
    analysis = analyzer.analyze(empty_scan)

    assert analysis.scan_result.total_files == 0
    assert len(analysis.top_categories) == 0
    assert len(analysis.top_extensions) == 0
    assert len(analysis.recommendations) == 0


def test_analyzer_extension_distribution(sample_scan_result: ScanResult):
    """Verify file extension grouping and ranking."""
    analyzer = DiskAnalyzer(top_extensions_count=5)
    analysis = analyzer.analyze(sample_scan_result)

    assert len(analysis.top_extensions) >= 2
    # .bin files: 8000 + 5000 = 13000 bytes
    ext_map = {e.extension: e for e in analysis.top_extensions}
    assert ".bin" in ext_map
    assert ext_map[".bin"].total_size_bytes == 13000
    assert ext_map[".bin"].file_count == 2


def test_analyzer_disk_usage_fallback():
    """Verify graceful handling when shutil.disk_usage raises OSError."""
    empty_scan = ScanResult(
        root_path="/tmp/nonexistent_mount",
        scanned_at="2026-10-12T12:00:00Z",
        duration_seconds=0.01,
        total_files=0,
        total_directories=1,
        total_logical_size_bytes=0,
        total_allocated_size_bytes=0,
    )
    analyzer = DiskAnalyzer()
    with patch("shutil.disk_usage", side_effect=OSError("Drive not accessible")):
        analysis = analyzer.analyze(empty_scan)

    assert analysis.disk_usage is None
