#!/usr/bin/env python3
"""Entry point for Nintendo Switch 2 media uploads"""

import os
import sys

from dotenv import load_dotenv

from game_media_sync.platforms.switch.uploader import process_switch2_folder

if __name__ == "__main__":
    load_dotenv()
    source_folder_path = os.getenv("SWITCH2_SOURCE_PATH") or ""

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
    print("\nProcessing complete.")
