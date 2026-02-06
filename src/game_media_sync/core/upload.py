import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .metadata import (
    STEAM_DECK,
    DeviceInfo,
    MediaMetadata,
    set_image_metadata,
)


def extract_date_from_filename(filename: str) -> datetime:
    """
    Extract creation date from Steam screenshot filename.
    Format: YYYYMMDDHHMMSS_N.jpg
    Example: 20250727170425_1.jpg -> July 27, 2025 17:04:25
    """
    try:
        date_part = filename.split("_")[0]
        if len(date_part) == 14 and date_part.isdigit():
            year = int(date_part[0:4])
            month = int(date_part[4:6])
            day = int(date_part[6:8])
            hour = int(date_part[8:10])
            minute = int(date_part[10:12])
            second = int(date_part[12:14])

            return datetime(year, month, day, hour, minute, second)
        else:
            return datetime.fromtimestamp(os.path.getctime(filename))
    except (ValueError, IndexError):
        return datetime.fromtimestamp(os.path.getctime(filename))


def cleanup_temp_file(file_path: str, original_path: str):
    """Clean up temporary file if it was created."""
    if file_path != original_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass


def upload_file_to_immich(
    filename: str,
    api_key: str,
    server_url: str,
    game_name: Optional[str] = None,
    is_favorite: bool = False,
    visibility: str = "timeline",
    media_type: str = "screenshot",
    device: DeviceInfo = STEAM_DECK,
    creation_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Upload a file to Immich using the correct API endpoint.

    For **images** the function embeds EXIF metadata (dates, camera info,
    game name) via :func:`set_image_metadata` before uploading.  For
    **videos** the caller is expected to have already embedded metadata
    (e.g. via :func:`set_video_metadata`).

    Args:
        filename: Path to the file to upload
        api_key: Immich API key (used with x-api-key header)
        server_url: Immich server URL (e.g., "https://your-immich-server.com")
        game_name: Optional game name for metadata
        is_favorite: Whether to mark the asset as favorite
        visibility: Asset visibility ("archive", "timeline", "hidden", "locked")
        media_type: Type of media ("screenshot" or "video")
        device: Device that captured the media (default: STEAM_DECK)
        creation_date: Optional creation date.  If not provided, will be
            extracted from filename (images) or file timestamp (videos).

    Returns:
        API response containing upload status and asset ID

    Raises:
        FileNotFoundError: If the specified file doesn't exist
        requests.RequestException: If the upload request fails
        ValueError: If the API response indicates an error
    """

    if not os.path.exists(filename):
        raise FileNotFoundError(f"File not found: {filename}")

    # Generate SHA1 checksum for duplicate detection
    sha1_hash = hashlib.sha1()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha1_hash.update(chunk)
    checksum = sha1_hash.hexdigest()

    upload_url = f"{server_url.rstrip('/')}/api/assets"

    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
        "x-immich-checksum": checksum,
    }

    file_extension = Path(filename).suffix.lower()
    is_video = file_extension in [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"]

    if is_video:
        if creation_date is None:
            creation_date = datetime.fromtimestamp(os.path.getmtime(filename))
        file_modified_date = datetime.fromtimestamp(os.path.getmtime(filename))
        upload_file_path = filename
    else:
        if creation_date is None:
            creation_date = extract_date_from_filename(filename)
        file_modified_date = datetime.fromtimestamp(os.path.getmtime(filename))

        meta = MediaMetadata(
            creation_date=creation_date,
            device=device,
            game_name=game_name,
        )

        base, ext = os.path.splitext(filename)
        temp_path = f"{base}_exif{ext}"

        if set_image_metadata(filename, temp_path, meta):
            upload_file_path = temp_path
        else:
            upload_file_path = filename

    try:
        with open(upload_file_path, "rb") as file:
            files = {
                "assetData": (
                    os.path.basename(filename),
                    file,
                    "application/octet-stream",
                )
            }

            data = {
                "deviceAssetId": os.path.basename(filename),
                "deviceId": "steam-deck",
                "fileCreatedAt": creation_date.isoformat(),
                "fileModifiedAt": file_modified_date.isoformat(),
                "filename": os.path.basename(filename),
                "isFavorite": str(is_favorite).lower(),
                "visibility": visibility,
            }

            response = requests.post(
                upload_url, headers=headers, files=files, data=data, timeout=30.0
            )

            response.raise_for_status()

            try:
                result = response.json()
            except ValueError:
                result = {
                    "response_text": response.text,
                    "status_code": response.status_code,
                }

            if "error" in result:
                raise ValueError(f"API Error: {result['error']}")

            return result

    finally:
        cleanup_temp_file(upload_file_path, filename)


if __name__ == "__main__":
    IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")
    IMMICH_SERVER_URL = os.getenv("IMMICH_SERVER_URL")

    if not IMMICH_API_KEY or not IMMICH_SERVER_URL:
        print("Error: Set IMMICH_API_KEY and IMMICH_SERVER_URL environment variables")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python -m game_media_sync.core.upload <filename>")
        sys.exit(1)

    try:
        result = upload_file_to_immich(
            filename=sys.argv[1],
            api_key=IMMICH_API_KEY,
            server_url=IMMICH_SERVER_URL,
        )
        print(f"Upload successful: {result}")
    except Exception as e:
        print(f"Upload failed: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Convenience wrappers (read credentials from env)
# ---------------------------------------------------------------------------


def upload_media(filename, game_name=None, media_type="screenshot"):
    """Upload media file to Immich. Reads credentials from environment."""
    try:
        api_key = os.getenv("IMMICH_API_KEY")
        server_url = os.getenv("IMMICH_SERVER_URL")

        if not api_key or not server_url:
            print("Error: Immich credentials not configured")
            return False

        return upload_file_to_immich(
            filename=filename,
            game_name=game_name,
            api_key=api_key,
            server_url=server_url,
            is_favorite=False,
            visibility="timeline",
            media_type=media_type,
        )

    except Exception as e:
        print(f"Error: Failed to upload {os.path.basename(filename)}: {e}")
        return False


def upload_screenshot(filename, game_name=None):
    """Upload screenshot to Immich photo server."""
    return upload_media(filename, game_name, "screenshot")


def upload_video(filename, game_name=None):
    """Upload video to Immich photo server."""
    return upload_media(filename, game_name, "video")
