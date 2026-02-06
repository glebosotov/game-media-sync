#!/usr/bin/env python3
"""
Game Clips Uploader
Handles discovery, conversion, and upload of Steam game clips to Immich.

Process:
1. Scan gamerecordings/clips/ for clip_{gameid}_{date}_{time} directories
2. Find session.mpd files in video subdirectories
3. Convert to MP4 using FFmpeg (raw, no metadata)
4. Embed metadata in a single pass via core.metadata
5. Upload to Immich with game info
"""

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

from ...core.metadata import (
    STEAM_DECK,
    MediaMetadata,
    set_file_timestamps,
    set_video_metadata,
)
from ...core.upload import upload_video
from .utils import GetAccountId, steamdir


def get_clips_directory() -> Optional[str]:
    """Get the Steam clips directory path."""
    try:
        user = GetAccountId()
        clips_dir = f"{steamdir}userdata/{user & 0xFFFFFFFF}/gamerecordings/clips"
        if os.path.exists(clips_dir):
            return clips_dir
    except Exception:
        pass
    return None


def discover_clips() -> List[Dict]:
    """Discover all game clips in the Steam clips directory.

    Returns list of clip info dictionaries with:
    - clip_path: path to clip directory
    - game_id: extracted from directory name
    - creation_time: parsed from directory name
    - session_mpd: path to session.mpd file
    - thumbnail: path to thumbnail.jpg
    """
    clips_dir = get_clips_directory()
    if not clips_dir:
        return []

    clips = []

    # Pattern: clip_{gameid}_{date}_{time}
    clip_pattern = re.compile(r"^clip_(\d+)_(\d{8})_(\d{6})$")

    try:
        for item in os.listdir(clips_dir):
            item_path = os.path.join(clips_dir, item)
            if not os.path.isdir(item_path):
                continue

            match = clip_pattern.match(item)
            if not match:
                continue

            game_id, date_str, time_str = match.groups()
            game_id = int(game_id)

            # Parse creation time
            try:
                # Format: YYYYMMDD_HHMMSS
                creation_time = datetime.strptime(
                    f"{date_str}_{time_str}", "%Y%m%d_%H%M%S"
                ).timestamp()
            except ValueError:
                # Fallback to directory modification time
                creation_time = os.path.getmtime(item_path)

            # Look for session.mpd in video subdirectories
            session_mpd = None
            video_dir = os.path.join(item_path, "video")
            if os.path.exists(video_dir):
                for subdir in os.listdir(video_dir):
                    subdir_path = os.path.join(video_dir, subdir)
                    if os.path.isdir(subdir_path):
                        mpd_path = os.path.join(subdir_path, "session.mpd")
                        if os.path.exists(mpd_path):
                            session_mpd = mpd_path
                            break

            # Look for thumbnail
            thumbnail = os.path.join(item_path, "thumbnail.jpg")
            if not os.path.exists(thumbnail):
                thumbnail = None

            clips.append(
                {
                    "clip_path": item_path,
                    "game_id": game_id,
                    "creation_time": int(creation_time),
                    "session_mpd": session_mpd,
                    "thumbnail": thumbnail,
                    "clip_name": item,
                }
            )

    except Exception as e:
        print(f"Error discovering clips: {e}")

    # Sort by creation time (oldest first)
    clips.sort(key=lambda x: x["creation_time"])
    return clips


