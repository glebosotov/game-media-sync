"""Unified CLI entry point for game-media-sync."""

import argparse
import sys

from dotenv import load_dotenv


def cmd_steam(args):
    from .platforms.steam.uploader import main as steam_main

    steam_main()


def cmd_steam_clips(args):
    from .platforms.steam.clips import main as clips_main

    clips_main()


def cmd_ps5(args):
    from .core import require_env
    from .platforms.ps5.processor import process_files_in_folder

    source = args.source or require_env("PS5_SOURCE_PATH")
    output = args.output or require_env("PS5_OUTPUT_PATH")
    process_files_in_folder(source, output)


def cmd_switch(args):
    from .core import require_env
    from .platforms.switch.uploader import process_switch2_folder

    source = args.source or require_env("SWITCH2_SOURCE_PATH")
    process_switch2_folder(source)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="gms", description="Sync gaming media to Immich"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("steam", help="Upload Steam screenshots")

    sub.add_parser("steam-clips", help="Upload Steam game clips")

    ps5 = sub.add_parser("ps5", help="Process PS5 media (embed metadata)")
    ps5.add_argument("--source", help="Source folder (or PS5_SOURCE_PATH env)")
    ps5.add_argument("--output", help="Output folder (or PS5_OUTPUT_PATH env)")

    sw = sub.add_parser("switch", help="Upload Nintendo Switch 2 media")
    sw.add_argument(
        "source", nargs="?", help="Source folder (or SWITCH2_SOURCE_PATH env)"
    )

    args = parser.parse_args()

    handlers = {
        "steam": cmd_steam,
        "steam-clips": cmd_steam_clips,
        "ps5": cmd_ps5,
        "switch": cmd_switch,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
