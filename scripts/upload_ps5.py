#!/usr/bin/env python3
"""Entry point for PS5 media processing"""

import sys

from dotenv import load_dotenv

from game_media_sync.platforms.ps5.processor import process_files_in_folder

if __name__ == "__main__":
    import os
    from pathlib import Path

    load_dotenv()

    source_folder_path = os.getenv("PS5_SOURCE_PATH", "")
    output_folder_path = os.getenv("PS5_OUTPUT_PATH", "")

    if not source_folder_path or not output_folder_path:
        print("Error: Set PS5_SOURCE_PATH and PS5_OUTPUT_PATH environment variables.")
        sys.exit(1)

    source_path = Path(source_folder_path)
    if not source_path.is_dir():
        print(f"Error: The source folder does not exist: {source_folder_path}")
        sys.exit(1)
    process_files_in_folder(source_folder_path, output_folder_path)
    print("\nProcessing complete.")
