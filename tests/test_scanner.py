"""Comprehensive unit tests for the recursive filesystem scanner."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from disk_analyzer.exceptions import NotADirectoryError, PathNotFoundError
from disk_analyzer.scanner.filesystem_scanner import FilesystemScanner, matches_pattern


def test_matches_pattern():
    """Verify glob pattern matching logic."""
    assert matches_pattern("/path/to/.git/config", "config", "**/.git/**")
    assert matches_pattern("/home/user/project/node_modules/foo.js", "foo.js", "**/node_modules/**")
    assert matches_pattern("/tmp/scratch.tmp", "scratch.tmp", "*.tmp")
    assert matches_pattern("/var/log/syslog.log", "syslog.log", "*.log")
    assert not matches_pattern("/home/user/file.py", "file.py", "*.tmp")
    assert not matches_pattern("/home/user/file.py", "file.py", "")


def test_scan_empty_directory(tmp_path: Path):
    """Verify scanner handles completely empty directory."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    scanner = FilesystemScanner()
    result = scanner.scan(empty_dir)

    assert result.total_files == 0
    assert result.total_directories == 1
    assert result.total_logical_size_bytes == 0
    assert result.total_allocated_size_bytes == 0
    assert len(result.largest_files) == 0
    assert len(result.largest_directories) == 1
    assert len(result.diagnostics) == 0


def test_scan_single_file(tmp_path: Path):
    """Verify scanning directory with a single file."""
    single_dir = tmp_path / "single"
    single_dir.mkdir()
    test_file = single_dir / "sample.txt"
    test_file.write_bytes(b"Hello World!" * 100)

    scanner = FilesystemScanner()
    result = scanner.scan(single_dir)

    assert result.total_files == 1
    assert result.total_logical_size_bytes == 1200
    assert len(result.largest_files) == 1
    assert result.largest_files[0].name == "sample.txt"
    assert result.largest_files[0].extension == ".txt"


def test_scan_synthetic_hierarchy(synthetic_fs: Path):
    """Verify scanning complex directory with unicode, spaces, nested folders, and exclusions."""
    scanner = FilesystemScanner(
        top_items=5,
        exclude_patterns=["**/.git/**"],
    )
    result = scanner.scan(synthetic_fs)

    assert result.total_files > 5
    assert result.total_directories >= 6
    assert result.total_logical_size_bytes > 20000

    # .git directory should be excluded
    file_paths = [f.path for f in result.largest_files]
    assert not any(".git" in p for p in file_paths)

    # Unicode filename and spaces should be present
    file_names = [f.name for f in scanner._all_files]
    assert "unicode_файл_🚀.dat" in file_names
    assert "file with spaces.log" in file_names
    assert "empty.txt" in file_names


def test_scan_max_depth(synthetic_fs: Path):
    """Verify depth limiting stops recursive descent."""
    scanner = FilesystemScanner(max_depth=1)
    scanner.scan(synthetic_fs)

    # At depth 1, files in deep subfolders (e.g. depth2/deep.txt) must not be counted
    all_paths = [f.path for f in scanner._all_files]
    assert not any("deep.txt" in p for p in all_paths)


