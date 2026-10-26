"""Font resolution shared by the presentation and video builders."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from PIL import ImageFont

from coursegen.config import get_settings

logger = logging.getLogger(__name__)

FONT_FILES = {
    "Arial": "arial.ttf",
    "Calibri": "calibri.ttf",
    "Times New Roman": "times.ttf",
    "Verdana": "verdana.ttf",
    "Courier New": "cour.ttf",
    "Georgia": "georgia.ttf",
    "Tahoma": "tahoma.ttf",
    "Comic Sans MS": "comic.ttf",
    "Impact": "impact.ttf",
    "Trebuchet MS": "trebuc.ttf",
}


def resolve_font(font_name: str) -> Optional[Path]:
    settings = get_settings()
    filename = FONT_FILES.get(font_name, FONT_FILES["Arial"])
    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = [
        settings.fonts_dir / filename,
        settings.fonts_dir / filename.capitalize(),
        windows_fonts / filename,
        windows_fonts / filename.capitalize(),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if settings.fonts_dir.is_dir():
        for entry in settings.fonts_dir.iterdir():
            if entry.is_file() and entry.name.lower() == filename.lower():
                return entry
    logger.warning("Font %s not found; using Pillow's default font.", font_name)
    return None


def load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = resolve_font(font_name)
    if path is not None:
        try:
            return ImageFont.truetype(str(path), max(8, size))
        except OSError as exc:
            logger.warning("Could not load font %s: %s", path, exc)
    return ImageFont.load_default()
