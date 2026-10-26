"""Upload generated presentations to Google Drive."""

from __future__ import annotations

import logging
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from coursegen.config import Settings, get_settings
from coursegen.errors import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive"]
_PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class GoogleDriveUploader:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def upload(self, file_path: Path) -> str:
        file_path = Path(file_path)
        if not file_path.is_file():
            raise ExternalServiceError(f"The presentation file does not exist: {file_path}")
        if not self._settings.google_drive_folder_id:
            raise ConfigurationError(
                "Google Drive is not configured. Set GOOGLE_DRIVE_FOLDER_ID in your .env file."
            )
        if not self._settings.google_service_account_file.is_file():
            raise ConfigurationError(
                "Google service account file not found at "
                f"{self._settings.google_service_account_file}. Place it in the secrets/ folder."
            )

        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(self._settings.google_service_account_file),
                scopes=_SCOPES,
            )
            service = build("drive", "v3", credentials=credentials, cache_discovery=False)
            uploaded = (
                service.files()
                .create(
                    body={
                        "name": file_path.name,
                        "parents": [self._settings.google_drive_folder_id],
                    },
                    media_body=MediaFileUpload(str(file_path), mimetype=_PPTX_MIME),
                    fields="id,webViewLink",
                )
                .execute()
            )
        except (HttpError, OSError, ValueError) as exc:
            logger.error("Google Drive upload failed: %s", exc)
            raise ExternalServiceError("Could not upload the presentation to Google Drive.") from exc

        link = uploaded.get("webViewLink")
        if not link:
            raise ExternalServiceError("Google Drive did not return a shareable link.")
        logger.info("Uploaded %s to Google Drive", file_path.name)
        return str(link)
