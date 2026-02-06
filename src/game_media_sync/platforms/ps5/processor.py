import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# --- CONFIGURATION ---
# Use PS5_SOURCE_PATH and PS5_OUTPUT_PATH environment variables, or pass when calling process_files_in_folder.
source_folder_path = os.getenv("PS5_SOURCE_PATH", "")
output_folder_path = os.getenv("PS5_OUTPUT_PATH", "")
# ---------------------


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


def update_jpg_metadata(source_path, dest_path, dt_object):
    """Copies a JPG and updates EXIF metadata using exiftool."""
    try:
        shutil.copy2(source_path, dest_path)

        exiftool_path = get_exiftool_path()

        exif_dt_str = dt_object.strftime("%Y:%m:%d %H:%M:%S")

        cmd = [
            exiftool_path,
            "-overwrite_original",
            f"-DateTime={exif_dt_str}",
            f"-DateTimeOriginal={exif_dt_str}",
            f"-DateTimeDigitized={exif_dt_str}",
            "-Make=Sony Interactive Entertainment",
            "-Model=PlayStation 5",
            dest_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print(f"Processed JPG: {Path(dest_path).name}")
            return True
        else:
            print(f"Error processing JPG {Path(source_path).name}: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error processing JPG {Path(source_path).name}: {e}")
        return False


def update_mp4_metadata(source_path, dest_path, dt_object):
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
            "-Make=Sony Interactive Entertainment",
            "-Model=PlayStation 5",
            "-CameraModelName=PlayStation 5",
            dest_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print(f"Processed MP4: {Path(dest_path).name}")
            return True
        else:
            print(f"Error processing MP4 {Path(source_path).name}: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error processing MP4 {Path(source_path).name}: {e}")
        return False


def update_webm_metadata(source_path, dest_path, dt_object):
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
            "make=Sony Interactive Entertainment",
            "-metadata",
            "model=PlayStation 5",
            "-metadata",
            "manufacturer=Sony Interactive Entertainment",
            dest_path,
        ]

        result = subprocess.run(
            cmd_ffmpeg,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            print(f"Processed WebM: {Path(dest_path).name}")
            return True
        else:
            print(f"Error processing WebM {Path(source_path).name}: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error processing WebM {Path(source_path).name}: {e}")
        return False


def update_file_system_timestamp(file_path, dt_object):
    """Updates the file system's 'created' and 'modified' times for the new file."""
    try:
        timestamp = dt_object.timestamp()
        os.utime(file_path, (timestamp, timestamp))
    except Exception as e:
        print(f"Could not update file system timestamp for {Path(file_path).name}: {e}")


def process_files_in_folder(source_dir, output_dir):
    """Main function to process all files and save them to the output directory."""
    timestamp_pattern = re.compile(r"(?P<timestamp>\d{14})")

    supported_extensions = {".jpg", ".mp4", ".webm"}

    source_path = Path(source_dir).resolve()
    output_path = Path(output_dir).resolve()

    print(f"Scanning source folder: {source_path}")
    print(f"Output will be saved to: {output_path}")

    for source_file in source_path.rglob("*"):
        if not source_file.is_file():
            continue

        if source_file.suffix.lower() not in supported_extensions:
            continue

        match = timestamp_pattern.search(source_file.stem)
        if match:
            timestamp_str = match.group("timestamp")

            relative_path = source_file.relative_to(source_path)
            dest_file = output_path / relative_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                dt_object = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                success = False
                ext = source_file.suffix.lower()

                if ext == ".jpg":
                    success = update_jpg_metadata(
                        str(source_file), str(dest_file), dt_object
                    )
                elif ext == ".mp4":
                    success = update_mp4_metadata(
                        str(source_file), str(dest_file), dt_object
                    )
                elif ext == ".webm":
                    success = update_webm_metadata(
                        str(source_file), str(dest_file), dt_object
                    )

                if success:
                    update_file_system_timestamp(str(dest_file), dt_object)

            except ValueError:
                print(f"Skipping {source_file.name}: Invalid date format.")
            except Exception as e:
                print(f"An unexpected error occurred with {source_file.name}: {e}")


if __name__ == "__main__":
    source_path = Path(source_folder_path)
    if not source_path.is_dir():
        print(f"Error: The source folder does not exist: {source_folder_path}")
    else:
        process_files_in_folder(source_folder_path, output_folder_path)
        print("\nProcessing complete.")
