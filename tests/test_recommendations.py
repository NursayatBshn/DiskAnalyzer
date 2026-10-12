"""Unit tests for deterministic recommendation engine."""

from disk_analyzer.analysis.recommendations import generate_recommendations
from disk_analyzer.domain.models import StorageCategorySummary


def test_trash_recommendation():
    """Verify trash generates high-priority recommendation with clear risks."""
    categories = [
        StorageCategorySummary(
            category_id="trash",
            name="Trash & Recycled Items",
            description="Deleted items",
            total_size_bytes=500_000_000,
            file_count=12,
            percentage_of_total=50.0,
            sample_paths=["/home/user/.local/share/Trash/files/file.zip"],
            confidence="high",
            is_potential_cleanup=True,
            rationale="Deleted files",
        )
    ]
    recs = generate_recommendations(categories, total_scanned_bytes=1_000_000_000)

    assert len(recs) == 1
    trash_rec = recs[0]
    assert trash_rec.priority == "high"
    assert trash_rec.confidence == "high"
    assert trash_rec.estimated_reclaimable_bytes == 500_000_000
    assert "Permanently deletes" in trash_rec.risks_and_caveats
    assert len(trash_rec.suggested_actions) >= 1


def test_package_cache_recommendation():
    """Verify package manager caches trigger conservative estimate and tool suggestions."""
    categories = [
        StorageCategorySummary(
            category_id="package_manager_cache",
            name="Package Manager & Tool Caches",
            description="Package cache",
            total_size_bytes=200 * 1024 * 1024,  # 200 MiB
            file_count=50,
            percentage_of_total=20.0,
            sample_paths=["/home/user/.npm/cache"],
            confidence="medium",
            is_potential_cleanup=True,
            rationale="Downloaded packages",
        )
    ]
    recs = generate_recommendations(categories, total_scanned_bytes=1024 * 1024 * 1024)

    assert len(recs) == 1
    pkg_rec = recs[0]
    assert pkg_rec.priority == "medium"
    assert pkg_rec.estimated_reclaimable_bytes is not None
    assert pkg_rec.estimated_reclaimable_bytes < 200 * 1024 * 1024
    assert any("npm cache clean" in act for act in pkg_rec.suggested_actions)


def test_node_modules_recommendation_does_not_claim_guaranteed_savings():
    """Verify node_modules recommendation leaves reclaimable bytes unestablished."""
    categories = [
        StorageCategorySummary(
            category_id="node_modules",
            name="Node.js Dependencies",
            description="Dependencies",
            total_size_bytes=300 * 1024 * 1024,
            file_count=4000,
            percentage_of_total=30.0,
            sample_paths=["/home/user/project/node_modules"],
            confidence="medium",
            is_potential_cleanup=True,
            rationale="Dependencies",
        )
    ]
    recs = generate_recommendations(categories, total_scanned_bytes=1024 * 1024 * 1024)

    assert len(recs) == 1
    node_rec = recs[0]
    assert node_rec.estimated_reclaimable_bytes is None
    assert "Do NOT delete in currently active projects" in node_rec.risks_and_caveats


def test_empty_categories_produce_no_recommendations():
    """Verify empty category list yields empty recommendations list."""
    recs = generate_recommendations([], total_scanned_bytes=0)
    assert recs == []
