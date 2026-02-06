"""Nintendo Switch 2 media processor and uploader."""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from ...core import (
    SWITCH2,
    MediaMetadata,
    get_immich_config,
    set_file_timestamps,
    set_image_metadata,
    set_video_metadata,
    upload_to_immich,
)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".mp4", ".webm", ".mov"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}

SWITCH_SUFFIXES = [
    " – Nintendo Switch 2 Edition",
    " - Nintendo Switch 2 Edition",
    " – Nintendo Switch 2",
    " - Nintendo Switch 2",
    " – Switch 2 Edition",
    " - Switch 2 Edition",
]


def extract_timestamp(filename: str) -> datetime:
    match = re.search(r"(\d{14})", filename)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    return datetime.fromtimestamp(os.path.getctime(filename))


def clean_game_name(folder_name: str) -> str:
    name = folder_name
    for suffix in SWITCH_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip()


def _process_file(file_path: Path, dest_path: Path, game_name: str) -> bool:
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False

    creation_date = extract_timestamp(file_path.name)
    meta = MediaMetadata(
        creation_date=creation_date, device=SWITCH2, game_name=game_name
    )

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if ext in VIDEO_EXTENSIONS:
        ok = set_video_metadata(
            str(file_path), str(dest_path), meta, container=ext.lstrip(".")
        )
    else:
        ok = set_image_metadata(str(file_path), str(dest_path), meta)

    if ok:
        set_file_timestamps(str(dest_path), creation_date)
    else:
        shutil.copy2(str(file_path), str(dest_path))
        set_file_timestamps(str(dest_path), creation_date)

    return True


def process_switch2_folder(source_dir: str, output_dir: str, *, upload: bool = True):
    source_path = Path(source_dir).resolve()
    output_path = Path(output_dir).resolve()

    if not source_path.is_dir():
        print(f"Source folder not found: {source_dir}")
        return

    cfg = get_immich_config() if upload else None

    ok = fail = total = 0
    for game_folder in source_path.iterdir():
        if not game_folder.is_dir() or game_folder.name.startswith("."):
            continue

        game_name = clean_game_name(game_folder.name) or game_folder.name

        for file_path in game_folder.iterdir():
            if not file_path.is_file() or file_path.name.startswith("."):
                continue
            total += 1

            dest_path = output_path / game_name / file_path.name
            try:
                if _process_file(file_path, dest_path, game_name):
                    if upload and cfg:
                        creation_date = extract_timestamp(file_path.name)
                        upload_to_immich(
                            str(dest_path),
                            cfg.api_key,
                            cfg.server_url,
                            device=SWITCH2,
                            creation_date=creation_date,
                        )
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"  Failed {file_path.name}: {e}")
                fail += 1

    print(f"Switch: {ok} processed, {fail} failed / {total}")
