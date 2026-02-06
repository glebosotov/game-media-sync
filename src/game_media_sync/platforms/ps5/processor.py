import os
import re
from datetime import datetime
from pathlib import Path

from ...core.metadata import (
    PS5,
    MediaMetadata,
    set_file_timestamps,
    set_image_metadata,
    set_video_metadata,
)

source_folder_path = os.getenv("PS5_SOURCE_PATH", "")
output_folder_path = os.getenv("PS5_OUTPUT_PATH", "")


def process_files_in_folder(source_dir, output_dir):
    """Main function to process all files and save them to the output directory."""
    timestamp_pattern = re.compile(r"(?P<timestamp>\d{14})")

    supported_extensions = {".jpg", ".mp4", ".webm"}

    source_path = Path(source_dir).resolve()
    output_path = Path(output_dir).resolve()

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
                meta = MediaMetadata(
                    creation_date=dt_object,
                    device=PS5,
                )

                success = False
                ext = source_file.suffix.lower()

                if ext == ".jpg":
                    success = set_image_metadata(str(source_file), str(dest_file), meta)
                elif ext == ".mp4":
                    success = set_video_metadata(
                        str(source_file), str(dest_file), meta, container="mp4"
                    )
                elif ext == ".webm":
                    success = set_video_metadata(
                        str(source_file), str(dest_file), meta, container="webm"
                    )

                if success:
                    set_file_timestamps(str(dest_file), dt_object)

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
