"""Unified course generation pipeline.

The book and "type a course" flows share every expensive step. This service
owns that pipeline so the UI only collects input, shows progress, and renders
the results.
"""

from __future__ import annotations

import logging
import pickle
from contextlib import nullcontext
from functools import lru_cache
from pathlib import Path
from typing import Callable, ContextManager, Dict, Iterable
from uuid import uuid4

from coursegen.ai.qa_engine import QaEngine
from coursegen.ai.slide_explainer import SlideExplainer, is_non_content_title
from coursegen.ai.slide_generator import SlideGenerator
from coursegen.config import Settings, get_settings
from coursegen.errors import ConfigurationError, GenerationError, ValidationError
from coursegen.infrastructure.cdn_storage import CdnStorage
from coursegen.infrastructure.google_drive import GoogleDriveUploader
from coursegen.media.presentation_builder import PresentationBuilder
from coursegen.media.tts import TextToSpeechService
from coursegen.media.video_builder import VideoGenerationService
from coursegen.models import (
    AudioMap,
    CourseArtifacts,
    LectureMap,
    MediaLibrary,
    PresentationStyle,
    UserAccount,
)
from coursegen.repositories.user_repository import UserRepository
from coursegen.utils import safe_filename

logger = logging.getLogger(__name__)

StepFactory = Callable[[str], ContextManager[None]]


def _null_step(message: str) -> ContextManager[None]:
    return nullcontext()


