"""Heuristic pattern classification for Linux storage consumers."""

import re
from collections import defaultdict
from dataclasses import dataclass

from disk_analyzer.domain.models import FileInfo, StorageCategorySummary


@dataclass(frozen=True)
class CategoryRule:
    """Definition of a storage classification rule."""

    category_id: str
    name: str
    description: str
    path_regex: str
    extension_set: frozenset[str]
    confidence: str
    is_potential_cleanup: bool
    rationale: str


# Order matters: more specific categories precede broader ones
CATEGORY_RULES: list[CategoryRule] = [
    CategoryRule(
        category_id="trash",
        name="Trash & Recycled Items",
        description="Desktop trash bins and deleted files waiting for permanent disposal",
        path_regex=r"(^|/)\.(local/share/Trash|Trash)(/|$)",
        extension_set=frozenset(),
        confidence="high",
        is_potential_cleanup=True,
        rationale="Items moved to trash have already been marked for removal by user.",
    ),
    CategoryRule(
        category_id="browser_cache",
        name="Browser Data & Caches",
        description="Web browser cached assets, service workers, and offline caches",
        path_regex=r"(^|/)\.(cache/(google-chrome|chromium|mozilla/firefox|BraveSoftware)|mozilla/firefox/.*cache)(/|$)",
        extension_set=frozenset(),
        confidence="high",
        is_potential_cleanup=True,
        rationale="Browser caches speed up navigation but can be cleared safely via browser settings.",
    ),
    CategoryRule(
        category_id="package_manager_cache",
        name="Package Manager & Tool Caches",
        description="Downloaded packages, tool distributions, and registry artifacts (npm, pip, cargo, gradle)",
        path_regex=r"(^|/)(\.(gradle/caches|npm|pnpm-store|cargo/registry|cargo/git|rustup/toolchains|m2/repository)|var/cache/(pacman|apt))(/|$)",
        extension_set=frozenset(),
        confidence="high",
        is_potential_cleanup=True,
        rationale="Downloaded packages can be re-downloaded if needed; tools offer official cache prune commands.",
    ),
    CategoryRule(
        category_id="node_modules",
        name="Node.js Dependencies (node_modules)",
        description="Local npm/yarn/pnpm JavaScript module dependency trees",
        path_regex=r"(^|/)node_modules(/|$)",
        extension_set=frozenset(),
        confidence="high",
        is_potential_cleanup=True,
        rationale="Can be regenerated via 'npm install' or 'pnpm install' in active projects; stale projects can be cleaned.",
    ),
    CategoryRule(
        category_id="python_environments",
        name="Python Virtual Environments & Bytecode",
        description="Virtual environments, site-packages, and compiled Python __pycache__ files",
        path_regex=r"(^|/)(\.(venv|env)|venv|__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache)(/|$)",
        extension_set=frozenset({".pyc", ".pyo"}),
        confidence="high",
        is_potential_cleanup=True,
        rationale="Virtualenvs can be rebuilt from requirements.txt or poetry.lock; bytecode is automatically recreated.",
    ),
    CategoryRule(
        category_id="build_artifacts",
        name="Build Artifacts & Compiled Output",
        description="Compiler outputs, target binaries, distribution bundles, and intermediate objects",
        path_regex=r"(^|/)(target/(debug|release)|build|dist|\.next|\.nuxt|\.turbo|out)(/|$)",
        extension_set=frozenset({".o", ".obj", ".so", ".a", ".class"}),
        confidence="medium",
        is_potential_cleanup=True,
        rationale="Generated during compilation; easily recreated with build commands (cargo clean, make clean, etc.).",
    ),
    CategoryRule(
        category_id="general_cache",
        name="User Application Caches",
        description="General application caches residing in ~/.cache",
        path_regex=r"(^|/)\.cache(/|$)",
        extension_set=frozenset(),
        confidence="medium",
        is_potential_cleanup=True,
        rationale="Standard XDG cache directory storing regenerable auxiliary application data.",
    ),
    CategoryRule(
        category_id="games_launchers",
        name="Game Assets & Launchers",
        description="Installed game assets, Minecraft instances, Steam libraries, and wine prefixes",
        path_regex=r"(^|/)(\.minecraft|\.steam|SteamLibrary|\.local/share/lutris|\.var/app/com\.valvesoftware\.Steam)(/|$)",
        extension_set=frozenset(),
        confidence="high",
        is_potential_cleanup=False,
        rationale="Contains installed game files and configurations; verify within game launchers before deleting.",
    ),
    CategoryRule(
        category_id="logs",
        name="System & Application Logs",
        description="Log files, diagnostics, journal exports, and crash dumps",
        path_regex=r"(^|/)(var/log|\.local/share/xorg)(/|$)",
        extension_set=frozenset({".log", ".log.1", ".log.old", ".out", ".err", ".journal"}),
        confidence="high",
        is_potential_cleanup=True,
        rationale="Old logs can accumulate over time; log rotation or manual truncation can reclaim space.",
    ),
    CategoryRule(
        category_id="virtual_machines_disk_images",
        name="Disk Images & Virtual Machines",
        description="ISO installation media, VM virtual disks, and container images",
        path_regex=r"",
        extension_set=frozenset({".iso", ".img", ".vmdk", ".vdi", ".qcow2", ".raw"}),
        confidence="high",
        is_potential_cleanup=False,
        rationale="Often very large files. Manual review is recommended to delete obsolete installation ISOs.",
    ),
    CategoryRule(
        category_id="archives_backups",
        name="Archives & Backups",
        description="Compressed file archives, tarballs, and backup copies",
        path_regex=r"",
        extension_set=frozenset(
            {
                ".tar",
                ".tar.gz",
                ".tar.bz2",
                ".tar.xz",
                ".tar.zst",
                ".tgz",
                ".zip",
                ".7z",
                ".rar",
                ".bak",
                ".backup",
                ".old",
            }
        ),
        confidence="medium",
        is_potential_cleanup=False,
        rationale="May contain important backups or redundant copies; verify contents before modifying.",
    ),
    CategoryRule(
        category_id="media",
        name="Media Files (Video & Audio)",
        description="Multimedia video and audio recordings",
        path_regex=r"",
        extension_set=frozenset(
            {
                ".mp4",
                ".mkv",
                ".avi",
                ".mov",
                ".flv",
                ".webm",
                ".mp3",
                ".flac",
                ".wav",
                ".aac",
                ".ogg",
                ".m4a",
            }
        ),
        confidence="high",
        is_potential_cleanup=False,
        rationale="Personal media files; delete only if user intentionally wants to purge unwatched/unused media.",
    ),
    CategoryRule(
        category_id="temporary_files",
        name="Temporary Files",
        description="Ephemeral temporary files, editor swap files, and lock files",
        path_regex=r"(^|/)(tmp|var/tmp)(/|$)",
        extension_set=frozenset({".tmp", ".temp", ".swp", ".swo", ".bak~", "~"}),
        confidence="high",
        is_potential_cleanup=True,
        rationale="Temporary and swap files left behind by interrupted programs.",
    ),
]

_COMPILED_RULES = [
    (
        rule,
        re.compile(rule.path_regex, re.IGNORECASE) if rule.path_regex else None,
        rule.extension_set,
    )
    for rule in CATEGORY_RULES
]


def classify_file_into_category(file_info: FileInfo) -> CategoryRule | None:
    """Classify a single file into a storage category using deterministic heuristic rules.

    Args:
        file_info: File metadata.

    Returns:
        Matching CategoryRule or None if unclassified.
    """
    path_str = file_info.path
    ext = file_info.extension.lower()

    for rule, regex, ext_set in _COMPILED_RULES:
        # Check regex path match
        if regex and regex.search(path_str):
            return rule

        # Check extension match
        if ext_set and ext in ext_set:
            return rule

    return None


def aggregate_categories(
    files: list[FileInfo], total_logical_size: int
) -> list[StorageCategorySummary]:
    """Aggregate a list of files into structured storage category summaries.

    Args:
        files: List of all scanned files.
        total_logical_size: Total logical size of the scan for percentage computation.

    Returns:
        List of StorageCategorySummary sorted by total size descending.
    """
    category_totals: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
    category_samples: dict[str, list[str]] = defaultdict(list)
    rule_lookup: dict[str, CategoryRule] = {r.category_id: r for r in CATEGORY_RULES}

    unclassified_size = 0
    unclassified_count = 0
    unclassified_samples: list[str] = []

    for file in files:
        matched_rule = classify_file_into_category(file)
        if matched_rule:
            cat_id = matched_rule.category_id
            category_totals[cat_id] += file.size_bytes
            category_counts[cat_id] += 1
            if len(category_samples[cat_id]) < 3:
                category_samples[cat_id].append(file.path)
        else:
            unclassified_size += file.size_bytes
            unclassified_count += 1
            if len(unclassified_samples) < 3:
                unclassified_samples.append(file.path)

    summaries: list[StorageCategorySummary] = []

    for cat_id, total_size in category_totals.items():
        rule = rule_lookup[cat_id]
        pct = (total_size / total_logical_size * 100.0) if total_logical_size > 0 else 0.0
        summaries.append(
            StorageCategorySummary(
                category_id=rule.category_id,
                name=rule.name,
                description=rule.description,
                total_size_bytes=total_size,
                file_count=category_counts[cat_id],
                percentage_of_total=round(pct, 2),
                sample_paths=category_samples[cat_id],
                confidence=rule.confidence,
                is_potential_cleanup=rule.is_potential_cleanup,
                rationale=rule.rationale,
            )
        )

    if unclassified_count > 0:
        pct = (unclassified_size / total_logical_size * 100.0) if total_logical_size > 0 else 0.0
        summaries.append(
            StorageCategorySummary(
                category_id="other",
                name="Other / Unclassified",
                description="Files not matching specific cache, dependency, or media heuristics",
                total_size_bytes=unclassified_size,
                file_count=unclassified_count,
                percentage_of_total=round(pct, 2),
                sample_paths=unclassified_samples,
                confidence="high",
                is_potential_cleanup=False,
                rationale="Standard user and application files. Do not modify without inspection.",
            )
        )

    # Sort categories by size descending
    summaries.sort(key=lambda c: c.total_size_bytes, reverse=True)
    return summaries
