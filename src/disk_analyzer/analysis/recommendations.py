"""Deterministic recommendation engine based on observed storage evidence."""

from disk_analyzer.domain.models import (
    RecommendationItem,
    StorageCategorySummary,
)
from disk_analyzer.utils.formatting import format_bytes


def generate_recommendations(
    categories: list[StorageCategorySummary],
    total_scanned_bytes: int,
) -> list[RecommendationItem]:
    """Generate evidence-based cleanup and maintenance recommendations without AI.

    All recommendations include confidence ratings, explicit risks, and non-destructive
    next steps for user review.

    Args:
        categories: Aggregated storage category summaries.
        total_scanned_bytes: Total logical bytes scanned.

    Returns:
        List of prioritized RecommendationItem objects.
    """
    recs: list[RecommendationItem] = []
    cat_by_id = {c.category_id: c for c in categories}

    # 1. Trash / Recycled Items
    trash_cat = cat_by_id.get("trash")
    if trash_cat and trash_cat.total_size_bytes > 0:
        size_str = format_bytes(trash_cat.total_size_bytes)
        recs.append(
            RecommendationItem(
                id="rec-trash-cleanup",
                title=f"Empty desktop trash ({size_str})",
                category="Trash & Recycled Items",
                priority="high",
                description=(
                    f"Found {size_str} across {trash_cat.file_count} files in trash directories. "
                    "These items were already marked for deletion by the user."
                ),
                estimated_reclaimable_bytes=trash_cat.total_size_bytes,
                confidence="high",
                target_paths=trash_cat.sample_paths,
                risks_and_caveats=(
                    "Permanently deletes files in trash. Recovery will require filesystem undelete "
                    "tools or backups. Ensure no accidentally deleted documents reside in Trash."
                ),
                suggested_actions=[
                    "Inspect trash folder contents via your file manager.",
                    "Empty trash permanently using desktop environment controls or review ~/.local/share/Trash.",
                ],
            )
        )

    # 2. Package Manager Caches
    pkg_cat = cat_by_id.get("package_manager_cache")
    if pkg_cat and pkg_cat.total_size_bytes > 100 * 1024 * 1024:  # > 100 MiB
        size_str = format_bytes(pkg_cat.total_size_bytes)
        recs.append(
            RecommendationItem(
                id="rec-package-caches",
                title=f"Prune package manager caches ({size_str})",
                category="Package Manager & Tool Caches",
                priority="medium",
                description=(
                    f"Package manager caches (npm, gradle, cargo, pacman) consume {size_str}. "
                    "These directories store previously downloaded toolchains, distributions, and dependencies."
                ),
                estimated_reclaimable_bytes=int(pkg_cat.total_size_bytes * 0.75),
                confidence="medium",
                target_paths=pkg_cat.sample_paths,
                risks_and_caveats=(
                    "Subsequent builds or package installations will need to re-download artifacts "
                    "from remote registries, temporarily increasing network bandwidth usage."
                ),
                suggested_actions=[
                    "Run package-specific maintenance commands: e.g. 'npm cache clean --force', 'cargo cache -a', or 'pnpm store prune'.",
                    "For Gradle on Linux, verify '~/.gradle/caches' and old wrapper distributions in '~/.gradle/wrapper/dists'.",
                ],
            )
        )

    # 3. Node Modules
    node_cat = cat_by_id.get("node_modules")
    if node_cat and node_cat.total_size_bytes > 200 * 1024 * 1024:  # > 200 MiB
        size_str = format_bytes(node_cat.total_size_bytes)
        recs.append(
            RecommendationItem(
                id="rec-node-modules",
                title=f"Review inactive node_modules directories ({size_str})",
                category="Node.js Dependencies",
                priority="medium",
                description=(
                    f"Found {node_cat.file_count} files in 'node_modules' directories occupying {size_str}. "
                    "Completed, paused, or duplicate JavaScript/TypeScript projects often leave large node_modules trees."
                ),
                estimated_reclaimable_bytes=None,  # Not established without knowing which projects are inactive
                confidence="medium",
                target_paths=node_cat.sample_paths,
                risks_and_caveats=(
                    "Deleting active node_modules breaks running Node applications and tests until "
                    "'npm install' or 'pnpm install' is run again. Do NOT delete in currently active projects."
                ),
                suggested_actions=[
                    "Identify inactive or archived JavaScript repositories.",
                    "Safely remove 'node_modules' only in stale repositories, knowing they can be reinstalled anytime from package-lock.json.",
                ],
            )
        )

    # 4. Build Artifacts
    build_cat = cat_by_id.get("build_artifacts")
    if build_cat and build_cat.total_size_bytes > 150 * 1024 * 1024:  # > 150 MiB
        size_str = format_bytes(build_cat.total_size_bytes)
        recs.append(
            RecommendationItem(
                id="rec-build-artifacts",
                title=f"Clean compilation and build output directories ({size_str})",
                category="Build Artifacts & Compiled Output",
                priority="medium",
                description=(
                    f"Compiler outputs, target binaries, and dist bundles consume {size_str}. "
                    "Build directories frequently accumulate incremental build artifacts."
                ),
                estimated_reclaimable_bytes=int(build_cat.total_size_bytes * 0.9),
                confidence="high",
                target_paths=build_cat.sample_paths,
                risks_and_caveats=(
                    "Next build will require a clean recompilation, which may take longer than incremental builds."
                ),
                suggested_actions=[
                    "Run clean targets in your build systems: 'cargo clean' in Rust, 'make clean' in C/C++, or remove 'dist/' and '.next/' in web apps.",
                ],
            )
        )

    # 5. General User Caches
    cache_cat = cat_by_id.get("general_cache")
    if cache_cat and cache_cat.total_size_bytes > 500 * 1024 * 1024:  # > 500 MiB
        size_str = format_bytes(cache_cat.total_size_bytes)
        recs.append(
            RecommendationItem(
                id="rec-general-cache",
                title=f"Review user application caches in ~/.cache ({size_str})",
                category="User Application Caches",
                priority="low",
                description=(
                    f"General user caches under ~/.cache consume {size_str}. "
                    "Applications place temporary caches here according to the XDG Base Directory specification."
                ),
                estimated_reclaimable_bytes=None,  # Variable by application
                confidence="medium",
                target_paths=cache_cat.sample_paths,
                risks_and_caveats=(
                    "Some applications store authentication sessions or thumbnails in subdirectories of ~/.cache. "
                    "Do NOT delete all of ~/.cache indiscriminately; inspect subdirectories individually."
                ),
                suggested_actions=[
                    "Examine largest subdirectories inside ~/.cache.",
                    "Purge obsolete cache directories for uninstalled or rarely used applications.",
                ],
            )
        )

    # 6. Disk Images & Virtual Machines
    vm_cat = cat_by_id.get("virtual_machines_disk_images")
    if vm_cat and vm_cat.total_size_bytes > 1024 * 1024 * 1024:  # > 1 GiB
        size_str = format_bytes(vm_cat.total_size_bytes)
        recs.append(
            RecommendationItem(
                id="rec-disk-images",
                title=f"Audit large disk images and installation media ({size_str})",
                category="Disk Images & Virtual Machines",
                priority="low",
                description=(
                    f"Found {size_str} in ISOs, VM virtual disks, or container images across {vm_cat.file_count} files. "
                    "These files are high-impact individual storage consumers."
                ),
                estimated_reclaimable_bytes=None,
                confidence="high",
                target_paths=vm_cat.sample_paths,
                risks_and_caveats=(
                    "Never delete virtual disks belonging to active VMs or data containers. "
                    "Ensure ISO images are no longer required for recovery or installation."
                ),
                suggested_actions=[
                    "Check if downloaded Linux distribution ISOs are outdated and safe to delete.",
                    "Compact sparse virtual machine disks or remove decommissioned VM images.",
                ],
            )
        )

    # 7. System / App Logs
    logs_cat = cat_by_id.get("logs")
    if logs_cat and logs_cat.total_size_bytes > 100 * 1024 * 1024:  # > 100 MiB
        size_str = format_bytes(logs_cat.total_size_bytes)
        recs.append(
            RecommendationItem(
                id="rec-system-logs",
                title=f"Vacuum or rotate application logs ({size_str})",
                category="System & Application Logs",
                priority="low",
                description=(
                    f"System and application logs consume {size_str}. "
                    "Unrotated or verbose log files can accumulate steadily."
                ),
                estimated_reclaimable_bytes=int(logs_cat.total_size_bytes * 0.8),
                confidence="medium",
                target_paths=logs_cat.sample_paths,
                risks_and_caveats=(
                    "Clearing logs removes historical debugging information and error traces."
                ),
                suggested_actions=[
                    "On systemd systems, check journal disk usage with 'journalctl --disk-usage'.",
                    "Retain only recent logs if desired: e.g. 'sudo journalctl --vacuum-size=200M'.",
                ],
            )
        )

    # Sort recommendations by priority (high -> medium -> low)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order.get(r.priority, 3))
    return recs
