#!/usr/bin/env python3
"""Entry point for Steam screenshot and clip uploads"""

import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from game_media_sync.platforms.steam.uploader import main

if __name__ == "__main__":
    sys.exit(main() or 0)
