"""Generate a lecture plan (titles + talking points) from a course name."""

from __future__ import annotations

import logging

from langchain.schema import HumanMessage, SystemMessage

from coursegen.ai.prompts import LECTURE_PLAN_PROMPT
from coursegen.errors import GenerationError, ValidationError
from coursegen.infrastructure.llm import get_llm
from coursegen.models import LectureMap

logger = logging.getLogger(__name__)


class LectureGenerator:
    def generate(self, lecture_count: int, course_name: str) -> LectureMap:
        if lecture_count < 1:
            raise ValidationError("The number of lectures must be at least 1.")
        if not course_name.strip():
            raise ValidationError("Enter a course name.")

        response = get_llm()(
            [
                SystemMessage(content=LECTURE_PLAN_PROMPT),
                HumanMessage(content=f"number of lecture = {lecture_count},course name = {course_name}"),
            ]
        )
        lectures = self._parse(response.content)
        if not lectures:
            raise GenerationError("The lecture plan could not be generated. Please try again.")
        return lectures

    @staticmethod
    def _parse(text: str) -> LectureMap:
        lectures: LectureMap = {}
        current_name = ""
        current_points: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.lower().startswith("lecture"):
                if current_name and current_points:
                    lectures[current_name] = current_points
                current_name = line.split(":", 1)[0].strip()
                current_points = []
            elif line:
                current_points.append(line)

        if current_name and current_points:
            lectures[current_name] = current_points
        return lectures
