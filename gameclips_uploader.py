#!/usr/bin/env python3
"""
Game Clips Uploader
Handles discovery, conversion, and upload of Steam game clips to Immich.

Process:
1. Scan gamerecordings/clips/ for clip_{gameid}_{date}_{time} directories
2. Find session.mpd files in video subdirectories
3. Convert to MP4 using FFmpeg
4. Set proper timestamps and metadata
5. Upload to Immich with game info
"""

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

import steamstuff
from transfer_handler import upload_video


def get_clips_directory() -> Optional[str]:
    """Get the Steam clips directory path."""
    try:
        user = steamstuff.GetAccountId()
        clips_dir = (
            f"{steamstuff.steamdir}userdata/{user & 0xFFFFFFFF}/gamerecordings/clips"
        )
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


def convert_clip_to_mp4(session_mpd_path: str, output_path: str) -> bool:
    """Convert session.mpd to MP4 by combining video and audio chunks.

    Based on the approach from: https://gist.githubusercontent.com/safijari/afa41cb017eb2d0cadb20bf9fcfecc93/raw/ebfe2e14265d51cecfbca5bb34cb28e518936fa6/convert_valve_video.py

    Args:
        session_mpd_path: Path to session.mpd file
        output_path: Path for output MP4 file

    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # Get the directory containing the MPD file and chunks
        mpd_dir = os.path.dirname(session_mpd_path)

        # Find video and audio chunks
        video_chunks = []
        audio_chunks = []

        # Debug: Show all files in the directory
        all_files = os.listdir(mpd_dir)
        print(f"📂 Files in MPD directory: {all_files}")

        # Look for init files and chunk files
        for file in all_files:
            if file.startswith("init-stream0.m4s"):
                video_chunks.append(os.path.join(mpd_dir, file))
            elif file.startswith("init-stream1.m4s"):
                audio_chunks.append(os.path.join(mpd_dir, file))
            elif file.startswith("chunk-stream0-") and file.endswith(".m4s"):
                video_chunks.append(os.path.join(mpd_dir, file))
            elif file.startswith("chunk-stream1-") and file.endswith(".m4s"):
                audio_chunks.append(os.path.join(mpd_dir, file))

        # Sort chunks to ensure proper order
        video_chunks.sort()
        audio_chunks.sort()

        print(f"📹 Found {len(video_chunks)} video chunks")
        print(f"🔊 Found {len(audio_chunks)} audio chunks")

        if not video_chunks:
            print("❌ No video chunks found")
            return False

        # Create temporary files for combined streams
        with tempfile.NamedTemporaryFile(
            suffix="_video.mp4", delete=False
        ) as temp_video:
            temp_video_path = temp_video.name

        with tempfile.NamedTemporaryFile(
            suffix="_audio.mp4", delete=False
        ) as temp_audio:
            temp_audio_path = temp_audio.name

        try:
            # Combine video chunks
            if video_chunks:
                print("🔗 Combining video chunks...")
                print(f"📹 Video chunks: {[os.path.basename(f) for f in video_chunks]}")
                with open(temp_video_path, "wb") as outfile:
                    for chunk in video_chunks:
                        if os.path.exists(chunk):
                            with open(chunk, "rb") as infile:
                                data = infile.read()
                                outfile.write(data)
                                print(
                                    f"  ✅ Added {os.path.basename(chunk)} ({len(data)} bytes)"
                                )
                        else:
                            print(f"  ❌ Missing chunk: {chunk}")

                # Verify the combined file was created and has content
                if os.path.exists(temp_video_path):
                    video_size = os.path.getsize(temp_video_path)
                    print(
                        f"📹 Combined video file: {temp_video_path} ({video_size} bytes)"
                    )
                else:
                    print("❌ Failed to create combined video file")
                    return False

            # Combine audio chunks (if any)
            if audio_chunks:
                print("🔗 Combining audio chunks...")
                print(f"🔊 Audio chunks: {[os.path.basename(f) for f in audio_chunks]}")
                with open(temp_audio_path, "wb") as outfile:
                    for chunk in audio_chunks:
                        if os.path.exists(chunk):
                            with open(chunk, "rb") as infile:
                                data = infile.read()
                                outfile.write(data)
                                print(
                                    f"  ✅ Added {os.path.basename(chunk)} ({len(data)} bytes)"
                                )
                        else:
                            print(f"  ❌ Missing chunk: {chunk}")

                # Verify the combined file was created and has content
                if os.path.exists(temp_audio_path):
                    audio_size = os.path.getsize(temp_audio_path)
                    print(
                        f"🔊 Combined audio file: {temp_audio_path} ({audio_size} bytes)"
                    )
                else:
                    print("❌ Failed to create combined audio file")
                    return False

            # Use FFmpeg to combine video and audio streams (based on reference)
            if audio_chunks:
                # Both video and audio - using reference approach
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
                # Video only - using reference approach
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

            print(f"🎬 Final FFmpeg command: {' '.join(cmd)}")

            # Check if input files exist and have content
            if os.path.exists(temp_video_path):
                video_size = os.path.getsize(temp_video_path)
                print(f"📹 Input video file: {temp_video_path} ({video_size} bytes)")
            else:
                print(f"❌ Input video file missing: {temp_video_path}")
                return False

            if audio_chunks and os.path.exists(temp_audio_path):
                audio_size = os.path.getsize(temp_audio_path)
                print(f"🔊 Input audio file: {temp_audio_path} ({audio_size} bytes)")
            elif audio_chunks:
                print(f"❌ Input audio file missing: {temp_audio_path}")
                return False

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0 and os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                print(f"✅ Conversion successful: {output_path} ({output_size} bytes)")
                return True
            else:
                print("❌ FFmpeg conversion failed:")
                print(f"   Return code: {result.returncode}")
                print(f"   Stderr: {result.stderr}")
                print(f"   Stdout: {result.stdout}")

                # Fallback: Try original MPD approach
                print("🔄 Trying fallback MPD approach...")
                cmd_fallback = [
                    "ffmpeg",
                    "-i",
                    session_mpd_path,
                    "-c",
                    "copy",
                    "-y",
                    output_path,
                ]

                result_fallback = subprocess.run(
                    cmd_fallback,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result_fallback.returncode == 0 and os.path.exists(output_path):
                    print(f"✅ Fallback conversion successful: {output_path}")
                    return True
                else:
                    print(
                        f"❌ Fallback conversion also failed: {result_fallback.stderr}"
                    )
                    return False

        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_video_path)
                if audio_chunks:
                    os.unlink(temp_audio_path)
            except Exception:
                pass

    except Exception as e:
        print(f"Error converting clip: {e}")
        return False


def set_file_timestamps(file_path: str, creation_time: int) -> None:
    """Set file creation and modification times."""
    try:
        # Convert creation_time to float (os.utime expects float)
        timestamp = float(creation_time)

        print(f"🕒 Setting file timestamps to: {timestamp}")
        print(f"🕒 Human readable: {datetime.fromtimestamp(timestamp)}")

        # Set both access time and modification time to the original clip time
        os.utime(file_path, (timestamp, timestamp))

        # Verify the timestamp was set correctly
        stat_info = os.stat(file_path)
        print(
            f"✅ File timestamps set - mtime: {stat_info.st_mtime}, atime: {stat_info.st_atime}"
        )

    except Exception as e:
        print(f"❌ Error setting file timestamps: {e}")


def upload_clip_to_immich(clip_info: Dict, game_name: Optional[str] = None) -> bool:
    """Upload a converted game clip to Immich.

    Args:
        clip_info: Clip information dictionary
        game_name: Optional game name for metadata

    Returns:
        True if upload successful, False otherwise
    """
    if not clip_info["session_mpd"]:
        print(f"No session.mpd found for clip {clip_info['clip_name']}")
        return False

    # Create temporary MP4 file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
        temp_mp4_path = temp_file.name

    try:
        # Debug: Check MPD file and directory structure
        print(f"Converting clip {clip_info['clip_name']}...")
        print(f"📁 Session MPD path: {clip_info['session_mpd']}")

        # Check if MPD file exists and show its size
        if os.path.exists(clip_info["session_mpd"]):
            mpd_size = os.path.getsize(clip_info["session_mpd"])
            print(f"📄 MPD file size: {mpd_size} bytes")

            # Show directory contents for debugging
            mpd_dir = os.path.dirname(clip_info["session_mpd"])
            try:
                dir_contents = os.listdir(mpd_dir)
                print(f"📂 MPD directory contents: {dir_contents}")
            except Exception:
                pass

        if not convert_clip_to_mp4(clip_info["session_mpd"], temp_mp4_path):
            return False

        # Set proper timestamps using the extracted creation time from folder name
        set_file_timestamps(temp_mp4_path, clip_info["creation_time"])

        # Upload to Immich using regular video upload function
        # The file timestamps are now set correctly, so Immich will read the right date
        print(f"Uploading clip {clip_info['clip_name']} to Immich...")
        success = upload_video(temp_mp4_path, game_name)

        if success:
            print(f"✅ Clip uploaded successfully: {clip_info['clip_name']}")
            if game_name:
                print(f"   Game: {game_name} (ID: {clip_info['game_id']})")
            print(f"   Created: {datetime.fromtimestamp(clip_info['creation_time'])}")

        return success

    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_mp4_path)
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
    print("Steam Game Clips Upload Script")
    print("=" * 40)

    # Check if Immich credentials are configured
    if not os.getenv("IMMICH_API_KEY") or not os.getenv("IMMICH_SERVER_URL"):
        print("❌ Immich credentials not configured!")
        print("Please set IMMICH_API_KEY and IMMICH_SERVER_URL environment variables")
        return

    # Load clips tracker
    tracker = load_clips_tracker()
    last_upload_time = tracker.get("last_upload_time", 0)
    uploaded_clips = tracker.get("uploaded_clips", [])

    print(
        f"Last upload time: {datetime.fromtimestamp(last_upload_time) if last_upload_time > 0 else 'Never'}"
    )

    # Discover all clips
    print("Scanning Steam game clips...")
    all_clips = discover_clips()

    if not all_clips:
        print("No game clips found")
        return

    print(f"Total clips found: {len(all_clips)}")

    # Get new clips since last upload
    new_clips = get_new_clips(all_clips, last_upload_time)

    if not new_clips:
        print("✅ No new clips to upload")
        return

    print(f"New clips to upload: {len(new_clips)}")

    # Import game name resolver
    def get_game_name_fallback(app_id):
        return None

    try:
        from game_name_resolver import get_game_name
    except ImportError:
        print("Warning: game_name_resolver not available, skipping game names")
        get_game_name = get_game_name_fallback

    # Upload new clips
    successful_uploads = 0
    failed_uploads = 0

    for clip in new_clips:
        print(f"\n🎬 Processing clip: {clip['clip_name']}")
        print(f"   Game ID: {clip['game_id']}")
        print(f"   Created: {datetime.fromtimestamp(clip['creation_time'])}")

        # Get game name
        game_name = get_game_name(clip["game_id"])
        if game_name:
            print(f"   Game: {game_name}")

        # Upload clip
        if upload_clip_to_immich(clip, game_name):
            successful_uploads += 1
            # Update tracker
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

    # Update tracker with latest upload time
    if successful_uploads > 0:
        latest_upload_time = max(c["creation_time"] for c in new_clips)
        tracker["last_upload_time"] = latest_upload_time
        tracker["uploaded_clips"] = uploaded_clips
        save_clips_tracker(tracker)

    # Summary
    print("\n" + "=" * 40)
    print("Clips Upload Summary:")
    print(f"✅ Successful: {successful_uploads}")
    print(f"❌ Failed: {failed_uploads}")
    print(f"📊 Total processed: {len(new_clips)}")

    if successful_uploads > 0:
        print(
            f"🕒 Last upload time updated to: {datetime.fromtimestamp(tracker['last_upload_time'])}"
        )


if __name__ == "__main__":
    main()
