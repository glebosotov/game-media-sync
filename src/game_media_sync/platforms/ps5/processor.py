"""PS5 media processor — embed metadata, copy to output, optionally upload."""

import re
from datetime import datetime
from pathlib import Path

from ...core import (
    PS5,
    MediaMetadata,
    get_immich_config,
    set_file_timestamps,
    set_image_metadata,
    set_video_metadata,
    upload_to_immich,
)

SUPPORTED_EXTENSIONS = {".jpg", ".mp4", ".webm"}
TIMESTAMP_RE = re.compile(r"(?P<ts>\d{14})")


def process_files_in_folder(source_dir: str, output_dir: str, *, upload: bool = True):
    source_path = Path(source_dir).resolve()
    output_path = Path(output_dir).resolve()
    cfg = get_immich_config() if upload else None

    ok = fail = total = 0
    for source_file in source_path.rglob("*"):
        if not source_file.is_file():
            continue
        ext = source_file.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        match = TIMESTAMP_RE.search(source_file.stem)
        if not match:
            continue

        total += 1
        dest_file = output_path / source_file.relative_to(source_path)
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            dt = datetime.strptime(match.group("ts"), "%Y%m%d%H%M%S")
            meta = MediaMetadata(creation_date=dt, device=PS5)

            if ext == ".jpg":
                ok_meta = set_image_metadata(str(source_file), str(dest_file), meta)
            else:
                ok_meta = set_video_metadata(
                    str(source_file),
                    str(dest_file),
                    meta,
                    container=ext.lstrip("."),
                )

            if ok_meta:
                set_file_timestamps(str(dest_file), dt)
                if upload and cfg:
                    upload_to_immich(
                        str(dest_file),
                        cfg.api_key,
                        cfg.server_url,
                        device=PS5,
                        creation_date=dt,
                    )
                ok += 1
            else:
                fail += 1
        except ValueError:
            print(f"Skipping {source_file.name}: invalid date")
            fail += 1
        except Exception as e:
            print(f"Error {source_file.name}: {e}")
            fail += 1

    print(f"PS5: {ok} processed, {fail} failed / {total}")
