"""Text-to-speech generation with a cached SpeechT5 pipeline."""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path

import soundfile as sf
import torch
from datasets import load_dataset
from transformers import pipeline

from coursegen.config import Settings, get_settings
from coursegen.errors import GenerationError
from coursegen.models import SlideMap
from coursegen.utils import safe_filename

logger = logging.getLogger(__name__)


class TextToSpeechService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._settings.audio_dir.mkdir(parents=True, exist_ok=True)

    @cached_property
    def _device(self) -> str:
        configured = self._settings.tts_device or "cuda"
        if configured.startswith("cuda") and not torch.cuda.is_available():
            logger.warning("CUDA is not available; running text-to-speech on CPU.")
            return "cpu"
        return configured

    @cached_property
    def _speaker_embedding(self) -> torch.Tensor:
        dataset = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")
        return torch.tensor(dataset[7200]["xvector"]).unsqueeze(0)

    @cached_property
    def _synthesizer(self):
        logger.info("Loading text-to-speech model %s on %s", self._settings.tts_model, self._device)
        return pipeline("text-to-speech", self._settings.tts_model, device=self._device)

    def generate_audio_chunks(self, sections: SlideMap) -> dict[str, list[str]]:
        audio_paths: dict[str, list[str]] = {}
        for section_title, texts in sections.items():
            title = safe_filename(section_title.replace("?", "").replace("*", ""), "section")
            paths: list[str] = []
            for text_index, text in enumerate(texts):
                for chunk_index, chunk in enumerate(self._split_text(text)):
                    path = self._settings.audio_dir / (
                        f"{title}_speech_chunk_{text_index}_{chunk_index + 1}.wav"
                    )
                    if not path.is_file():
                        self._synthesize(chunk, path)
                    paths.append(str(path))
            audio_paths[section_title] = paths
        return audio_paths

    def _synthesize(self, text: str, path: Path) -> None:
        try:
            speech = self._synthesizer(
                text,
                forward_params={"speaker_embeddings": self._speaker_embedding},
            )
            sf.write(str(path), speech["audio"], samplerate=speech["sampling_rate"])
        except Exception as exc:
            logger.error("Text-to-speech failed for %s: %s", path.name, exc)
            raise GenerationError("Could not synthesize speech for the course narration.") from exc

    @staticmethod
    def _split_text(text: str, max_width: int = 400) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in text.split():
            if len(current) + len(word) <= max_width:
                current = f"{current} {word}".strip()
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
