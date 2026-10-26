"""Parse generated slide text and expand each bullet into an explanation."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Iterable, List, Tuple

import nltk
from langchain.schema import HumanMessage, SystemMessage
from nltk.tokenize import word_tokenize

from coursegen.ai.prompts import EXPLANATION_PROMPT
from coursegen.infrastructure.llm import get_llm
from coursegen.models import LectureMap, SlideMap

logger = logging.getLogger(__name__)

_SUPPRESSED_TITLE_PREFIXES = (
    "conclusion",
    "q&a",
    "references",
    "thank",
    "questions",
    "question",
    "resources",
    "resource",
    "discuss",
)


def is_non_content_title(title: str) -> bool:
    cleaned = title.strip().lower().lstrip(":")
    return not cleaned or cleaned.startswith(_SUPPRESSED_TITLE_PREFIXES)


@lru_cache(maxsize=1)
def _ensure_tokenizer() -> bool:
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)
    return True


class SlideExplainer:
    def extract_slides(self, slide_texts: Iterable[str]) -> SlideMap:
        slides: SlideMap = {}
        for text in slide_texts:
            for block in text.split("Slide"):
                if not block.strip():
                    continue
                title, content = self._partition(block)
                if not title or is_non_content_title(title) or not content:
                    continue
                slides[title] = content
        return slides

    def explain_points(self, slides: SlideMap) -> SlideMap:
        explained: SlideMap = {}
        for title, points in slides.items():
            if "references" in title.lower():
                continue
            explained[title] = [self._explain_point(point) for point in points if point.strip()]
        return explained

    def clean_explanations(self, explanations: LectureMap) -> LectureMap:
        cleaned: LectureMap = {}
        for lecture, slides in explanations.items():
            cleaned[lecture] = {
                title: [self._strip_filler(point) for point in points if point.strip()]
                for title, points in slides.items()
            }
        return cleaned

    def _explain_point(self, point: str) -> str:
        response = get_llm()(
            [
                SystemMessage(content=EXPLANATION_PROMPT),
                HumanMessage(content=point),
            ]
        )
        return str(getattr(response, "content", "") or "").strip()

    @staticmethod
    def _partition(block: str) -> Tuple[str, List[str]]:
        title = ""
        if "Title:" in block:
            after_title = block.split("Title:", 1)[1]
            title = after_title.splitlines()[0].strip() if after_title else ""
        else:
            match = re.search(r"\d+:(.*?)\n", block)
            if match:
                title = match.group(1).strip()
        title = title.lstrip(":").strip()

        content = []
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or not stripped.startswith("-"):
                continue
            if stripped.startswith(("(Note", "Note")):
                continue
            if "conclusion" in stripped.lower() or "title" in stripped.lower():
                continue
            content.append(stripped)
        return title, content

    @staticmethod
    def _strip_filler(point: str) -> str:
        _ensure_tokenizer()
        cleaned = re.sub(r"conclusion", "", point, flags=re.IGNORECASE).strip()
        if not cleaned:
            return ""
        try:
            tokens = word_tokenize(cleaned)
        except LookupError:
            tokens = cleaned.split()
        if tokens and tokens[0].lower() == "today":
            cleaned = re.sub(r"^\s*today[,\s]+", "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned
