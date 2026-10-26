"""BunnyCDN storage client."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List
from urllib.parse import quote

import requests

from coursegen.config import Settings, get_settings
from coursegen.errors import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)


class CdnStorage:
    def __init__(self, settings: Settings | None = None, session: requests.Session | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.bunny_api_key or not self._settings.bunny_storage_zone:
            raise ConfigurationError(
                "BunnyCDN is not configured. Set BUNNY_STORAGE_API_KEY and "
                "BUNNY_STORAGE_ZONE in your .env file."
            )
        self._session = session or requests.Session()
        region = self._settings.bunny_storage_region
        host = "storage.bunnycdn.com" if region in ("", "de") else f"{region}.storage.bunnycdn.com"
        self._base_url = f"https://{host}/{self._settings.bunny_storage_zone}/"
        self._cdn_base = self._settings.bunny_cdn_base_url

    def upload(self, local_path: Path, remote_path: str) -> str:
        local_path = Path(local_path)
        if not local_path.is_file():
            raise ExternalServiceError(f"The file to upload does not exist: {local_path}")

        remote = remote_path.lstrip("/")
        url = self._base_url + quote(remote)
        headers = {
            "AccessKey": self._settings.bunny_api_key,
            "Content-Type": "application/octet-stream",
            "Accept": "application/json",
        }
        try:
            with local_path.open("rb") as file_handle:
                response = self._session.put(url, data=file_handle, headers=headers, timeout=300)
        except requests.RequestException as exc:
            raise ExternalServiceError(f"Could not upload {local_path.name} to BunnyCDN.") from exc

        if response.status_code >= 400:
            raise ExternalServiceError(
                f"BunnyCDN rejected the upload ({response.status_code})."
            )
        logger.info("Uploaded %s to %s", local_path.name, remote)
        return f"{self._cdn_base}/{quote(remote)}"

    def delete(self, remote_path: str) -> None:
        remote = remote_path.lstrip("/")
        url = self._base_url + quote(remote)
        response = self._session.delete(
            url,
            headers={"AccessKey": self._settings.bunny_api_key, "Accept": "application/json"},
            timeout=60,
        )
        if response.status_code >= 400:
            raise ExternalServiceError(f"BunnyCDN could not delete {remote} ({response.status_code}).")

    def list_objects(self, remote_path: str = "") -> List[str]:
        remote = remote_path.strip("/")
        url = self._base_url + (quote(remote) + "/" if remote else "")
        response = self._session.get(
            url,
            headers={"AccessKey": self._settings.bunny_api_key, "Accept": "application/json"},
            timeout=60,
        )
        if response.status_code >= 400:
            raise ExternalServiceError(f"BunnyCDN could not list {remote or '/'} ({response.status_code}).")
        payload: Any = response.json()
        return [str(item.get("ObjectName")) for item in payload if item.get("ObjectName")]
