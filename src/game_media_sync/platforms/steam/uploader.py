"""Steam screenshot uploader."""

import os
import sys
from datetime import datetime

from ...core import (
    STEAM_DECK,
    MediaMetadata,
    UploadTracker,
    get_immich_config,
    set_file_timestamps,
    set_image_metadata,
    temp_upload_file,
    upload_to_immich,
)
from ...resolvers.game_name import get_game_name
import vdf
from .utils import GetAccountId, steamdir

TRACKING_FILE = "upload_tracker.json"


def get_all_screenshots():
    try:
        user = GetAccountId()
        vdf_path = f"{steamdir}userdata/{user}/760/screenshots.vdf"
        if not os.path.exists(vdf_path):
            return []

        with open(vdf_path, "r") as f:
            d = vdf.parse(f)

        screenshots = d.get("screenshots") or d.get("Screenshots")
        if not screenshots:
            return []

        result = []
        for game in screenshots:
            for sid in screenshots[game]:
                s = screenshots[game][sid]
                if "creation" in s and "filename" in s:
                    result.append(
                        {
                            "game_id": int(game),
                            "creation_time": int(s["creation"]),
                            "filename": s["filename"],
                            "full_path": f"{steamdir}userdata/{user}/760/remote/{s['filename']}",
                        }
                    )

        result.sort(key=lambda x: x["creation_time"])
        return result
    except Exception as e:
        print(f"Error reading screenshots: {e}")
        return []


def upload_screenshot(filepath: str, game_name: str | None, cfg) -> bool:
    """Embed image metadata and upload to Immich."""
    import tempfile

    creation_date = datetime.fromtimestamp(os.path.getmtime(filepath))
    meta = MediaMetadata(
        creation_date=creation_date, device=STEAM_DECK, game_name=game_name
    )

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    with temp_upload_file(tmp_path, filepath) as upload_path:
        if not set_image_metadata(filepath, tmp_path, meta):
            upload_path = filepath  # noqa: F841 — fall back to original

        set_file_timestamps(upload_path, creation_date)
        upload_to_immich(
            upload_path,
            cfg.api_key,
            cfg.server_url,
            device=STEAM_DECK,
            creation_date=creation_date,
        )
    return True


def main():
    upload_clips = "--clips" in sys.argv or "-c" in sys.argv
    upload_screenshots = (
        "--screenshots" in sys.argv or "-s" in sys.argv or not upload_clips
    )

    if upload_clips and not upload_screenshots:
        from .clips import main as clips_main

        clips_main()
        return

    cfg = get_immich_config()
    tracker = UploadTracker(TRACKING_FILE)
    all_screenshots = get_all_screenshots()
    if not all_screenshots:
        return

    new = [s for s in all_screenshots if tracker.is_new(s["creation_time"])]
    if not new:
        return

    ok = 0
    fail = 0
    for s in new:
        if not os.path.exists(s["full_path"]):
            fail += 1
            continue

        game_name = get_game_name(s["game_id"])
        try:
            upload_screenshot(s["full_path"], game_name, cfg)
            ok += 1
            tracker.record(
                {
                    "filename": s["filename"],
                    "upload_time": datetime.now().isoformat(),
                    "creation_time": s["creation_time"],
                }
            )
        except Exception as e:
            print(f"  Failed {s['filename']}: {e}")
            fail += 1

    if ok:
        tracker.update_time(max(s["creation_time"] for s in new))
        tracker.save()

    print(f"Screenshots: {ok} uploaded, {fail} failed / {len(new)}")
