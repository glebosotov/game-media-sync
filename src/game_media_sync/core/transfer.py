# Immich Media Upload Handler
# Uploads Steam screenshots and game clips to Immich photo server
import os

from .upload import upload_file_to_immich


def upload_media(filename, game_name=None, media_type="screenshot"):
    """Upload media file (screenshot or video) to Immich photo server

    Args:
        filename: Path to the media file
        game_name: Optional game name for metadata
        media_type: Type of media ("screenshot" or "video")
    """
    try:
        api_key = os.getenv("IMMICH_API_KEY")
        server_url = os.getenv("IMMICH_SERVER_URL")

        if not api_key or not server_url:
            print("Immich credentials not configured")
            print(
                "Set IMMICH_API_KEY and IMMICH_SERVER_URL environment variables to enable"
            )
            return False

        print(f"Uploading {media_type} {filename} to Immich...")

        result = upload_file_to_immich(
            filename=filename,
            game_name=game_name,
            api_key=api_key,
            server_url=server_url,
            is_favorite=False,  # You can customize this
            visibility="timeline",  # You can customize this
            media_type=media_type,
        )

        print(f"✓ Successfully uploaded to Immich: {result}")
        return True

    except Exception as e:
        print(f"✗ Failed to upload to Immich: {e}")
        return False


def upload_screenshot(filename, game_name=None):
    """Upload screenshot to Immich photo server (backward compatibility)"""
    return upload_media(filename, game_name, "screenshot")


def upload_video(filename, game_name=None):
    """Upload video to Immich photo server"""
    return upload_media(filename, game_name, "video")


def upload_multiple_screenshots(filenames):
    """
    Upload multiple screenshots to Immich

    Args:
        filenames (list): List of screenshot file paths to upload

    Returns:
        list: List of upload results for each file
    """
    results = []

    for filename in filenames:
        success = upload_screenshot(filename)
        results.append(
            {"filename": filename, "status": "success" if success else "error"}
        )

    return results
