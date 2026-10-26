"""Small shared helpers."""

from __future__ import annotations

import re


def safe_filename(value: str, fallback: str = "file") -> str:
    """Return a filesystem-safe filename stem."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or fallback
