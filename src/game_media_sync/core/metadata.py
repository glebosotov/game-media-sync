"""
Unified media metadata service.

Provides a single set of functions for embedding metadata (dates, camera info,
game names) into images and videos across all platforms (Steam, PS5, Switch).

Tools used:
  - exiftool  for JPG and MP4 containers
  - FFmpeg    for WebM / MOV containers (exiftool support is limited)
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceInfo:
    """Describes the device that captured the media."""

    make: str
    model: str


@dataclass
class MediaMetadata:
    """All metadata that should be written into a media file."""

    creation_date: datetime
    device: DeviceInfo
    game_name: Optional[str] = None


# Pre-built device constants
STEAM_DECK = DeviceInfo(make="Valve", model="Steam Deck")
PS5 = DeviceInfo(make="Sony Interactive Entertainment", model="PlayStation 5")
SWITCH2 = DeviceInfo(make="Nintendo", model="Nintendo Switch 2")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_exiftool_path() -> str:
    """Return the path to the exiftool binary.

    Checks the ``EXIFTOOL_PATH`` environment variable first (directory containing
    the binary).  Falls back to the bare ``exiftool`` command name so that it
    can be found on ``$PATH``.
    """
    exiftool_dir = os.getenv("EXIFTOOL_PATH")
    if not exiftool_dir:
        return "exiftool"

    possible_names = ["exiftool", "exiftool.exe"]
    for name in possible_names:
        full_path = os.path.join(exiftool_dir, name)
        if os.path.exists(full_path) and os.access(full_path, os.X_OK):
            return full_path

    return "exiftool"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def set_image_metadata(source: str, dest: str, meta: MediaMetadata) -> bool:
    """Copy *source* image to *dest* and embed EXIF metadata via exiftool.

    Sets the following tags:
      - DateTime, DateTimeOriginal, DateTimeDigitized
      - ImageDescription  (game name, when provided)
      - Make, Model

    Args:
        source: Path to the original image file.
        dest:   Path where the tagged copy will be written.
        meta:   Metadata to embed.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    try:
        shutil.copy2(source, dest)

        exiftool = get_exiftool_path()
        exif_dt = meta.creation_date.strftime("%Y:%m:%d %H:%M:%S")

        cmd = [
            exiftool,
            "-overwrite_original",
            f"-DateTime={exif_dt}",
            f"-DateTimeOriginal={exif_dt}",
            f"-DateTimeDigitized={exif_dt}",
            f"-Make={meta.device.make}",
            f"-Model={meta.device.model}",
        ]

        if meta.game_name:
            cmd.append(f"-ImageDescription={meta.game_name}")

        cmd.append(dest)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return True
        else:
            print(
                f"Error: exiftool failed on {Path(source).name}: {result.stderr.strip()}"
            )
            return False

    except Exception as e:
        print(f"Error: processing image {Path(source).name}: {e}")
        return False


def set_video_metadata(
    source: str,
    dest: str,
    meta: MediaMetadata,
    container: str,
) -> bool:
    """Copy *source* video to *dest* and embed metadata.

    - **MP4** containers are handled by *exiftool* (single-pass: dates + camera
      + game name).
    - **WebM / MOV** containers are handled by *FFmpeg* ``-metadata`` flags
      (exiftool support for these is limited).

    Args:
        source:    Path to the original video file.
        dest:      Path where the tagged copy will be written.
        meta:      Metadata to embed.
        container: File extension **without dot** (``"mp4"``, ``"webm"``,
                   ``"mov"``).  Used to choose the right tool.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    container = container.lower().lstrip(".")

    if container == "mp4":
        return _set_mp4_metadata_exiftool(source, dest, meta)
    elif container in ("webm", "mov"):
        return _set_video_metadata_ffmpeg(source, dest, meta)
    else:
        print(f"Unsupported video container: {container}")
        return False


def set_file_timestamps(path: str, dt: datetime) -> None:
    """Set the file-system access and modification times to *dt*."""
    try:
        timestamp = dt.timestamp()
        os.utime(path, (timestamp, timestamp))
    except Exception as e:
        print(f"Could not update file system timestamp for {Path(path).name}: {e}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _set_mp4_metadata_exiftool(source: str, dest: str, meta: MediaMetadata) -> bool:
    """Embed metadata into an MP4 file using exiftool (single pass)."""
    try:
        shutil.copy2(source, dest)

        exiftool = get_exiftool_path()
        dt_str = meta.creation_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        cmd = [
            exiftool,
            "-overwrite_original",
            f"-CreateDate={dt_str}",
            f"-ModifyDate={dt_str}",
            f"-MediaCreateDate={dt_str}",
            f"-MediaModifyDate={dt_str}",
            f"-Make={meta.device.make}",
            f"-Model={meta.device.model}",
            f"-CameraModelName={meta.device.model}",
        ]

        if meta.game_name:
            cmd.extend(
                [
                    f"-Description={meta.game_name}",
                    f"-Title={meta.game_name}",
                    f"-Comment={meta.game_name}",
                ]
            )

        cmd.append(dest)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return True
        else:
            print(
                f"Error: exiftool failed on {Path(source).name}: {result.stderr.strip()}"
            )
            return False

    except Exception as e:
        print(f"Error: processing MP4 {Path(source).name}: {e}")
        return False


def _set_video_metadata_ffmpeg(source: str, dest: str, meta: MediaMetadata) -> bool:
    """Embed metadata into a WebM/MOV file using FFmpeg ``-metadata`` flags."""
    try:
        ffmpeg_dt = meta.creation_date.isoformat()

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-c",
            "copy",
            "-metadata",
            f"creation_time={ffmpeg_dt}",
            "-metadata",
            f"date={ffmpeg_dt}",
            "-metadata",
            f"make={meta.device.make}",
            "-metadata",
            f"model={meta.device.model}",
            "-metadata",
            f"manufacturer={meta.device.make}",
        ]

        if meta.game_name:
            cmd.extend(
                [
                    "-metadata",
                    f"title={meta.game_name}",
                    "-metadata",
                    f"comment={meta.game_name}",
                    "-metadata",
                    f"description={meta.game_name}",
                ]
            )

        cmd.append(dest)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            return True
        else:
            print(
                f"Error: ffmpeg failed on {Path(source).name}: {result.stderr.strip()}"
            )
            return False

    except Exception as e:
        print(f"Error: processing {Path(source).name}: {e}")
        return False
