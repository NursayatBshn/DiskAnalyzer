"""High-performance recursive filesystem scanner with error handling and deduplication."""

import fnmatch
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from disk_analyzer.domain.models import (
    DirectoryStats,
    FileInfo,
    ScanDiagnostic,
    ScanResult,
)
from disk_analyzer.exceptions import (
    NotADirectoryError,
    PathNotFoundError,
)

SYSTEM_VIRTUAL_FS = ("/proc", "/sys", "/dev", "/run")


def matches_pattern(path_str: str, name: str, pattern: str) -> bool:
    """Check if a path or filename matches an exclusion pattern.

    Supports glob patterns such as `**/.git/**`, `*.tmp`, `node_modules`.

    Args:
        path_str: Full path string.
        name: Basename of entry.
        pattern: Pattern string.

    Returns:
        True if matched, False otherwise.
    """
    clean_pat = pattern.strip()
    if not clean_pat:
        return False

    # Direct filename match
    if fnmatch.fnmatch(name, clean_pat):
        return True

    # Full path fnmatch
    if fnmatch.fnmatch(path_str, clean_pat):
        return True

    # Handle **/name/** style patterns
    normalized_pat = clean_pat.strip("*").strip("/")
    if normalized_pat and (
        f"/{normalized_pat}/" in path_str
        or path_str.endswith(f"/{normalized_pat}")
        or name == normalized_pat
    ):
        return True

    # Pathlib match fallback
    try:
        p = Path(path_str)
        if p.match(clean_pat):
            return True
    except ValueError:
        pass

    return False


