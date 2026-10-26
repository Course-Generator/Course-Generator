"""Structural interfaces for infrastructure adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FileStorage(Protocol):
    def upload(self, local_path: Path, remote_path: str) -> str:
        ...


class PresentationUploader(Protocol):
    def upload(self, file_path: Path) -> str:
        ...
