"""Generate raw slide text from chapters or lecture points."""

from __future__ import annotations

import logging
from typing import Dict, List

from langchain.schema import HumanMessage, SystemMessage

from coursegen.ai.prompts import TOPIC_SLIDE_PROMPT, chapter_slide_prompt
from coursegen.errors import GenerationError
from coursegen.infrastructure.llm import get_llm

logger = logging.getLogger(__name__)


class SlideGenerator:
    MAX_WORDS_PER_REQUEST = 10_000

    def generate_for_chapter(self, chapter_title: str, text: str) -> str:
        response = get_llm()(
            [
                SystemMessage(content=chapter_slide_prompt(chapter_title)),
                HumanMessage(content=text),
            ]
        )
        return self._content(response)

    def generate_for_topic(self, text: str) -> str:
        response = get_llm()(
            [
                SystemMessage(content=TOPIC_SLIDE_PROMPT),
                HumanMessage(content=text),
            ]
        )
        return self._content(response)

    def generate_slide_texts(self, data: Dict[str, str]) -> List[str]:
        """Generate one slide blob per dictionary entry, chunking long inputs."""
        results: List[str] = []
        for title, text in data.items():
            if len(text.split()) <= self.MAX_WORDS_PER_REQUEST:
                results.append(self.generate_for_chapter(title, text))
                continue

            points = ""
            index = 0
            remaining_words = len(text.split())
            while remaining_words > 0:
                segment = text[
                    index * self.MAX_WORDS_PER_REQUEST : (index + 1) * self.MAX_WORDS_PER_REQUEST
                ]
                if not segment:
                    break
                points += self.generate_for_chapter(title, segment)
                remaining_words -= self.MAX_WORDS_PER_REQUEST
                index += 1
            results.append(points)
        return results

    def generate_from_lecture_points(self, lectures: Dict[str, List[str]]) -> List[List[str]]:
        """Generate slide blobs for every point of every lecture."""
        generated: List[List[str]] = []
        for _, points in lectures.items():
            lecture_slides = [self.generate_for_topic(point) for point in points if point.strip()]
            generated.append(lecture_slides)
        return generated

    @staticmethod
    def _content(response: object) -> str:
        content = getattr(response, "content", "")
        if not content or not str(content).strip():
            raise GenerationError("The slide generation step returned an empty result. Please try again.")
        return str(content)
