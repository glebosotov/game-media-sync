#!/usr/bin/env python3
"""
Steam Screenshot Upload Script
Uploads all screenshots made since the last successful upload to Immich
"""

import os
import json
import vdf
import steamstuff
from transfer_handler import upload_screenshot
from datetime import datetime

# Configuration
TRACKING_FILE = "upload_tracker.json"
STEAMDIR = steamstuff.steamdir

def load_upload_tracker():
    """Load the tracking file to see which screenshots have been uploaded"""
    if os.path.exists(TRACKING_FILE):
        try:
            with open(TRACKING_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {"last_upload_time": 0, "uploaded_screenshots": []}

def save_upload_tracker(tracker_data):
    """Save the tracking data to file"""
    with open(TRACKING_FILE, 'w') as f:
        json.dump(tracker_data, f, indent=2)

def get_all_screenshots():
    """Get all screenshots from Steam's screenshots.vdf file"""
    try:
        user = steamstuff.GetAccountId()
        vdf_path = f"{STEAMDIR}userdata/{user & 0xFFFFFFFF}/760/screenshots.vdf"
        
        if not os.path.exists(vdf_path):
            print(f"Screenshots file not found: {vdf_path}")
            return []
        
        # Parse the screenshots.vdf file
        with open(vdf_path, 'r') as f:
            d = vdf.parse(f)
        
        # Handle case inconsistency
        if 'screenshots' in d:
            screenshots = d['screenshots']
        elif 'Screenshots' in d:
            screenshots = d['Screenshots']
        else:
            print("No screenshots found in VDF file")
            return []
        
        # Collect all screenshots with metadata
        all_screenshots = []
        for game in screenshots:
            for screenshot_id in screenshots[game]:
                screenshot_data = screenshots[game][screenshot_id]
                if 'creation' in screenshot_data and 'filename' in screenshot_data:
                    all_screenshots.append({
                        'game_id': int(game),
                        'screenshot_id': int(screenshot_id),
                        'creation_time': int(screenshot_data['creation']),
                        'filename': screenshot_data['filename'],
                        'full_path': f"{STEAMDIR}userdata/{user & 0xFFFFFFFF}/760/remote/{screenshot_data['filename']}"
                    })
        
        # Sort by creation time (oldest first)
        all_screenshots.sort(key=lambda x: x['creation_time'])
        return all_screenshots
        
    except Exception as e:
        print(f"Error reading screenshots: {e}")
        return []

def get_new_screenshots(screenshots, last_upload_time):
    """Filter screenshots to only include new ones since last upload"""
    return [s for s in screenshots if s['creation_time'] > last_upload_time]

def main():
    """Main function to upload new screenshots"""
    print("Steam Screenshot Upload Script")
    print("=" * 40)
    
    # Check if Immich credentials are configured
    if not os.getenv("IMMICH_API_KEY") or not os.getenv("IMMICH_SERVER_URL"):
        print("❌ Immich credentials not configured!")
        print("Please set IMMICH_API_KEY and IMMICH_SERVER_URL environment variables")
        return
    
    # Load upload tracker
    tracker = load_upload_tracker()
    last_upload_time = tracker.get("last_upload_time", 0)
    uploaded_screenshots = tracker.get("uploaded_screenshots", [])
    
    print(f"Last upload time: {datetime.fromtimestamp(last_upload_time) if last_upload_time > 0 else 'Never'}")
    
    # Get all screenshots
    print("Scanning Steam screenshots...")
    all_screenshots = get_all_screenshots()
    
    if not all_screenshots:
        print("No screenshots found")
        return
    
    print(f"Total screenshots found: {len(all_screenshots)}")
    
    # Get new screenshots since last upload
    new_screenshots = get_new_screenshots(all_screenshots, last_upload_time)
    
    if not new_screenshots:
        print("✅ No new screenshots to upload")
        return
    
    print(f"New screenshots to upload: {len(new_screenshots)}")
    
    # Upload new screenshots
    successful_uploads = 0
    failed_uploads = 0
    
    for screenshot in new_screenshots:
        print(f"\n📸 Uploading: {screenshot['filename']}")
        print(f"   Game ID: {screenshot['game_id']}")
        print(f"   Created: {datetime.fromtimestamp(screenshot['creation_time'])}")
        
        # Check if file exists
        if not os.path.exists(screenshot['full_path']):
            print(f"   ❌ File not found: {screenshot['full_path']}")
            failed_uploads += 1
            continue
        
        # Upload to Immich
        if upload_screenshot(screenshot['full_path']):
            print(f"   ✅ Upload successful")
            successful_uploads += 1
            # Update tracker
            uploaded_screenshots.append({
                'filename': screenshot['filename'],
                'upload_time': datetime.now().isoformat(),
                'creation_time': screenshot['creation_time']
            })
        else:
            print(f"   ❌ Upload failed")
            failed_uploads += 1
    
    # Update tracker with latest upload time
    if successful_uploads > 0:
        latest_upload_time = max(s['creation_time'] for s in new_screenshots)
        tracker['last_upload_time'] = latest_upload_time
        tracker['uploaded_screenshots'] = uploaded_screenshots
        save_upload_tracker(tracker)
    
    # Summary
    print("\n" + "=" * 40)
    print("Upload Summary:")
    print(f"✅ Successful: {successful_uploads}")
    print(f"❌ Failed: {failed_uploads}")
    print(f"📊 Total processed: {len(new_screenshots)}")
    
    if successful_uploads > 0:
        print(f"🕒 Last upload time updated to: {datetime.fromtimestamp(tracker['last_upload_time'])}")

if __name__ == "__main__":
    main()
