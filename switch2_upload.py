#!/usr/bin/env python3
"""
Nintendo Switch 2 Screenshot/Video Upload Script
Uploads screenshots and videos from Nintendo Switch 2 to Immich with proper metadata
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not available. Install with: pip install python-dotenv")
    print("   Environment variables must be set manually.")

from immich_upload import upload_file_to_immich

# --- CONFIGURATION ---
# Set the path to the folder containing your Nintendo Switch 2 files
# Files should be organized in folders by game name
source_folder_path = os.getenv(
    "SWITCH2_SOURCE_PATH", "/Users/glebosotov/Desktop/Switch"
)
# ---------------------


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


def get_exiftool_path():
    """Get the exiftool executable path from EXIFTOOL_PATH environment variable."""
    exiftool_dir = os.getenv("EXIFTOOL_PATH")
    if not exiftool_dir:
        return "exiftool"

    possible_names = ["exiftool", "exiftool.exe"]
    for name in possible_names:
        exiftool_path = os.path.join(exiftool_dir, name)
        if os.path.exists(exiftool_path) and os.access(exiftool_path, os.X_OK):
            return exiftool_path

    return "exiftool"


def update_file_metadata(file_path: str, creation_date: datetime, game_name: str):
    """
    Update file system timestamps to match the creation date.
    This ensures Immich reads the correct date from file metadata.
    """
    try:
        timestamp = creation_date.timestamp()
        os.utime(file_path, (timestamp, timestamp))
    except Exception as e:
        print(
            f"⚠️  Could not update file system timestamp for {Path(file_path).name}: {e}"
        )


def update_mp4_metadata(
    source_path: str, dest_path: str, dt_object: datetime, game_name: str
):
    """Copies an MP4 and updates metadata using exiftool."""
    try:
        shutil.copy2(source_path, dest_path)

        exiftool_path = get_exiftool_path()

        dt_str = dt_object.strftime("%Y-%m-%dT%H:%M:%SZ")

        cmd = [
            exiftool_path,
            "-overwrite_original",
            f"-CreateDate={dt_str}",
            f"-ModifyDate={dt_str}",
            f"-MediaCreateDate={dt_str}",
            f"-MediaModifyDate={dt_str}",
            "-Make=Nintendo",
            "-Model=Nintendo Switch 2",
            "-CameraModelName=Nintendo Switch 2",
        ]

        if game_name:
            cmd.extend(
                [
                    f"-Description={game_name}",
                    f"-Title={game_name}",
                    f"-Comment={game_name}",
                ]
            )

        cmd.append(dest_path)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print(f"   ✅ Processed MP4 metadata: {Path(dest_path).name}")
            return True
        else:
            print(
                f"   ⚠️  Error processing MP4 {Path(source_path).name}: {result.stderr}"
            )
            return False

    except Exception as e:
        print(f"   ⚠️  Error processing MP4 {Path(source_path).name}: {e}")
        return False


def update_webm_metadata(
    source_path: str, dest_path: str, dt_object: datetime, game_name: str
):
    """Uses FFmpeg to copy a WebM file and add metadata in one pass."""
    try:
        ffmpeg_dt_str = dt_object.isoformat()

        cmd_ffmpeg = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i",
            source_path,
            "-c",
            "copy",
            "-metadata",
            f"creation_time={ffmpeg_dt_str}",
            "-metadata",
            f"date={ffmpeg_dt_str}",
            "-metadata",
            "make=Nintendo",
            "-metadata",
            "model=Nintendo Switch 2",
            "-metadata",
            "manufacturer=Nintendo",
        ]

        if game_name:
            cmd_ffmpeg.extend(
                [
                    "-metadata",
                    f"title={game_name}",
                    "-metadata",
                    f"comment={game_name}",
                    "-metadata",
                    f"description={game_name}",
                ]
            )

        cmd_ffmpeg.append(dest_path)

        result = subprocess.run(
            cmd_ffmpeg,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            print(f"   ✅ Processed WebM metadata: {Path(dest_path).name}")
            return True
        else:
            print(
                f"   ⚠️  Error processing WebM {Path(source_path).name}: {result.stderr}"
            )
            return False
    except Exception as e:
        print(f"   ⚠️  Error processing WebM {Path(source_path).name}: {e}")
        return False


def update_mov_metadata(
    source_path: str, dest_path: str, dt_object: datetime, game_name: str
):
    """Uses FFmpeg to copy a MOV file and add metadata in one pass."""
    try:
        ffmpeg_dt_str = dt_object.isoformat()

        cmd_ffmpeg = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i",
            source_path,
            "-c",
            "copy",
            "-metadata",
            f"creation_time={ffmpeg_dt_str}",
            "-metadata",
            f"date={ffmpeg_dt_str}",
            "-metadata",
            "make=Nintendo",
            "-metadata",
            "model=Nintendo Switch 2",
            "-metadata",
            "manufacturer=Nintendo",
        ]

        if game_name:
            cmd_ffmpeg.extend(
                [
                    "-metadata",
                    f"title={game_name}",
                    "-metadata",
                    f"comment={game_name}",
                    "-metadata",
                    f"description={game_name}",
                ]
            )

        cmd_ffmpeg.append(dest_path)

        result = subprocess.run(
            cmd_ffmpeg,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            print(f"   ✅ Processed MOV metadata: {Path(dest_path).name}")
            return True
        else:
            print(
                f"   ⚠️  Error processing MOV {Path(source_path).name}: {result.stderr}"
            )
            return False
    except Exception as e:
        print(f"   ⚠️  Error processing MOV {Path(source_path).name}: {e}")
        return False


def process_and_upload_file(file_path: Path, game_name: str, source_dir: Path):
    """
    Process a single file: extract timestamp, update metadata, and upload to Immich.
    """
    filename = file_path.name
    file_ext = file_path.suffix.lower()

    supported_extensions = {".jpg", ".jpeg", ".mp4", ".webm", ".mov"}
    if file_ext not in supported_extensions:
        print(f"⚠️  Skipping unsupported file type: {filename}")
        return False

    creation_date = extract_timestamp_from_filename(filename)

    print(f"\n📸 Processing: {filename}")
    print(f"   Game: {game_name}")
    print(f"   Date: {creation_date.strftime('%Y-%m-%d %H:%M:%S')}")

    is_video = file_ext in {".mp4", ".webm", ".mov"}
    media_type = "video" if is_video else "screenshot"

    # Process video files with metadata embedding (like PS5 script)
    upload_file_path = str(file_path)
    temp_file_path = None

    if is_video:
        with tempfile.NamedTemporaryFile(
            suffix=file_ext, delete=False, dir=file_path.parent
        ) as temp_file:
            temp_file_path = temp_file.name

        success = False
        if file_ext == ".mp4":
            success = update_mp4_metadata(
                str(file_path), temp_file_path, creation_date, game_name
            )
        elif file_ext == ".webm":
            success = update_webm_metadata(
                str(file_path), temp_file_path, creation_date, game_name
            )
        elif file_ext == ".mov":
            success = update_mov_metadata(
                str(file_path), temp_file_path, creation_date, game_name
            )

        if success:
            upload_file_path = temp_file_path
            update_file_metadata(upload_file_path, creation_date, game_name)
        else:
            print("   ⚠️  Metadata update failed, using original file")
            update_file_metadata(str(file_path), creation_date, game_name)
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            temp_file_path = None
    else:
        update_file_metadata(str(file_path), creation_date, game_name)

    try:
        api_key = os.getenv("IMMICH_API_KEY")
        server_url = os.getenv("IMMICH_SERVER_URL")

        if not api_key or not server_url:
            print("❌ Immich credentials not configured!")
            print(
                "Please set IMMICH_API_KEY and IMMICH_SERVER_URL environment variables"
            )
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
            make="Nintendo",
            model="Nintendo Switch 2",
            creation_date=creation_date,  # Pass the extracted date
        )

        print("   ✅ Upload successful")

        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        return True

    except Exception as e:
        print(f"   ❌ Upload failed: {e}")
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
        print(f"❌ Error: The source folder does not exist: {source_dir}")
        return

    print("Nintendo Switch 2 Screenshot/Video Upload Script")
    print("=" * 50)
    print(f"Scanning source folder: {source_path}")

    if not os.getenv("IMMICH_API_KEY") or not os.getenv("IMMICH_SERVER_URL"):
        print("❌ Immich credentials not configured!")
        print("Please set IMMICH_API_KEY and IMMICH_SERVER_URL environment variables")
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
            game_name = game_folder.name  # Fallback to original folder name
        print(f"\n🎮 Processing game folder: {game_name}")
        print("-" * 50)

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

    print("\n" + "=" * 50)
    print("Upload Summary:")
    print(f"📊 Total files processed: {total_files}")
    print(f"✅ Successful uploads: {successful_uploads}")
    print(f"❌ Failed uploads: {failed_uploads}")
    print("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print("Nintendo Switch 2 Screenshot/Video Upload Script")
            print("Usage:")
            print("  python switch2_upload.py              # Use default source path")
            print(
                "  python switch2_upload.py <path>       # Specify custom source path"
            )
            print("  python switch2_upload.py --help      # Show this help")
            print("\nEnvironment variables:")
            print("  SWITCH2_SOURCE_PATH - Source folder path (optional)")
            print("  IMMICH_API_KEY - Immich API key (required)")
            print("  IMMICH_SERVER_URL - Immich server URL (required)")
            sys.exit(0)
        else:
            source_folder_path = sys.argv[1]

    process_switch2_folder(source_folder_path)
    print("\n✅ Processing complete.")