def convert_clip_to_mp4(
    session_mpd_path: str,
    output_path: str,
) -> bool:
    """Convert session.mpd to a raw MP4 by combining DASH video and audio chunks.

    This performs *only* the container conversion.  No metadata is embedded here;
    that is handled separately by :func:`set_video_metadata`.

    Based on the approach from:
    https://gist.github.com/safijari/afa41cb017eb2d0cadb20bf9fcfecc93

    Args:
        session_mpd_path: Path to session.mpd file
        output_path: Path for output MP4 file

    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # Get the directory containing the MPD file and chunks
        mpd_dir = os.path.dirname(session_mpd_path)

        all_files = os.listdir(mpd_dir)

        video_init = None
        audio_init = None
        video_chunk_files = []
        audio_chunk_files = []

        for file in all_files:
            if file.startswith("init-stream0.m4s"):
                video_init = os.path.join(mpd_dir, file)
            elif file.startswith("init-stream1.m4s"):
                audio_init = os.path.join(mpd_dir, file)
            elif file.startswith("chunk-stream0-") and file.endswith(".m4s"):
                video_chunk_files.append(os.path.join(mpd_dir, file))
            elif file.startswith("chunk-stream1-") and file.endswith(".m4s"):
                audio_chunk_files.append(os.path.join(mpd_dir, file))

        video_chunk_files.sort()
        audio_chunk_files.sort()

        video_chunks: list[str] = []
        audio_chunks: list[str] = []

        if video_init:
            video_chunks.append(video_init)
        video_chunks.extend(video_chunk_files)

        if audio_init:
            audio_chunks.append(audio_init)
        audio_chunks.extend(audio_chunk_files)

        if not video_chunks:
            print("Error: No video chunks found")
            return False

        with tempfile.NamedTemporaryFile(
            suffix="_video.mp4", delete=False
        ) as temp_video:
            temp_video_path = temp_video.name

        with tempfile.NamedTemporaryFile(
            suffix="_audio.mp4", delete=False
        ) as temp_audio:
            temp_audio_path = temp_audio.name

        try:
            # --- Combine video chunks ---
            with open(temp_video_path, "wb") as outfile:
                for chunk in video_chunks:
                    if os.path.exists(chunk):
                        with open(chunk, "rb") as infile:
                            outfile.write(infile.read())

            if not os.path.exists(temp_video_path):
                print("Error: Failed to create combined video file")
                return False

            # --- Combine audio chunks ---
            if audio_chunks:
                with open(temp_audio_path, "wb") as outfile:
                    for chunk in audio_chunks:
                        if os.path.exists(chunk):
                            with open(chunk, "rb") as infile:
                                outfile.write(infile.read())

                if not os.path.exists(temp_audio_path):
                    print("Error: Failed to create combined audio file")
                    return False

            # --- FFmpeg mux (raw, no metadata) ---
            if audio_chunks:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    temp_video_path,
                    "-i",
                    temp_audio_path,
                    "-c",
                    "copy",
                    "-analyzeduration",
                    "100M",
                    "-probesize",
                    "50M",
                    output_path,
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    temp_video_path,
                    "-c",
                    "copy",
                    "-analyzeduration",
                    "100M",
                    "-probesize",
                    "50M",
                    output_path,
                ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0 and os.path.exists(output_path):
                return True
            else:
                print(
                    f"Error: FFmpeg conversion failed (code {result.returncode}): {result.stderr.strip()}"
                )
                return False

        finally:
            try:
                os.unlink(temp_video_path)
                if audio_chunks:
                    os.unlink(temp_audio_path)
            except Exception:
                pass

    except Exception as e:
        print(f"Error converting clip: {e}")
        return False


def upload_clip_to_immich(clip_info: Dict, game_name: Optional[str] = None) -> bool:
    """Upload a converted game clip to Immich.

    Flow:
      1. Convert DASH segments → raw MP4 (no metadata).
      2. Embed all metadata (dates, camera, game name) via exiftool in one pass.
      3. Set filesystem timestamps.
      4. Upload the final file.

    Args:
        clip_info: Clip information dictionary
        game_name: Optional game name for metadata

    Returns:
        True if upload successful, False otherwise
    """
    if not clip_info["session_mpd"]:
        print(f"No session.mpd found for clip {clip_info['clip_name']}")
        return False

    # Two temp files: raw conversion output, and the tagged final file
    with tempfile.NamedTemporaryFile(suffix="_raw.mp4", delete=False) as f:
        temp_raw_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_final_path = f.name

    try:
        # Step 1: raw DASH → MP4 conversion
        if not convert_clip_to_mp4(clip_info["session_mpd"], temp_raw_path):
            return False

        # Step 2: embed metadata in one pass
        creation_datetime = datetime.fromtimestamp(clip_info["creation_time"])
        meta = MediaMetadata(
            creation_date=creation_datetime,
            device=STEAM_DECK,
            game_name=game_name,
        )
        if not set_video_metadata(
            temp_raw_path, temp_final_path, meta, container="mp4"
        ):
            print("Warning: Metadata embedding failed, using raw file")
            temp_final_path = temp_raw_path

        # Step 3: filesystem timestamps
        set_file_timestamps(temp_final_path, creation_datetime)

        # Step 4: upload
        success = upload_video(temp_final_path, game_name)
        return success

    finally:
        for path in (temp_raw_path, temp_final_path):
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass


def get_new_clips(clips: List[Dict], last_upload_time: int) -> List[Dict]:
    """Filter clips to only include new ones since last upload."""
    return [c for c in clips if c["creation_time"] > last_upload_time]


def save_clips_tracker(tracker_data: Dict) -> None:
    """Save clips tracking data to file."""
    tracker_file = "clips_tracker.json"
    try:
        with open(tracker_file, "w") as f:
            json.dump(tracker_data, f, indent=2)
    except Exception as e:
        print(f"Error saving clips tracker: {e}")


def load_clips_tracker() -> Dict:
    """Load clips tracking data from file."""
    tracker_file = "clips_tracker.json"
    if os.path.exists(tracker_file):
        try:
            with open(tracker_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_upload_time": 0, "uploaded_clips": []}


def main():
    """Main function to upload new game clips."""
    if not os.getenv("IMMICH_API_KEY") or not os.getenv("IMMICH_SERVER_URL"):
        print("Error: Immich credentials not configured")
        return

    tracker = load_clips_tracker()
    last_upload_time = tracker.get("last_upload_time", 0)
    uploaded_clips = tracker.get("uploaded_clips", [])

    all_clips = discover_clips()

    if not all_clips:
        print("No game clips found")
        return

    new_clips = get_new_clips(all_clips, last_upload_time)

    if not new_clips:
        print("No new clips to upload")
        return

    print(f"Processing {len(new_clips)} new clip(s)...")

    from ...resolvers.game_name import get_game_name

    successful_uploads = 0
    failed_uploads = 0

    for clip in new_clips:
        game_name = get_game_name(clip["game_id"])
        label = game_name or f"Game {clip['game_id']}"
        print(f"  {clip['clip_name']} ({label})")

        if upload_clip_to_immich(clip, game_name):
            successful_uploads += 1
            uploaded_clips.append(
                {
                    "clip_name": clip["clip_name"],
                    "game_id": clip["game_id"],
                    "upload_time": datetime.now().isoformat(),
                    "creation_time": clip["creation_time"],
                }
            )
        else:
            failed_uploads += 1

    if successful_uploads > 0:
        latest_upload_time = max(c["creation_time"] for c in new_clips)
        tracker["last_upload_time"] = latest_upload_time
        tracker["uploaded_clips"] = uploaded_clips
        save_clips_tracker(tracker)

    print(
        f"Clips: {successful_uploads} uploaded, {failed_uploads} failed out of {len(new_clips)}"
    )


if __name__ == "__main__":
    main()
