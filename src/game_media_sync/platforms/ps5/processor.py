"""PS5 media processor — embed metadata and copy to output folder."""

import re
from datetime import datetime
from pathlib import Path

from ...core import (
    PS5,
    MediaMetadata,
    set_file_timestamps,
    set_image_metadata,
    set_video_metadata,
)

SUPPORTED_EXTENSIONS = {".jpg", ".mp4", ".webm"}
TIMESTAMP_RE = re.compile(r"(?P<ts>\d{14})")


def process_files_in_folder(source_dir: str, output_dir: str):
    source_path = Path(source_dir).resolve()
    output_path = Path(output_dir).resolve()

    for source_file in source_path.rglob("*"):
        if not source_file.is_file():
            continue
        ext = source_file.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        match = TIMESTAMP_RE.search(source_file.stem)
        if not match:
            continue

        dest_file = output_path / source_file.relative_to(source_path)
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            dt = datetime.strptime(match.group("ts"), "%Y%m%d%H%M%S")
            meta = MediaMetadata(creation_date=dt, device=PS5)

            if ext == ".jpg":
                ok = set_image_metadata(str(source_file), str(dest_file), meta)
            else:
                ok = set_video_metadata(
                    str(source_file), str(dest_file), meta, container=ext.lstrip(".")
                )

            if ok:
                set_file_timestamps(str(dest_file), dt)
        except ValueError:
            print(f"Skipping {source_file.name}: invalid date")
        except Exception as e:
            print(f"Error processing {source_file.name}: {e}")
