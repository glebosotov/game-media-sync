#!/usr/bin/env python3
"""
Nintendo Switch 2 Screenshot/Video Upload Script
Uploads screenshots and videos from Nintendo Switch 2 to Immich with proper metadata
"""

import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from ...core.metadata import (
    SWITCH2,
    MediaMetadata,
    set_file_timestamps,
    set_video_metadata,
)
from ...core.upload import upload_file_to_immich


def extract_timestamp_from_filename(filename: str) -> datetime:
    """
    Extract creation date from Nintendo Switch 2 filename.
    Format: YYYYMMDDHHMMSS00_c.jpg or YYYYMMDDHHMMSS00_c.mp4
    Example: 2026010720290900_c.jpg -> January 7, 2026 20:29:09
    """
    try:
        match = re.search(r"(\d{14})", filename)
        if match:
            timestamp_str = match.group(1)
            return datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        else:
            return datetime.fromtimestamp(os.path.getctime(filename))
    except (ValueError, AttributeError):
        return datetime.fromtimestamp(os.path.getctime(filename))


def clean_game_name(folder_name: str) -> str:
    """
    Clean game name from folder name.
    Removes common suffixes like " – Nintendo Switch 2 Edition"
    """
    suffixes = [
        " – Nintendo Switch 2 Edition",
        " - Nintendo Switch 2 Edition",
        " – Nintendo Switch 2",
        " - Nintendo Switch 2",
        " – Switch 2 Edition",
        " - Switch 2 Edition",
    ]

    cleaned = folder_name
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break

    return cleaned.strip()


def process_and_upload_file(file_path: Path, game_name: str, source_dir: Path):
    """
    Process a single file: extract timestamp, update metadata, and upload to Immich.
    """
    filename = file_path.name
    file_ext = file_path.suffix.lower()

    supported_extensions = {".jpg", ".jpeg", ".mp4", ".webm", ".mov"}
    if file_ext not in supported_extensions:
        return False

    creation_date = extract_timestamp_from_filename(filename)

    is_video = file_ext in {".mp4", ".webm", ".mov"}
    media_type = "video" if is_video else "screenshot"

    meta = MediaMetadata(
        creation_date=creation_date,
        device=SWITCH2,
        game_name=game_name,
    )

    # Process video files with metadata embedding
    upload_file_path = str(file_path)
    temp_file_path = None

    if is_video:
        with tempfile.NamedTemporaryFile(
            suffix=file_ext, delete=False, dir=file_path.parent
        ) as temp_file:
            temp_file_path = temp_file.name

        container = file_ext.lstrip(".")
        success = set_video_metadata(
            str(file_path), temp_file_path, meta, container=container
        )

        if success:
            upload_file_path = temp_file_path
            set_file_timestamps(upload_file_path, creation_date)
        else:
            print(f"  Warning: Metadata update failed for {filename}, using original")
            set_file_timestamps(str(file_path), creation_date)
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            temp_file_path = None
    else:
        # For images, just update filesystem timestamps -- EXIF will be
        # handled by upload_file_to_immich via set_image_metadata
        set_file_timestamps(str(file_path), creation_date)

    try:
        api_key = os.getenv("IMMICH_API_KEY")
        server_url = os.getenv("IMMICH_SERVER_URL")

        if not api_key or not server_url:
            print("Error: Immich credentials not configured")
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return False

        upload_file_to_immich(
            filename=upload_file_path,
            api_key=api_key,
            server_url=server_url,
            game_name=game_name,
            is_favorite=False,
            visibility="timeline",
            media_type=media_type,
            device=SWITCH2,
            creation_date=creation_date,
        )

        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        return True

    except Exception as e:
        print(f"  Error: Upload failed for {filename}: {e}")
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
        return False


def process_switch2_folder(source_dir: str):
    """
    Main function to process all files in the Nintendo Switch 2 folder structure.
    Files should be organized in folders by game name.
    """
    source_path = Path(source_dir).resolve()

    if not source_path.is_dir():
        print(f"Error: Source folder does not exist: {source_dir}")
        return

    if not os.getenv("IMMICH_API_KEY") or not os.getenv("IMMICH_SERVER_URL"):
        print("Error: Immich credentials not configured")
        return

    total_files = 0
    successful_uploads = 0
    failed_uploads = 0

    for game_folder in source_path.iterdir():
        if not game_folder.is_dir():
            continue

        if game_folder.name.startswith("."):
            continue

        game_name = clean_game_name(game_folder.name)
        if not game_name:
            game_name = game_folder.name
        print(f"\nProcessing: {game_name}")

        for file_path in game_folder.iterdir():
            if not file_path.is_file():
                continue

            if file_path.name.startswith("."):
                continue

            total_files += 1

            if process_and_upload_file(file_path, game_name, source_path):
                successful_uploads += 1
            else:
                failed_uploads += 1

    print(
        f"\nSwitch: {successful_uploads} uploaded, {failed_uploads} failed out of {total_files}"
    )


if __name__ == "__main__":
    load_dotenv()
    source_folder_path = os.getenv("SWITCH2_SOURCE_PATH", "")

    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print("Usage:")
            print(
                "  python -m scripts.upload_switch              # Use default source path"
            )
            print(
                "  python -m scripts.upload_switch <path>       # Specify custom source path"
            )
            print("  python -m scripts.upload_switch --help       # Show this help")
            print("\nEnvironment variables:")
            print("  SWITCH2_SOURCE_PATH  Source folder path (optional)")
            print("  IMMICH_API_KEY       Immich API key (required)")
            print("  IMMICH_SERVER_URL    Immich server URL (required)")
            sys.exit(0)
        else:
            source_folder_path = sys.argv[1]

    if not source_folder_path:
        print("Error: Set SWITCH2_SOURCE_PATH or pass the source path as argument.")
        sys.exit(1)

    process_switch2_folder(source_folder_path)
