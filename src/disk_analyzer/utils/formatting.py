"""Utility functions for byte formatting, duration formatting, and privacy redaction."""

import re
from pathlib import Path


def format_bytes(num_bytes: int | float) -> str:
    """Format a byte count into a human-readable string with binary units (KiB, MiB, GiB, etc.).

    Args:
        num_bytes: Number of bytes to format.

    Returns:
        Formatted string, e.g. '512 B', '1.24 MiB', '45.10 GiB'.
    """
    if num_bytes < 0:
        return f"-{format_bytes(-num_bytes)}"

    if num_bytes < 1024:
        return f"{int(num_bytes)} B"

    units = ["KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]
    val = float(num_bytes)
    for unit in units:
        val /= 1024.0
        if val < 1024.0 or unit == units[-1]:
            return f"{val:.2f} {unit}"

    return f"{val:.2f} EiB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds into a friendly human-readable string.

    Args:
        seconds: Elapsed time in seconds.

    Returns:
        Formatted string, e.g. '145 ms', '2.34s', '1m 23s'.
    """
    if seconds < 0:
        return "0 ms"
    if seconds < 1.0:
        ms = int(seconds * 1000)
        return f"{ms} ms"
    if seconds < 60.0:
        return f"{seconds:.2f}s"

    mins = int(seconds // 60)
    remaining_secs = seconds % 60
    return f"{mins}m {remaining_secs:.1f}s"


def redact_path(path_str: str, redact: bool = True) -> str:
    """Redact user-specific home directory prefixes from filesystem paths for privacy.

    Replaces current user's home directory with `~` and generic `/home/<username>` paths
    with `~/` or `~<user>/`.

    Args:
        path_str: Original path string.
        redact: Whether redaction is enabled.

    Returns:
        Redacted or original path string.
    """
    if not redact or not path_str:
        return path_str

    try:
        home_str = str(Path.home().resolve())
        if path_str.startswith(home_str):
            rel = path_str[len(home_str) :]
            if rel == "" or rel == "/":
                return "~"
            if rel.startswith("/"):
                return f"~{rel}"
            return f"~/{rel}"
    except (RuntimeError, OSError):
        pass

    # Generic Linux home redaction: /home/<user>/... -> ~/...
    home_match = re.match(r"^/home/[^/]+(/.*)?$", path_str)
    if home_match:
        suffix = home_match.group(1) or ""
        return f"~{suffix}" if suffix else "~"

    return path_str


def mask_secret(secret: str | None) -> str:
    """Mask a sensitive secret or API key for safe terminal display.

    Args:
        secret: Raw secret string.

    Returns:
        Masked representation, e.g. 'AIza...3f1a' or '(not set)'.
    """
    if not secret:
        return "(not set)"
    clean = secret.strip()
    if len(clean) <= 8:
        return "********"
    return f"{clean[:4]}...{clean[-4:]}"