class FilesystemScanner:
    """Recursively scans directories to collect metadata, sizes, and diagnostics."""

    def __init__(
        self,
        top_items: int = 15,
        max_depth: int | None = None,
        follow_symlinks: bool = False,
        exclude_patterns: list[str] | None = None,
        exclude_system_virtual_fs: bool = True,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> None:
        """Initialize the scanner with configurable limits and exclusions.

        Args:
            top_items: Number of largest files and directories to retain in results.
            max_depth: Maximum directory recursion depth (None for unlimited).
            follow_symlinks: Whether to follow symbolic links (default False).
            exclude_patterns: List of glob patterns to exclude.
            exclude_system_virtual_fs: Automatically exclude /proc, /sys, /dev, /run.
            progress_callback: Optional callback(files_count, dirs_count, current_path).
        """
        self.top_items = max(1, top_items)
        self.max_depth = max_depth
        self.follow_symlinks = follow_symlinks
        self.exclude_patterns = list(exclude_patterns or [])
        self.exclude_system_virtual_fs = exclude_system_virtual_fs
        self.progress_callback = progress_callback

        # State tracking
        self._seen_inodes: set[tuple[int, int]] = set()
        self._seen_realpaths: set[str] = set()
        self._diagnostics: list[ScanDiagnostic] = []
        self._all_files: list[FileInfo] = []
        self._dir_stats_list: list[DirectoryStats] = []
        self._total_files = 0
        self._total_dirs = 0
        self._total_logical_size = 0
        self._total_allocated_size = 0

    def scan(self, target_path: Path | str) -> ScanResult:
        """Execute a recursive filesystem scan on target_path.

        Args:
            target_path: Root directory path to scan.

        Returns:
            ScanResult containing metrics, top files/dirs, and diagnostics.

        Raises:
            PathNotFoundError: If target_path does not exist.
            NotADirectoryError: If target_path is not a directory.
        """
        path_obj = Path(target_path).expanduser().resolve()

        if not path_obj.exists():
            raise PathNotFoundError(f"Target path does not exist: {path_obj}")

        if not path_obj.is_dir():
            raise NotADirectoryError(f"Target path is not a directory: {path_obj}")

        # Reset state for fresh scan
        self._seen_inodes.clear()
        self._seen_realpaths.clear()
        self._diagnostics.clear()
        self._all_files.clear()
        self._dir_stats_list.clear()
        self._total_files = 0
        self._total_dirs = 0
        self._total_logical_size = 0
        self._total_allocated_size = 0

        start_time = time.monotonic()
        root_str = str(path_obj)

        if self.follow_symlinks:
            self._seen_realpaths.add(os.path.realpath(root_str))

        # Perform recursive traversal starting at depth 0
        self._scan_directory(root_str, depth=0)

        duration = time.monotonic() - start_time

        # Sort largest files and directories
        sorted_files = sorted(self._all_files, key=lambda f: f.size_bytes, reverse=True)[
            : self.top_items
        ]
        sorted_dirs = sorted(
            self._dir_stats_list, key=lambda d: d.logical_size_bytes, reverse=True
        )[: self.top_items]

        return ScanResult(
            root_path=root_str,
            scanned_at=datetime.now(UTC),
            duration_seconds=duration,
            total_files=self._total_files,
            total_directories=self._total_dirs,
            total_logical_size_bytes=self._total_logical_size,
            total_allocated_size_bytes=self._total_allocated_size,
            largest_files=sorted_files,
            largest_directories=sorted_dirs,
            diagnostics=self._diagnostics,
            excluded_patterns=self.exclude_patterns,
        )

    def _is_excluded(self, path_str: str, name: str) -> bool:
        """Check if path should be excluded based on virtual FS or user patterns."""
        if self.exclude_system_virtual_fs:
            for vfs in SYSTEM_VIRTUAL_FS:
                if path_str == vfs or path_str.startswith(f"{vfs}/"):
                    return True

        for pat in self.exclude_patterns:
            if matches_pattern(path_str, name, pat):
                return True

        return False

    def _scan_directory(self, dir_path: str, depth: int) -> tuple[int, int, int, int]:
        """Traverse a single directory recursively.

        Returns:
            Tuple of (cumulative_logical_bytes, cumulative_allocated_bytes,
                      subtree_file_count, subtree_dir_count).
        """
        self._total_dirs += 1
        dir_name = os.path.basename(dir_path) or dir_path

        dir_logical_bytes = 0
        dir_allocated_bytes = 0
        dir_file_count = 0
        dir_dir_count = 0

        if self.progress_callback and (self._total_files % 100 == 0 or self._total_dirs % 20 == 0):
            self.progress_callback(self._total_files, self._total_dirs, dir_path)

        try:
            scandir_iter = os.scandir(dir_path)
        except PermissionError as exc:
            self._diagnostics.append(
                ScanDiagnostic(
                    path=dir_path,
                    error_type="PermissionDenied",
                    message=f"Access denied reading directory: {exc.strerror or exc}",
                )
            )
            return 0, 0, 0, 0
        except FileNotFoundError:
            # Directory vanished during scan
            return 0, 0, 0, 0
        except OSError as exc:
            self._diagnostics.append(
                ScanDiagnostic(
                    path=dir_path,
                    error_type="OSError",
                    message=f"Operating system error: {exc.strerror or exc}",
                )
            )
            return 0, 0, 0, 0

        subdirs: list[str] = []

        with scandir_iter:
            for entry in scandir_iter:
                try:
                    entry_name = entry.name
                    entry_path = entry.path

                    # Check exclusion
                    if self._is_excluded(entry_path, entry_name):
                        continue

                    # Check if symlink
                    is_symlink = entry.is_symlink()
                    if is_symlink and not self.follow_symlinks:
                        # Non-following symlinks: do not follow, treat as 0 or small symlink size
                        try:
                            l_stat = entry.stat(follow_symlinks=False)
                            dir_logical_bytes += l_stat.st_size
                            dir_file_count += 1
                            self._total_files += 1
                        except (OSError, FileNotFoundError):
                            pass
                        continue

                    # Check directory vs file
                    is_dir = entry.is_dir(follow_symlinks=self.follow_symlinks)

                    if is_dir:
                        # Prevent symlink loops if follow_symlinks is enabled
                        if self.follow_symlinks:
                            real_p = os.path.realpath(entry_path)
                            if real_p in self._seen_realpaths:
                                self._diagnostics.append(
                                    ScanDiagnostic(
                                        path=entry_path,
                                        error_type="SymlinkLoopDetected",
                                        message=f"Recursive symlink cycle avoided: {real_p}",
                                    )
                                )
                                continue
                            self._seen_realpaths.add(real_p)

                        subdirs.append(entry_path)

                    else:
                        # Process file
                        try:
                            f_stat = entry.stat(follow_symlinks=self.follow_symlinks)
                        except (FileNotFoundError, OSError) as exc:
                            # File deleted, broken link, or inaccessible
                            self._diagnostics.append(
                                ScanDiagnostic(
                                    path=entry_path,
                                    error_type="FileInaccessible",
                                    message=f"Cannot stat file: {exc}",
                                )
                            )
                            continue

                        logical_size = f_stat.st_size

                        # Calculate allocated size on Linux (st_blocks * 512)
                        st_blocks = getattr(f_stat, "st_blocks", None)
                        if st_blocks is not None and st_blocks >= 0:
                            allocated_size = st_blocks * 512
                        else:
                            allocated_size = logical_size

                        # Hardlink deduplication
                        st_dev = f_stat.st_dev
                        st_ino = f_stat.st_ino
                        st_nlink = f_stat.st_nlink

                        is_duplicate_hardlink = False
                        if st_nlink > 1:
                            inode_key = (st_dev, st_ino)
                            if inode_key in self._seen_inodes:
                                is_duplicate_hardlink = True
                            else:
                                self._seen_inodes.add(inode_key)

                        # Determine file extension (e.g. .tar.gz or .txt)
                        ext = self._extract_extension(entry_name)

                        # Mod time
                        try:
                            mtime = datetime.fromtimestamp(f_stat.st_mtime, UTC)
                        except (ValueError, OSError):
                            mtime = None

                        file_info = FileInfo(
                            path=entry_path,
                            name=entry_name,
                            size_bytes=logical_size,
                            allocated_bytes=allocated_size,
                            extension=ext,
                            is_symlink=is_symlink,
                            modified_at=mtime,
                        )

                        self._all_files.append(file_info)
                        self._total_files += 1
                        self._total_logical_size += logical_size
                        dir_logical_bytes += logical_size
                        dir_file_count += 1

                        if not is_duplicate_hardlink:
                            self._total_allocated_size += allocated_size
                            dir_allocated_bytes += allocated_size

                except PermissionError as exc:
                    self._diagnostics.append(
                        ScanDiagnostic(
                            path=getattr(entry, "path", dir_path),
                            error_type="PermissionDenied",
                            message=f"Access denied: {exc}",
                        )
                    )
                except (FileNotFoundError, OSError) as exc:
                    self._diagnostics.append(
                        ScanDiagnostic(
                            path=getattr(entry, "path", dir_path),
                            error_type="EntryError",
                            message=f"Error inspecting entry: {exc}",
                        )
                    )

        # Recurse into subdirectories if depth limit allows
        can_descend = self.max_depth is None or (depth < self.max_depth)
        for sdir in subdirs:
            if can_descend:
                sub_log, sub_alloc, sub_files, sub_dirs = self._scan_directory(sdir, depth + 1)
                dir_logical_bytes += sub_log
                dir_allocated_bytes += sub_alloc
                dir_file_count += sub_files
                dir_dir_count += 1 + sub_dirs
            else:
                dir_dir_count += 1

        # Record this directory's statistics
        stats = DirectoryStats(
            path=dir_path,
            name=dir_name,
            logical_size_bytes=dir_logical_bytes,
            allocated_size_bytes=dir_allocated_bytes,
            file_count=dir_file_count,
            dir_count=dir_dir_count,
            depth=depth,
        )
        self._dir_stats_list.append(stats)

        return dir_logical_bytes, dir_allocated_bytes, dir_file_count, dir_dir_count

    @staticmethod
    def _extract_extension(filename: str) -> str:
        """Extract multi-part extension (e.g., .tar.gz) or single extension in lower-case."""
        lower = filename.lower()
        if lower.endswith(".tar.gz"):
            return ".tar.gz"
        if lower.endswith(".tar.bz2"):
            return ".tar.bz2"
        if lower.endswith(".tar.xz"):
            return ".tar.xz"
        if lower.endswith(".tar.zst"):
            return ".tar.zst"

        ext = Path(filename).suffix.lower()
        return ext if ext else "(no extension)"
