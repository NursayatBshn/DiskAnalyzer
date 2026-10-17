"""Deterministic analysis engine and pattern classification."""

from disk_analyzer.analysis.analyzer import DiskAnalyzer
from disk_analyzer.analysis.categories import classify_file_into_category
from disk_analyzer.analysis.recommendations import generate_recommendations

__all__ = ["DiskAnalyzer", "classify_file_into_category", "generate_recommendations"]

