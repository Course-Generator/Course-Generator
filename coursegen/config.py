"""Application configuration loaded from environment variables.

Values are read once per process and exposed through :func:`get_settings`.
A local ``.env`` file is loaded automatically; legacy secret files are
supported as fallbacks so existing installations keep working after the
repository was reorganised.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    try:
        return int(value) if value else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    try:
        return float(value) if value else default
    except ValueError:
        return default


def _load_environment() -> None:
    """Load every supported env file without overriding already-set values."""
    for candidate in (
        BASE_DIR / ".env",
        BASE_DIR / "secrets" / "api_key",
        BASE_DIR / "api_key",
    ):
        if candidate.is_file():
            load_dotenv(candidate, override=False)


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    assets_dir: Path
    fonts_dir: Path
    backgrounds_dir: Path
    data_dir: Path
    pdf_dir: Path
    images_dir: Path
    audio_dir: Path
    video_dir: Path
    start_dir: Path
    presentations_dir: Path
    transcriptions_dir: Path
    artifacts_dir: Path
    books_dir: Path
    conversation_pickle: Path

    mongo_uri: str
    mongo_db: str

    openai_model: str
    openai_temperature: float

    bunny_api_key: str
    bunny_storage_zone: str
    bunny_storage_region: str
    bunny_cdn_base_url: str

    google_service_account_file: Path
    google_drive_folder_id: str

    smtp_gmail_user: str
    smtp_gmail_password: str
    smtp_outlook_user: str
    smtp_outlook_password: str

    tts_model: str
    tts_device: str
    whisper_command: str
    whisper_device: str
    log_level: str

    def ensure_workspace(self) -> None:
        """Create the writable runtime directories if they do not exist."""
        for directory in (
            self.data_dir,
            self.pdf_dir,
            self.images_dir,
            self.audio_dir,
            self.video_dir,
            self.start_dir,
            self.presentations_dir,
            self.transcriptions_dir,
            self.artifacts_dir,
            self.books_dir,
            self.assets_dir,
            self.fonts_dir,
            self.backgrounds_dir,
            self.base_dir / "secrets",
        ):
            directory.mkdir(parents=True, exist_ok=True)


def _resolve_google_service_account(base_dir: Path) -> Path:
    configured = _env("GOOGLE_SERVICE_ACCOUNT_FILE")
    if configured:
        candidate = Path(configured)
        return candidate if candidate.is_absolute() else base_dir / candidate
    for candidate in (base_dir / "secrets" / "service_account.json", base_dir / "service_account.json"):
        if candidate.is_file():
            return candidate
    return base_dir / "secrets" / "service_account.json"


def _resolve_conversation_pickle(data_dir: Path) -> Path:
    configured = _env("CONVERSATION_PICKLE")
    if configured:
        candidate = Path(configured)
        return candidate if candidate.is_absolute() else BASE_DIR / candidate
    preferred = data_dir / "artifacts" / "conversation.pkl"
    if preferred.is_file():
        return preferred
    legacy = BASE_DIR / "conversation.pkl"
    return legacy if legacy.is_file() else preferred


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_environment()

    workspace = Path(_env("WORKSPACE_DIR", "data"))
    data_dir = workspace if workspace.is_absolute() else BASE_DIR / workspace
    assets_dir = BASE_DIR / "assets"

    bunny_zone = _env("BUNNY_STORAGE_ZONE")
    bunny_region = _env("BUNNY_STORAGE_REGION", "de")
    cdn_base = _env("BUNNY_CDN_BASE_URL")
    if not cdn_base and bunny_zone:
        cdn_base = f"https://{bunny_zone}.b-cdn.net"
    cdn_base = cdn_base.rstrip("/")

    return Settings(
        base_dir=BASE_DIR,
        assets_dir=assets_dir,
        fonts_dir=assets_dir / "fonts",
        backgrounds_dir=assets_dir / "backgrounds",
        data_dir=data_dir,
        pdf_dir=data_dir / "pdfs",
        images_dir=data_dir / "images",
        audio_dir=data_dir / "audio",
        video_dir=data_dir / "video",
        start_dir=data_dir / "start",
        presentations_dir=data_dir / "presentations",
        transcriptions_dir=data_dir / "transcriptions",
        artifacts_dir=data_dir / "artifacts",
        books_dir=data_dir / "books",
        conversation_pickle=_resolve_conversation_pickle(data_dir),
        mongo_uri=_env("MONGODB_URI", "mongodb://localhost:27017"),
        mongo_db=_env("MONGODB_DB", "grad"),
        openai_model=_env("OPENAI_MODEL", "gpt-3.5-turbo"),
        openai_temperature=_env_float("OPENAI_TEMPERATURE", 0.8),
        bunny_api_key=_env("BUNNY_STORAGE_API_KEY"),
        bunny_storage_zone=bunny_zone,
        bunny_storage_region=bunny_region,
        bunny_cdn_base_url=cdn_base,
        google_service_account_file=_resolve_google_service_account(BASE_DIR),
        google_drive_folder_id=_env("GOOGLE_DRIVE_FOLDER_ID"),
        smtp_gmail_user=_env("SMTP_GMAIL_USER"),
        smtp_gmail_password=_env("SMTP_GMAIL_APP_PASSWORD"),
        smtp_outlook_user=_env("SMTP_OUTLOOK_USER"),
        smtp_outlook_password=_env("SMTP_OUTLOOK_PASSWORD"),
        tts_model=_env("TTS_MODEL", "microsoft/speecht5_tts"),
        tts_device=_env("TTS_DEVICE", "cuda"),
        whisper_command=_env("WHISPER_COMMAND", "whisper"),
        whisper_device=_env("WHISPER_DEVICE", "cuda"),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
    )
