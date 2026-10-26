"""Render narrated lecture videos from slide maps and audio files."""

from __future__ import annotations

import contextlib
import logging
import wave
from pathlib import Path
from typing import Dict, List, Sequence

import cv2
import numpy as np
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips
from PIL import Image, ImageDraw
from pydub import AudioSegment

from coursegen.config import Settings, get_settings
from coursegen.errors import GenerationError
from coursegen.media.fonts import load_font
from coursegen.media.subtitles import SubtitleService
from coursegen.models import SlideMap
from coursegen.utils import safe_filename

logger = logging.getLogger(__name__)

RENDER_WIDTH = 1024
RENDER_HEIGHT = 768
VIDEO_FPS = 30
INTRO_SECONDS = 5.0


class SlideImageFactory:
    def create_blank_slide_image(self, width: int, height: int, background_color=(255, 255, 255)) -> Image.Image:
        return Image.new("RGB", (width, height), background_color)

    def create_slides(self, slide_map: SlideMap) -> List[Image.Image]:
        slides: List[Image.Image] = []
        for title_text, content_lines in slide_map.items():
            image = self.create_blank_slide_image(RENDER_WIDTH, RENDER_HEIGHT)
            self.add_title(image, title_text, RENDER_WIDTH - 20, RENDER_HEIGHT // 4, (30, 144, 255))
            self.add_content(image, content_lines, RENDER_WIDTH - 20, RENDER_HEIGHT - 40)
            slides.append(image)
        return slides

    def add_title(
        self,
        image: Image.Image,
        title_text: str,
        max_width: int,
        max_height: int,
        font_color=(0, 0, 0),
    ) -> None:
        font_size = 70
        draw = ImageDraw.Draw(image)
        font = load_font("Arial", font_size)
        text = title_text.strip() or " "
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        while (right - left > max_width or bottom - top > max_height) and font_size > 12:
            font_size -= 1
            font = load_font("Arial", font_size)
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        draw.text(
            ((max_width - (right - left)) / 2, (max_height - (bottom - top)) / 2),
            text,
            font=font,
            fill=font_color,
        )

    def add_content(
        self,
        image: Image.Image,
        content_lines: Sequence[str],
        max_width: int,
        max_height: int,
        font_size: int = 35,
        font_color=(0, 0, 0),
    ) -> None:
        if not content_lines:
            return

        draw = ImageDraw.Draw(image)
        left_margin = 60
        indent = 40
        top = max_height // 4 + 30
        bottom = image.height - 50
        y = top

        for line in content_lines:
            split_lines = self._split_text_into_lines(
                line,
                max_width - indent,
                load_font("Arial", font_size),
                draw,
            )
            for split_line in split_lines:
                current_size = font_size
                line_font = load_font("Arial", current_size)
                line_left, line_top, line_right, line_bottom = draw.textbbox((0, 0), split_line, font=line_font)
                while line_right - line_left > max_width - indent and current_size > 10:
                    current_size -= 1
                    line_font = load_font("Arial", current_size)
                    line_left, line_top, line_right, line_bottom = draw.textbbox(
                        (0, 0), split_line, font=line_font
                    )

                line_height = line_bottom - line_top
                if y + line_height > bottom:
                    return
                draw.text((left_margin + indent, y), split_line, font=line_font, fill=font_color)
                y += line_height + 15

    def create_starting_slide_image(
        self,
        text: str,
        image_size: tuple[int, int] = (800, 600),
        font_size: int = 36,
    ) -> Image.Image:
        image = Image.new("RGB", image_size, (255, 255, 255))
        draw = ImageDraw.Draw(image)
        font = load_font("Arial", font_size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        draw.text(
            ((image_size[0] - (right - left)) // 2, (image_size[1] - (bottom - top)) // 2),
            text,
            fill=(0, 0, 0),
            font=font,
        )
        return image

    @staticmethod
    def _split_text_into_lines(text: str, max_width: int, font, draw: ImageDraw.ImageDraw) -> List[str]:
        lines: List[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines


class VideoAssembler:
    def images_to_videos(
        self,
        images: Sequence[Image.Image],
        audio_durations: Sequence[float],
        output_dir: str | Path,
        prefix: str = "video",
    ) -> List[Path]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        videos: List[Path] = []

        for index, image in enumerate(images):
            duration = max(float(audio_durations[index]), 1.0)
            frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            video_path = output_path / f"{safe_filename(prefix)}_{index}.mp4"
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                VIDEO_FPS,
                (frame.shape[1], frame.shape[0]),
            )
            if not writer.isOpened():
                raise GenerationError(f"Could not create the video file {video_path.name}.")
            try:
                for _ in range(max(1, int(round(duration * VIDEO_FPS)))):
                    writer.write(frame)
            finally:
                writer.release()
            videos.append(video_path)
        return videos

    def combine_videos_with_audios(
        self,
        video_files: Sequence[str | Path],
        audio_files: Sequence[str | Path],
        output_dir: str | Path,
    ) -> List[Path]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        combined_paths: List[Path] = []

        for video_file, audio_file in zip(video_files, audio_files, strict=False):
            video_path = Path(video_file)
            final_path = output_path / f"{video_path.stem}_with_audio.mp4"
            video_clip = None
            audio_clip = None
            output_clip = None
            try:
                video_clip = VideoFileClip(str(video_path))
                audio_clip = AudioFileClip(str(audio_file))
                output_clip = video_clip.set_audio(audio_clip)
                output_clip.write_videofile(
                    str(final_path),
                    codec="libx264",
                    audio_codec="aac",
                    threads=4,
                    logger=None,
                )
            except Exception as exc:
                logger.error("Combining %s with %s failed: %s", video_path.name, audio_file, exc)
                raise GenerationError("Could not add narration to the lecture video.") from exc
            finally:
                if output_clip is not None:
                    output_clip.close()
                if audio_clip is not None:
                    audio_clip.close()
                if video_clip is not None:
                    video_clip.close()
            combined_paths.append(final_path)
        return combined_paths

    def concatenate_videos(self, video_files: Sequence[str | Path], output_file: str | Path) -> Path:
        clips = [VideoFileClip(str(video)) for video in video_files]
        final_clip = None
        try:
            final_clip = concatenate_videoclips(clips)
            final_clip.write_videofile(str(output_file), codec="libx264", audio_codec="aac", logger=None)
        finally:
            if final_clip is not None:
                final_clip.close()
            for clip in clips:
                clip.close()
        return Path(output_file)

    @staticmethod
    def calculate_audio_durations(audio_files: Sequence[str | Path]) -> List[float]:
        durations: List[float] = []
        for audio_file in audio_files:
            try:
                with contextlib.closing(wave.open(str(audio_file), "r")) as handle:
                    durations.append(handle.getnframes() / float(handle.getframerate()))
            except (wave.Error, OSError) as exc:
                logger.warning("Could not measure %s: %s", audio_file, exc)
                durations.append(1.0)
        return durations

    @staticmethod
    def merge_audio(audio_paths: Sequence[str | Path]) -> AudioSegment:
        merged = AudioSegment.empty()
        for path in audio_paths:
            merged += AudioSegment.from_wav(str(path))
        return merged

    def merge_all_audio(
        self,
        audio_map: Dict[str, List[str]],
        output_dir: str | Path,
        prefix: str = "",
    ) -> List[str]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        merged_paths: List[str] = []
        for title, paths in audio_map.items():
            if not paths:
                continue
            stem = safe_filename(title.replace("?", ""), "section")
            if prefix:
                stem = f"{safe_filename(prefix)}_{stem}"
            merged_path = output_path / f"{stem}_merged.wav"
            self.merge_audio(paths).export(str(merged_path), format="wav")
            merged_paths.append(str(merged_path))
        return merged_paths


class VideoGenerationService:
    def __init__(
        self,
        settings: Settings | None = None,
        factory: SlideImageFactory | None = None,
        assembler: VideoAssembler | None = None,
        subtitles: SubtitleService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._factory = factory or SlideImageFactory()
        self._assembler = assembler or VideoAssembler()
        self._subtitles = subtitles or SubtitleService(self._settings)

    def run(
        self,
        slide_map: Dict[str, SlideMap],
        audio_map: Dict[str, Dict[str, List[str]]],
        name: str,
    ) -> Path:
        if not slide_map:
            raise GenerationError("There are no slides to render.")
        self._settings.video_dir.mkdir(parents=True, exist_ok=True)
        self._settings.start_dir.mkdir(parents=True, exist_ok=True)

        lecture_videos: List[Path] = []
        for index, (lecture, slides) in enumerate(slide_map.items(), start=1):
            if not slides:
                continue
            if lecture not in audio_map or not audio_map[lecture]:
                raise GenerationError(f"Missing narration for {lecture}.")
            lecture_tag = f"lec{index}"

            start_image = self._factory.create_starting_slide_image(f"Lecture {index}")
            start_video = self._assembler.images_to_videos(
                [start_image],
                [INTRO_SECONDS],
                self._settings.start_dir,
                prefix=f"{lecture_tag}_start",
            )[0]

            slide_images = self._factory.create_slides(slides)
            audio_files = self._assembler.merge_all_audio(
                audio_map[lecture],
                self._settings.audio_dir,
                prefix=lecture_tag,
            )
            durations = self._assembler.calculate_audio_durations(audio_files)
            silent_videos = self._assembler.images_to_videos(
                slide_images,
                durations,
                self._settings.video_dir,
                prefix=lecture_tag,
            )
            narrations = self._assembler.combine_videos_with_audios(
                silent_videos,
                audio_files,
                self._settings.video_dir,
            )
            subtitles = self._subtitles.transcribe(audio_files)
            subtitled = self._subtitles.add_subtitles_to_videos(narrations, subtitles)

            lecture_path = self._settings.video_dir / f"final_{name}_{lecture_tag}.mp4"
            self._assembler.concatenate_videos(subtitled, lecture_path)

            composed_path = self._settings.video_dir / f"final_edited_{name}_{lecture_tag}.mp4"
            self._compose_intro(start_video, lecture_path, composed_path)
            lecture_videos.append(composed_path)
            logger.info("Finished %s", composed_path.name)

        if not lecture_videos:
            raise GenerationError("No lecture videos were produced.")
        final_path = self._settings.video_dir / f"final_{name}.mp4"
        self._assembler.concatenate_videos(lecture_videos, final_path)
        return final_path

    def _compose_intro(self, intro_path: Path, lecture_path: Path, output_path: Path) -> None:
        intro_clip = None
        lecture_clip = None
        final_clip = None
        try:
            intro_clip = VideoFileClip(str(intro_path)).resize((RENDER_WIDTH, RENDER_HEIGHT))
            lecture_clip = VideoFileClip(str(lecture_path)).resize((RENDER_WIDTH, RENDER_HEIGHT))
            final_clip = concatenate_videoclips([intro_clip, lecture_clip], method="compose")
            final_clip.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )
        finally:
            if final_clip is not None:
                final_clip.close()
            if lecture_clip is not None:
                lecture_clip.close()
            if intro_clip is not None:
                intro_clip.close()
