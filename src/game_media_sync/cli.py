"""Unified CLI entry point for game-media-sync."""

import argparse
import sys

from dotenv import load_dotenv


def cmd_steam(args):
    from .platforms.steam.uploader import main as steam_main

    steam_main(output_dir=args.output, upload=not args.no_upload)


def cmd_steam_clips(args):
    from .platforms.steam.clips import main as clips_main

    clips_main(output_dir=args.output, upload=not args.no_upload)


def cmd_ps5(args):
    from .platforms.ps5.processor import process_files_in_folder

    process_files_in_folder(args.source, args.output, upload=not args.no_upload)


def cmd_switch(args):
    from .platforms.switch.uploader import process_switch2_folder

    process_switch2_folder(args.source, args.output, upload=not args.no_upload)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="gms", description="Sync gaming media to Immich"
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--no-upload", action="store_true", help="Skip Immich upload")

    sub = parser.add_subparsers(dest="command", required=True)

    steam = sub.add_parser("steam", parents=[common], help="Upload Steam screenshots")
    steam.add_argument("--output", help="Save processed files to this folder")

    sc = sub.add_parser("steam-clips", parents=[common], help="Upload Steam game clips")
    sc.add_argument("--output", help="Save processed files to this folder")

    ps5 = sub.add_parser("ps5", parents=[common], help="Process and upload PS5 media")
    ps5.add_argument("--source", required=True, help="Source folder")
    ps5.add_argument("--output", required=True, help="Output folder")

    sw = sub.add_parser(
        "switch", parents=[common], help="Process and upload Switch 2 media"
    )
    sw.add_argument("--source", required=True, help="Source folder")
    sw.add_argument("--output", required=True, help="Output folder")

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
