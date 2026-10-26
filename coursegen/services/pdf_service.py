"""Upload, outline parsing, and text extraction for PDF books."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List

import fitz

from coursegen.config import Settings, get_settings
from coursegen.errors import ValidationError
from coursegen.models import Chapter
from coursegen.services.chapters import filter_chapters, normalize_chapters
from coursegen.utils import safe_filename

logger = logging.getLogger(__name__)


class PdfService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def save_upload(self, uploaded_file: object) -> Path:
        self._settings.pdf_dir.mkdir(parents=True, exist_ok=True)
        original_name = Path(str(getattr(uploaded_file, "name", "book.pdf"))).name
        stem = safe_filename(Path(original_name).stem, "book")
        destination = self._settings.pdf_dir / f"{stem}.pdf"
        content = getattr(uploaded_file, "getbuffer", None)
        data = content() if callable(content) else uploaded_file.getvalue()
        destination.write_bytes(bytes(data))
        logger.info("Saved uploaded book to %s", destination)
        return destination

    def course_name_for(self, uploaded_file: object) -> str:
        original_name = Path(str(getattr(uploaded_file, "name", "course.pdf"))).name
        return Path(original_name).stem

    def extract_chapters(self, pdf_path: Path) -> List[Chapter]:
        try:
            with fitz.open(str(pdf_path)) as document:
                toc = document.get_toc()
                page_count = document.page_count
        except Exception as exc:
            logger.error("Could not read the book outline: %s", exc)
            raise ValidationError("The PDF could not be read. Make sure it is a valid PDF file.") from exc

        chapters: List[Chapter] = []
        for index, entry in enumerate(toc):
            level, raw_title, start_page = entry
            if level != 1:
                continue
            title = re.sub(r"\d+$", "", raw_title).strip()
            if not title:
                continue
            end_page = page_count - 1
            for next_level, _, next_start_page in toc[index + 1 :]:
                if next_level == 1:
                    end_page = next_start_page - 1
                    break
            chapters.append(Chapter(title=title, start_page=start_page, end_page=end_page))

        return filter_chapters(normalize_chapters(chapters))

    def extract_text(
        self,
        pdf_path: Path,
        chapters: Iterable[Chapter],
        selected_titles: Iterable[str],
    ) -> Dict[str, str]:
        selected = set(selected_titles)
        chosen = [chapter for chapter in chapters if chapter.title in selected]
        if not chosen:
            raise ValidationError("Select at least one chapter to generate the course.")

        extracted: Dict[str, str] = {}
        with fitz.open(str(pdf_path)) as document:
            for chapter in chosen:
                start = max(chapter.start_page - 1, 0)
                end = min(chapter.end_page, document.page_count)
                text = "\n".join(document[page].get_text() for page in range(start, end))
                if text.strip():
                    extracted[chapter.title] = text

        if not extracted:
            raise ValidationError("No readable text was found in the selected chapters.")
        return extracted


@lru_cache(maxsize=1)
def get_pdf_service() -> PdfService:
    return PdfService()
