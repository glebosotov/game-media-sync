import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    print("⚠️  httpx not available. Install with: pip install httpx")
    import requests
    import urllib3

    # Suppress SSL warnings
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️  Pillow not available. Install with: pip install Pillow")
    print("   EXIF data will not be added to images.")


def extract_date_from_filename(filename: str) -> datetime:
    """
    Extract creation date from Steam screenshot filename.
    Format: YYYYMMDDHHMMSS_N.jpg
    Example: 20250727170425_1.jpg -> July 27, 2025 17:04:25
    """
    try:
        # Extract the date part (first 14 characters before the underscore)
        date_part = filename.split("_")[0]
        if len(date_part) == 14 and date_part.isdigit():
            # Parse YYYYMMDDHHMMSS format
            year = int(date_part[0:4])
            month = int(date_part[4:6])
            day = int(date_part[6:8])
            hour = int(date_part[8:10])
            minute = int(date_part[10:12])
            second = int(date_part[12:14])

            return datetime(year, month, day, hour, minute, second)
        else:
            # Fallback to file system timestamp
            return datetime.fromtimestamp(os.path.getctime(filename))
    except (ValueError, IndexError):
        # Fallback to file system timestamp if parsing fails
        return datetime.fromtimestamp(os.path.getctime(filename))


def add_exif_date_to_image(
    input_path: str, creation_date: datetime, game_name: str
) -> str:
    """
    Add EXIF creation date to an image and return the path to the modified file.

    Args:
        input_path (str): Path to the original image
        creation_date (datetime): Date to set in EXIF

    Returns:
        str: Path to the temporary file with EXIF data, or original path if failed
    """
    if not PIL_AVAILABLE:
        return input_path

    try:
        # Open the image
        with Image.open(input_path) as img:
            # Convert to RGB if necessary (JPEG requires RGB)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")

            # Get existing EXIF data
            img_exif = img.getexif()

            # Set creation date in EXIF using proper tag constants
            from PIL.ExifTags import Base

            date_string = creation_date.strftime("%Y:%m:%d %H:%M:%S")
            img_exif[Base.DateTimeOriginal] = date_string
            img_exif[Base.DateTimeDigitized] = date_string
            img_exif[Base.DateTime] = date_string
            img_exif[Base.ImageDescription] = game_name
            img_exif[Base.Make] = "Valve"
            img_exif[Base.Model] = "Steam Deck"

            # Create a temporary file path without replacing leading dot in directories

            base, ext = os.path.splitext(input_path)
            temp_path = f"{base}_exif{ext}"

            # Save with modified EXIF data
            img.save(temp_path, "JPEG", exif=img_exif, quality=95)

            print(
                f"📸 Added EXIF date {creation_date.strftime('%Y:%m:%d %H:%M:%S')} to {temp_path}"
            )
            return temp_path

    except Exception as e:
        print(f"⚠️  Failed to add EXIF data: {e}")
        return input_path


def cleanup_temp_file(file_path: str, original_path: str):
    """Clean up temporary file if it was created"""
    if file_path != original_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"🧹 Cleaned up temporary file: {file_path}")
        except Exception as e:
            print(f"⚠️  Failed to clean up temporary file: {e}")


