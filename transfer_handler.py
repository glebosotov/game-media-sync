# Immich Screenshot Upload Handler
# Uploads Steam screenshots directly to Immich photo server
import os
from immich_upload import upload_file_to_immich

def upload_screenshot(filename):
    """Upload screenshot to Immich photo server"""
    try:
        # Check if Immich credentials are configured
        api_key = os.getenv("IMMICH_API_KEY")
        server_url = os.getenv("IMMICH_SERVER_URL")
        
        if not api_key or not server_url:
            print("Immich credentials not configured")
            print("Set IMMICH_API_KEY and IMMICH_SERVER_URL environment variables to enable")
            return False
        
        print(f"Uploading {filename} to Immich...")
        
        # Upload to Immich
        result = upload_file_to_immich(
            filename=filename,
            api_key=api_key,
            server_url=server_url,
            is_favorite=False,  # You can customize this
            visibility="timeline"  # You can customize this
        )
        
        print(f"✓ Successfully uploaded to Immich: {result}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to upload to Immich: {e}")
        return False

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
        results.append({
            'filename': filename,
            'status': 'success' if success else 'error'
        })
    
    return results
