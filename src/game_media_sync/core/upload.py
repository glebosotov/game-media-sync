"""Pure Immich upload — hash, POST, done."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from .metadata import STEAM_DECK, DeviceInfo


def upload_to_immich(
    filepath: str,
    api_key: str,
    server_url: str,
    *,
    device: DeviceInfo = STEAM_DECK,
    creation_date: Optional[datetime] = None,
    is_favorite: bool = False,
    visibility: str = "timeline",
) -> Dict[str, Any]:
    """Upload a single file to Immich and return the JSON response.

    Metadata embedding must happen *before* calling this function.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    sha1 = hashlib.sha1()
    with open(filepath, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            sha1.update(chunk)

    if creation_date is None:
        creation_date = datetime.fromtimestamp(os.path.getmtime(filepath))
    file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))

    url = f"{server_url.rstrip('/')}/api/assets"
    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
        "x-immich-checksum": sha1.hexdigest(),
    }
    device_id = f"{device.make}-{device.model}".lower().replace(" ", "-")
    basename = os.path.basename(filepath)

    with open(filepath, "rb") as fh:
        resp = requests.post(
            url,
            headers=headers,
            files={"assetData": (basename, fh, "application/octet-stream")},
            data={
                "deviceAssetId": basename,
                "deviceId": device_id,
                "fileCreatedAt": creation_date.isoformat(),
                "fileModifiedAt": file_modified.isoformat(),
                "filename": basename,
                "isFavorite": str(is_favorite).lower(),
                "visibility": visibility,
            },
            timeout=30.0,
        )

    resp.raise_for_status()
    result = resp.json()

    if "error" in result:
        raise ValueError(f"Immich API error: {result['error']}")

    return result