class CourseService:
    def __init__(
        self,
        settings: Settings | None = None,
        slide_generator: SlideGenerator | None = None,
        explainer: SlideExplainer | None = None,
        qa_engine: QaEngine | None = None,
        tts: TextToSpeechService | None = None,
        video_service: VideoGenerationService | None = None,
        presentation_builder: PresentationBuilder | None = None,
        users: UserRepository | None = None,
        cdn: CdnStorage | None = None,
        drive: GoogleDriveUploader | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._slides = slide_generator or SlideGenerator()
        self._explainer = explainer or SlideExplainer()
        self._qa = qa_engine or QaEngine()
        self._tts = tts or TextToSpeechService(self._settings)
        self._video = video_service or VideoGenerationService(self._settings)
        self._presentations = presentation_builder or PresentationBuilder(self._settings)
        self._users = users or UserRepository()
        self._cdn = cdn
        self._drive = drive

    # --------------------------------------------------------------- generation
    def generate_from_book(
        self,
        chapters: Dict[str, str],
        course_name: str,
        step: StepFactory | None = None,
    ) -> CourseArtifacts:
        if not chapters:
            raise ValidationError("Select at least one chapter to generate the course.")
        step = step or _null_step

        with step("Generating slides and explanations..."):
            slide_texts = self._slides.generate_slide_texts(chapters)
            slides = {
                f"Lecture {index + 1}": self._explainer.extract_slides([text])
                for index, text in enumerate(slide_texts)
            }
            short_slides, explanations = self._initial_explanations(slides)

        return self._finish_generation(course_name, slides, short_slides, explanations, step)

    def generate_from_lectures(
        self,
        lectures: LectureMap,
        course_name: str,
        step: StepFactory | None = None,
    ) -> CourseArtifacts:
        if not lectures:
            raise ValidationError("Generate a lecture plan first.")
        step = step or _null_step

        with step("Generating slides and explanations..."):
            generated = self._slides.generate_from_lecture_points(lectures)
            slides = {
                f"Lecture {index + 1}": self._explainer.extract_slides(slide_texts)
                for index, slide_texts in enumerate(generated)
            }
            short_slides, explanations = self._initial_explanations(slides)

        return self._finish_generation(course_name, slides, short_slides, explanations, step)

    def _initial_explanations(
        self,
        slides: LectureMap,
    ) -> tuple[LectureMap, LectureMap]:
        slides = {lecture: slide_map for lecture, slide_map in slides.items() if slide_map}
        if not slides:
            raise GenerationError("No slides could be generated. Please try again.")

        short_slides = {
            lecture: dict(list(slide_map.items())[:2]) for lecture, slide_map in slides.items()
        }
        explanations = {
            lecture: self._explainer.explain_points(slide_map)
            for lecture, slide_map in short_slides.items()
        }
        return short_slides, self._explainer.clean_explanations(explanations)

    def _finish_generation(
        self,
        course_name: str,
        slides: LectureMap,
        short_slides: LectureMap,
        explanations: LectureMap,
        step: StepFactory,
    ) -> CourseArtifacts:
        artifacts = CourseArtifacts(
            course_name=course_name,
            output_stem=f"{safe_filename(course_name, 'course')}_{uuid4().hex}",
            slides=slides,
            short_slides=short_slides,
            explanations=explanations,
        )

        with step("Generating detailed explanations..."):
            detailed = self._explain_with_reference_chain(slides)

        with step("Building presentation slides..."):
            presentation_slides: LectureMap = {}
            for lecture, explanation_map in detailed.items():
                if not explanation_map:
                    continue
                generated = self._slides.generate_slide_texts(explanation_map)
                presentation_slides[lecture] = self._explainer.extract_slides(generated)
            artifacts.presentation_slides = presentation_slides or slides

        with step("Initialising the lecturer..."):
            text_chunks = self._qa.get_text_chunks(self._slides_to_text(slides))
            artifacts.text_chunks = text_chunks
            vector_store = self._qa.build_vector_store(text_chunks)
            artifacts.conversation = self._qa.build_conversation_chain(vector_store)

        with step("Generating narration..."):
            audio_paths: AudioMap = {}
            for lecture, slide_map in explanations.items():
                if slide_map:
                    audio_paths[lecture] = self._tts.generate_audio_chunks(slide_map)
            if not audio_paths:
                raise GenerationError("No narration could be generated for this course.")
            artifacts.audio_paths = audio_paths

        with step("Rendering the lecture video..."):
            artifacts.video_path = str(
                self._video.run(short_slides, audio_paths, artifacts.output_stem)
            )

        return artifacts

    def _explain_with_reference_chain(self, slides: LectureMap) -> LectureMap:
        pickle_path = self._settings.conversation_pickle
        if not pickle_path.is_file():
            raise ConfigurationError(
                "The reference conversation file is missing. Place conversation.pkl at "
                f"{pickle_path} before generating a course."
            )

        try:
            with pickle_path.open("rb") as file_handle:
                chain = pickle.load(file_handle)
        except Exception as exc:
            logger.error("Could not load %s: %s", pickle_path, exc)
            raise GenerationError(
                "The reference conversation file could not be loaded. It must match the "
                "installed LangChain version."
            ) from exc

        detailed: LectureMap = {}
        for lecture, slide_map in slides.items():
            memory = getattr(chain, "memory", None)
            if memory is not None:
                try:
                    memory.clear()
                except AttributeError:
                    pass

            lecture_explanations: Dict[str, str] = {}
            for title, questions in slide_map.items():
                if is_non_content_title(title):
                    continue
                answers = self._answer_questions(chain, questions)
                if len(answers) > 20:
                    lecture_explanations[title] = answers
            detailed[lecture] = lecture_explanations
        return detailed

    @staticmethod
    def _answer_questions(chain: object, questions: Iterable[str]) -> str:
        answers = ""
        for question in questions:
            try:
                response = chain({"question": question})  # type: ignore[operator]
            except Exception as exc:
                logger.warning("Question answering failed for %r: %s", question, exc)
                continue
            answer = str(response.get("answer", "")).strip()
            if not answer:
                answers += f"{question}\n"
            elif answer.startswith(("Yes", "No")):
                answers += " ".join(answer.split(",")[1:]) + "\n"
            elif (
                not answer.startswith("Hello")
                and not answer.endswith("?")
                and not answer.startswith("I ")
                and not answer.startswith("I'm")
                and not answer.startswith("Sorry")
            ):
                answers += answer + "\n"
            else:
                answers += question + "\n"
        return answers

    @staticmethod
    def _slides_to_text(slides: LectureMap) -> str:
        parts: list[str] = []
        for lecture, slide_map in slides.items():
            parts.append(lecture)
            for title, points in slide_map.items():
                parts.append(title)
                parts.extend(points)
        return "\n".join(parts)

    # ---------------------------------------------------------------- publishing
    def publish(
        self,
        artifacts: CourseArtifacts,
        style: PresentationStyle,
        account: UserAccount,
        step: StepFactory | None = None,
    ) -> CourseArtifacts:
        if not artifacts.video_path:
            raise GenerationError("Generate the course before creating its presentation.")
        step = step or _null_step

        with step("Creating the PowerPoint presentation..."):
            presentation_path = self._presentations.create(
                artifacts.presentation_slides,
                style,
                artifacts.output_stem,
            )
            artifacts.presentation_path = str(presentation_path)

        with step("Uploading the video to the CDN..."):
            cdn = self._cdn or CdnStorage(self._settings)
            video_path = Path(artifacts.video_path)
            artifacts.video_link = cdn.upload(video_path, f"videos/{video_path.name}")
            self._users.add_video(account.id, artifacts.output_stem, artifacts.video_link)

        with step("Uploading the presentation to Google Drive..."):
            drive = self._drive or GoogleDriveUploader(self._settings)
            artifacts.presentation_link = drive.upload(presentation_path)
            self._users.add_presentation(
                account.id,
                f"presentation_{artifacts.output_stem}",
                artifacts.presentation_link,
            )

        return artifacts

    # ------------------------------------------------------------------ lecturer
    @staticmethod
    def ask(artifacts: CourseArtifacts, question: str) -> list[object]:
        if artifacts.conversation is None:
            raise GenerationError("The lecturer is not ready yet.")
        response = artifacts.conversation({"question": question})  # type: ignore[operator]
        artifacts.chat_history = list(response.get("chat_history", []))
        return artifacts.chat_history

    # -------------------------------------------------------------------- library
    def library(self, account: UserAccount) -> MediaLibrary:
        return MediaLibrary(
            videos=self._users.list_videos(account.id),
            presentations=self._users.list_presentations(account.id),
        )

    def delete_video(self, account: UserAccount, name: str) -> None:
        self._users.delete_video(account.id, name)

    def delete_presentation(self, account: UserAccount, name: str) -> None:
        self._users.delete_presentation(account.id, name)


@lru_cache(maxsize=1)
def get_course_service() -> CourseService:
    return CourseService()
