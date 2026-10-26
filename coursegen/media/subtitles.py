"""Whisper transcription and subtitle burn-in."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Iterable, List, Sequence

import pysrt
from moviepy.editor import CompositeVideoClip, VideoFileClip

from coursegen.config import Settings, get_settings
from coursegen.errors import ConfigurationError, GenerationError

logger = logging.getLogger(__name__)


class SubtitleService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def transcribe(self, audio_files: Sequence[str | Path]) -> List[Path]:
        self._settings.transcriptions_dir.mkdir(parents=True, exist_ok=True)
        transcriptions: List[Path] = []
        for audio_file in audio_files:
            audio_path = Path(audio_file)
            srt_path = self._settings.transcriptions_dir / f"{audio_path.stem}.srt"
            if not srt_path.is_file():
                self._run_whisper(audio_path)
            if not srt_path.is_file():
                raise GenerationError(f"Whisper did not produce subtitles for {audio_path.name}.")
            transcriptions.append(srt_path)
        return transcriptions

    def add_subtitles_to_videos(
        self,
        video_files: Sequence[str | Path],
        srt_files: Sequence[str | Path],
    ) -> List[Path]:
        subtitled_videos: List[Path] = []
        for video_file, srt_file in zip(video_files, srt_files, strict=False):
            video_path = Path(video_file)
            output_path = video_path.with_name(f"{video_path.stem}_subtitled.mp4")
            self._add_subtitles(video_path, Path(srt_file), output_path)
            subtitled_videos.append(output_path)
        return subtitled_videos

    def _run_whisper(self, audio_path: Path) -> None:
        command = [
            self._settings.whisper_command,
            str(audio_path),
            "--language",
            "English",
            "--output_format",
            "srt",
            "--task",
            "transcribe",
            "--output_dir",
            str(self._settings.transcriptions_dir),
            "--device",
            self._settings.whisper_device,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise ConfigurationError(
                "The Whisper CLI was not found. Install openai-whisper and make sure "
                "the 'whisper' command is on PATH (or set WHISPER_COMMAND)."
            ) from exc
        except subprocess.CalledProcessError as exc:
            logger.error("Whisper failed for %s: %s", audio_path.name, exc.stderr)
            raise GenerationError(f"Whisper could not transcribe {audio_path.name}.") from exc

    def _add_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> None:
        video = VideoFileClip(str(video_path))
        final_video = None
        try:
            subtitles = pysrt.open(str(srt_path))
            subtitle_clips = self._create_subtitle_clips(subtitles, video.size)
            final_video = CompositeVideoClip([video] + subtitle_clips)
            final_video.audio = video.audio
            final_video.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )
        except Exception as exc:
            logger.error("Adding subtitles to %s failed: %s", video_path.name, exc)
            raise GenerationError(
                "Could not burn subtitles into the video. MoviePy's TextClip requires ImageMagick."
            ) from exc
        finally:
            if final_video is not None:
                final_video.close()
            video.close()

    @staticmethod
    def _create_subtitle_clips(subtitles: Iterable[pysrt.SubRipItem], video_size: tuple[int, int], fontsize: int = 24):
        from moviepy.editor import TextClip

        subtitle_clips = []
        video_width, video_height = video_size
        for subtitle in subtitles:
            start = _time_to_seconds(subtitle.start)
            end = _time_to_seconds(subtitle.end)
            text_clip = (
                TextClip(
                    subtitle.text,
                    fontsize=fontsize,
                    font="Arial",
                    color="black",
                    size=(video_width * 3 / 4, None),
                    method="caption",
                )
                .set_start(start)
                .set_duration(end - start)
            )
            subtitle_clips.append(text_clip.set_position(("center", video_height * 4 / 5)))
        return subtitle_clips


def _time_to_seconds(value: pysrt.SubRipTime) -> float:
    return value.hours * 3600 + value.minutes * 60 + value.seconds + value.milliseconds / 1000
