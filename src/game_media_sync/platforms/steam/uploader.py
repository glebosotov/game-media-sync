#!/usr/bin/env python3
"""
Steam Screenshot Upload Script
Uploads all screenshots made since the last successful upload to Immich
"""

import json
import os
import sys
from datetime import datetime

from ...core.upload import upload_screenshot
from ...resolvers.game_name import get_game_name
from ...utils import vdf
from .utils import GetAccountId, steamdir

from dotenv import load_dotenv

load_dotenv()

# Configuration
TRACKING_FILE = "upload_tracker.json"
STEAMDIR = steamdir


def load_upload_tracker():
    """Load the tracking file to see which screenshots have been uploaded"""
    if os.path.exists(TRACKING_FILE):
        try:
            with open(TRACKING_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {"last_upload_time": 0, "uploaded_screenshots": []}


def save_upload_tracker(tracker_data):
    """Save the tracking data to file"""
    with open(TRACKING_FILE, "w") as f:
        json.dump(tracker_data, f, indent=2)


def get_all_screenshots():
    """Get all screenshots from Steam's screenshots.vdf file"""
    try:
        user = GetAccountId()
        vdf_path = f"{STEAMDIR}userdata/{user & 0xFFFFFFFF}/760/screenshots.vdf"

        if not os.path.exists(vdf_path):
            print(f"Screenshots file not found: {vdf_path}")
            return []

        with open(vdf_path, "r") as f:
            d = vdf.parse(f)

        if "screenshots" in d:
            screenshots = d["screenshots"]
        elif "Screenshots" in d:
            screenshots = d["Screenshots"]
        else:
            print("No screenshots found in VDF file")
            return []

        all_screenshots = []
        for game in screenshots:
            for screenshot_id in screenshots[game]:
                screenshot_data = screenshots[game][screenshot_id]
                if "creation" in screenshot_data and "filename" in screenshot_data:
                    all_screenshots.append(
                        {
                            "game_id": int(game),
                            "screenshot_id": int(screenshot_id),
                            "creation_time": int(screenshot_data["creation"]),
                            "filename": screenshot_data["filename"],
                            "full_path": f"{STEAMDIR}userdata/{user & 0xFFFFFFFF}/760/remote/{screenshot_data['filename']}",
                        }
                    )

        all_screenshots.sort(key=lambda x: x["creation_time"])
        return all_screenshots

    except Exception as e:
        print(f"Error reading screenshots: {e}")
        return []


def get_new_screenshots(screenshots, last_upload_time):
    """Filter screenshots to only include new ones since last upload"""
    return [s for s in screenshots if s["creation_time"] > last_upload_time]


def main():
    """Main function to upload new screenshots and clips"""
    upload_clips = "--clips" in sys.argv or "-c" in sys.argv
    upload_screenshots = (
        "--screenshots" in sys.argv or "-s" in sys.argv or not upload_clips
    )

    if upload_clips and not upload_screenshots:
        from .clips import main as upload_clips_main

        upload_clips_main()
        return

    if not os.getenv("IMMICH_API_KEY") or not os.getenv("IMMICH_SERVER_URL"):
        print("Error: Immich credentials not configured")
        return

    tracker = load_upload_tracker()
    last_upload_time = tracker.get("last_upload_time", 0)
    uploaded_screenshots = tracker.get("uploaded_screenshots", [])

    all_screenshots = get_all_screenshots()

    if not all_screenshots:
        print("No screenshots found")
        return

    new_screenshots = get_new_screenshots(all_screenshots, last_upload_time)

    if not new_screenshots:
        print("No new screenshots to upload")
        return

    print(f"Processing {len(new_screenshots)} new screenshot(s)...")

    successful_uploads = 0
    failed_uploads = 0

    for screenshot in new_screenshots:
        if not os.path.exists(screenshot["full_path"]):
            print(f"  File not found: {screenshot['full_path']}")
            failed_uploads += 1
            continue

        game_name = get_game_name(screenshot["game_id"])

        if upload_screenshot(screenshot["full_path"], game_name):
            successful_uploads += 1
            uploaded_screenshots.append(
                {
                    "filename": screenshot["filename"],
                    "upload_time": datetime.now().isoformat(),
                    "creation_time": screenshot["creation_time"],
                }
            )
        else:
            print(f"  Failed: {screenshot['filename']}")
            failed_uploads += 1

    if successful_uploads > 0:
        latest_upload_time = max(s["creation_time"] for s in new_screenshots)
        tracker["last_upload_time"] = latest_upload_time
        tracker["uploaded_screenshots"] = uploaded_screenshots
        save_upload_tracker(tracker)

    print(
        f"Screenshots: {successful_uploads} uploaded, {failed_uploads} failed out of {len(new_screenshots)}"
    )


if __name__ == "__main__":
    load_dotenv()

    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        print("Usage:")
        print("  python -m scripts.upload_steam           # Upload screenshots only")
        print("  python -m scripts.upload_steam --clips   # Upload clips only")
        print("  python -m scripts.upload_steam --both    # Upload both")
        print("  python -m scripts.upload_steam --help    # Show this help")
        sys.exit(0)

    if "--both" in sys.argv:
        main()

        from .clips import main as upload_clips_main

        upload_clips_main()
    else:
        main()
