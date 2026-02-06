#!/usr/bin/env python3
"""Entry point for Steam screenshot and clip uploads"""

import sys

from dotenv import load_dotenv

from game_media_sync.platforms.steam.uploader import main

if __name__ == "__main__":
    load_dotenv()
    sys.exit(main() or 0)