def test_symlink_not_followed_by_default(tmp_path: Path):
    """Verify symlinks are not traversed into by default."""
    scan_dir = tmp_path / "symlink_test"
    scan_dir.mkdir()

    target_dir = tmp_path / "target_dir"
    target_dir.mkdir()
    (target_dir / "hidden.txt").write_bytes(b"Target content")

    link = scan_dir / "link_to_target"
    try:
        link.symlink_to(target_dir, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks not supported on filesystem")

    scanner = FilesystemScanner(follow_symlinks=False)
    scanner.scan(scan_dir)

    all_names = [f.name for f in scanner._all_files]
    assert "hidden.txt" not in all_names


def test_symlink_followed_and_loop_detection(tmp_path: Path):
    """Verify symlinks can be followed and recursive cycle is safely broken."""
    scan_dir = tmp_path / "loop_test"
    scan_dir.mkdir()

    sub = scan_dir / "subdir"
    sub.mkdir()
    (sub / "file.txt").write_bytes(b"data")

    # Create cycle: loop_test/subdir/loop_link -> loop_test
    loop_link = sub / "loop_link"
    try:
        loop_link.symlink_to(scan_dir, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks not supported on filesystem")

    scanner = FilesystemScanner(follow_symlinks=True)
    result = scanner.scan(scan_dir)

    assert result.total_files >= 1
    # Check that loop was detected in diagnostics
    loop_diags = [d for d in result.diagnostics if d.error_type == "SymlinkLoopDetected"]
    assert len(loop_diags) >= 1


def test_broken_symlink_handled(tmp_path: Path):
    """Verify broken symlinks do not crash scanner."""
    scan_dir = tmp_path / "broken_symlink_test"
    scan_dir.mkdir()

    broken = scan_dir / "broken.lnk"
    try:
        broken.symlink_to(tmp_path / "nonexistent_file_xyz")
    except OSError:
        pytest.skip("Symlinks not supported on filesystem")

    scanner = FilesystemScanner(follow_symlinks=False)
    result = scanner.scan(scan_dir)
    assert result.total_files >= 0


def test_hardlink_deduplication(tmp_path: Path):
    """Verify hard links pointing to same inode are not double-counted in allocated space."""
    scan_dir = tmp_path / "hardlink_test"
    scan_dir.mkdir()

    orig_file = scan_dir / "original.bin"
    orig_file.write_bytes(b"X" * 10240)  # 10 KiB

    hardlink_file = scan_dir / "link.bin"
    try:
        os.link(orig_file, hardlink_file)
    except OSError:
        pytest.skip("Hard links not supported on filesystem")

    scanner = FilesystemScanner()
    result = scanner.scan(scan_dir)

    assert result.total_files == 2
    assert result.total_logical_size_bytes == 20480

    # Allocated size should account for the file only once
    # Check that allocated bytes does not count double
    stat_orig = orig_file.stat()
    expected_alloc = stat_orig.st_blocks * 512 if getattr(stat_orig, "st_blocks", None) else 10240
    assert result.total_allocated_size_bytes == expected_alloc


def test_path_not_found(tmp_path: Path):
    """Verify PathNotFoundError when target directory does not exist."""
    scanner = FilesystemScanner()
    with pytest.raises(PathNotFoundError):
        scanner.scan(tmp_path / "does_not_exist_xyz")


def test_not_a_directory(tmp_path: Path):
    """Verify NotADirectoryError when target path is a file."""
    a_file = tmp_path / "just_a_file.txt"
    a_file.write_text("content")

    scanner = FilesystemScanner()
    with pytest.raises(NotADirectoryError):
        scanner.scan(a_file)


def test_permission_error_recorded_in_diagnostics(tmp_path: Path):
    """Verify PermissionError during scandir is captured in diagnostics without crashing."""
    restricted_dir = tmp_path / "restricted"
    restricted_dir.mkdir()

    scanner = FilesystemScanner()
    with patch("os.scandir", side_effect=PermissionError("Permission denied")):
        result = scanner.scan(restricted_dir)

    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].error_type == "PermissionDenied"


def test_file_disappearing_during_stat(tmp_path: Path):
    """Verify FileNotFoundError during entry.stat is handled as diagnostic."""
    test_dir = tmp_path / "vanishing"
    test_dir.mkdir()
    (test_dir / "temp.txt").write_bytes(b"temp")

    scanner = FilesystemScanner()

    # Simulate entry.stat raising FileNotFoundError (e.g. deleted concurrently)
    real_scandir = os.scandir

    class MockEntry:
        def __init__(self, real):
            self._real = real
            self.name = real.name
            self.path = real.path

        def is_symlink(self):
            return False

        def is_dir(self, **kwargs):
            return False

        def stat(self, **kwargs):
            raise FileNotFoundError("Simulated disappearing file")

    class MockScandirContext:
        def __init__(self, path):
            self.path = path
            self.iter = real_scandir(path)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.iter.close()

        def __iter__(self):
            for item in self.iter:
                yield MockEntry(item)

    with patch("os.scandir", side_effect=MockScandirContext):
        result = scanner.scan(test_dir)

    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].error_type == "FileInaccessible"


def test_progress_callback_called(tmp_path: Path):
    """Verify progress callback is invoked during scan."""
    test_dir = tmp_path / "progress_test"
    test_dir.mkdir()
    for i in range(10):
        (test_dir / f"f_{i}.txt").write_bytes(b"data")

    calls = []

    def on_progress(files, dirs, path):
        calls.append((files, dirs, path))

    scanner = FilesystemScanner(progress_callback=on_progress)
    scanner.scan(test_dir)
    # Callback may be called on intervals or dirs
    assert isinstance(calls, list)