def upload_file_to_immich(
    filename: str,
    api_key: str,
    server_url: str,
    game_name: str = None,
    is_favorite: bool = False,
    visibility: str = "timeline",
    media_type: str = "screenshot",
) -> Dict[str, Any]:
    """
    Upload a file to Immich using the correct API endpoint.

    Args:
        filename (str): Path to the file to upload
        api_key (str): Immich API key (used with x-api-key header)
        server_url (str): Immich server URL (e.g., "https://your-immich-server.com")
        is_favorite (bool): Whether to mark the asset as favorite
        visibility (str): Asset visibility. Options: "archive", "timeline", "hidden", "locked"

    Returns:
        Dict[str, Any]: API response containing upload status and asset ID

    Raises:
        FileNotFoundError: If the specified file doesn't exist
        requests.RequestException: If the upload request fails
        ValueError: If the API response indicates an error
    """

    # Check if file exists
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File not found: {filename}")

    # Generate SHA1 checksum for duplicate detection
    sha1_hash = hashlib.sha1()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha1_hash.update(chunk)
    checksum = sha1_hash.hexdigest()

    # Prepare the upload URL - try the base assets endpoint
    upload_url = f"{server_url.rstrip('/')}/api/assets"

    # Prepare headers - try different authentication methods
    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
        "x-immich-checksum": checksum,
    }

    # Determine file type and extract creation date accordingly
    file_extension = Path(filename).suffix.lower()
    is_video = file_extension in [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"]

    if is_video:
        # For videos, use file modification time (which we set to the original clip time)
        # This is more reliable than creation time for converted files
        creation_date = datetime.fromtimestamp(os.path.getmtime(filename))
        file_modified_date = datetime.fromtimestamp(os.path.getmtime(filename))
        upload_file_path = filename  # No EXIF processing for videos
        print(f"🎬 Processing video file: {filename}")
        print(f"🎬 Using modification time as creation date: {creation_date}")
    else:
        # For images (screenshots), use the existing logic
        creation_date = extract_date_from_filename(filename)
        file_modified_date = datetime.fromtimestamp(os.path.getmtime(filename))
        upload_file_path = add_exif_date_to_image(filename, creation_date, game_name)
        print(f"📸 Processing image file: {filename}")

    # Debug: Show what dates we're reading
    print(
        f"📅 File system creation time: {datetime.fromtimestamp(os.path.getctime(filename))}"
    )
    print(f"📅 File system modification time: {file_modified_date}")
    print(f"📅 Extracted from filename: {creation_date}")
    print(f"📅 Sending to API - fileCreatedAt: {creation_date.isoformat()}")
    print(f"📅 Sending to API - fileModifiedAt: {file_modified_date.isoformat()}")

    try:
        # Prepare form data with file
        with open(upload_file_path, "rb") as file:
            files = {
                "assetData": (
                    os.path.basename(filename),
                    file,
                    "application/octet-stream",
                )
            }

            data = {
                "deviceAssetId": os.path.basename(filename),
                "deviceId": "steam-deck",
                "fileCreatedAt": creation_date.isoformat(),
                "fileModifiedAt": file_modified_date.isoformat(),
                "filename": os.path.basename(filename),
                "isFavorite": str(is_favorite).lower(),
                "visibility": visibility,
            }

            # Make the upload request with SSL configuration
            print(f"🔗 Uploading to: {upload_url}")
            print(f"📋 Headers: {headers}")
            print(f"📁 File: {filename}")
            print(f"🔑 API Key: {api_key[:10]}...")

            # Use httpx if available, otherwise fallback to requests
            if HTTPX_AVAILABLE:
                # Use httpx with SSL bypass
                with httpx.Client(timeout=30.0) as client:
                    # httpx handles multipart differently
                    response = client.post(
                        upload_url, headers=headers, files=files, data=data
                    )
            else:
                # Fallback to requests
                session = requests.Session()
                session.verify = False
                response = session.post(
                    upload_url, headers=headers, files=files, data=data
                )

            print(f"📡 Response status: {response.status_code}")
            print(f"📡 Response headers: {dict(response.headers)}")
            print(f"📡 Response body: {response.text}")

            # Check if request was successful
            response.raise_for_status()

            # Parse response
            try:
                result = response.json()
            except ValueError:
                # If response is not JSON, return the text
                result = {
                    "response_text": response.text,
                    "status_code": response.status_code,
                }

            # Check for API-level errors
            if "error" in result:
                raise ValueError(f"API Error: {result['error']}")

            return result

    finally:
        # Clean up temporary file if it was created
        cleanup_temp_file(upload_file_path, filename)


# Example usage and configuration
if __name__ == "__main__":
    # Configuration - read from environment variables
    IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")
    IMMICH_SERVER_URL = os.getenv("IMMICH_SERVER_URL")

    # Check if required environment variables are set
    if not IMMICH_API_KEY:
        print("Error: IMMICH_API_KEY environment variable not set")
        print("Please set the IMMICH_API_KEY environment variable")
        print("You can do this by:")
        print("  - Exporting it in your shell: export IMMICH_API_KEY='your_key'")
        print("  - Setting it in your system environment variables")
        print("  - Creating a .env file and sourcing it manually")
        exit(1)

    if not IMMICH_SERVER_URL:
        print("Error: IMMICH_SERVER_URL environment variable not set")
        print("Please set the IMMICH_SERVER_URL environment variable")
        print("You can do this by:")
        print(
            "  - Exporting it in your shell: export IMMICH_SERVER_URL='https://your-server.com'"
        )
        print("  - Setting it in your system environment variables")
        print("  - Creating a .env file and sourcing it manually")
        exit(1)

    # Check if filename argument is provided
    if len(sys.argv) < 2:
        print("Error: No filename provided")
        print("Usage: python immich_upload.py <filename>")
        print("Example: python immich_upload.py screenshot.jpg")
        exit(1)

    filename = sys.argv[1]

    # Example: Upload a single file
    try:
        result = upload_file_to_immich(
            filename=filename,
            api_key=IMMICH_API_KEY,
            server_url=IMMICH_SERVER_URL,
        )
        print(f"Upload successful: {result}")
    except Exception as e:
        print(f"Upload failed: {e}")
        exit(1)
