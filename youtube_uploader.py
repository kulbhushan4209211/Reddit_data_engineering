import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")

# 🎯 Strict YouTube upload clearance scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/spreadsheets']
CLIENT_SECRETS_FILE = 'credentials.json'

# Global asset storage structures
VIDEO_DIR = "assets/videos"

def get_authenticated_service():
    """Handles OAuth v2 user flow and caches credentials using a permanent pickle asset."""
    creds = None
    # 'token_youtube.pickle' stores the access and refresh tokens locally
    if os.path.exists('token_youtube.pickle'):
        with open('token_youtube.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired YouTube API access token...")
            creds.refresh(Request())
        else:
            print("🔑 Booting local browser authorization window...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next automated run
        with open('token_youtube.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds), build('sheets', 'v4', credentials=creds)

def upload_short_video(youtube, video_path, title, description):
    """Executes a multi-part chunked video upload directly to the channel grid."""
    print(f"🚀 Initializing video stream upload array for: {video_path}")
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['Shorts', 'RedditDebates', 'DataStorytelling'],
            'categoryId': '24' # 24 maps directly to 'Entertainment'
        },
        'status': {
            'privacyStatus': 'public', # Instantly live! Change to 'private' if you want to preview first
            'selfDeclaredMadeForKids': False
        }
    }

    # Upload in chunks of 1MB to handle large network drops gracefully
    media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True, mimetype='video/mp4')
    
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"📦 Upload Progress: {int(status.progress() * 100)}% complete...")
            
    print(f"✅ SUCCESS! Video successfully live. Video ID: {response['id']}")
    return response['id']

def process_youtube_upload_pipeline():
    print("📺 Booting up Phase 6: Automated YouTube Shorts Deployment Engine...")
    youtube_service, sheets_service = get_authenticated_service()
    
    TARGET_TAB = "Production_Scripts"
    result = sheets_service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"{TARGET_TAB}!A:H").execute()
    rows = result.get('values', [])
    
    for i, row in enumerate(rows):
        if i == 0: continue
        if len(row) == 8 and row[7] == "Video Completed":
            date, sub, hook = row[0], row[1], row[2]
            base_name = f"{date}_{sub.replace(' ', '_')}_row{i+1}_FINAL.mp4"
            video_path = f"{VIDEO_DIR}/{base_name}"
            
            if not os.path.exists(video_path):
                print(f"⚠️ Could not find expected target video file: {video_path}. Skipping.")
                continue
                
            # Build high-engagement short-form metadata layout
            # 🎯 CRITICAL: #Shorts must be present in metadata for the short vertical placement
            short_title = f"r/{sub} Debate: {hook[:60]}... #Shorts"
            short_description = f"Original Post Topic: {hook}\n\nWhat side are you on? Answer in the comments below! #Shorts #Reddit #Trending"
            
            try:
                # Fire upload array
                upload_short_video(youtube_service, video_path, short_title, short_description)
                
                # Update database architecture status field to fully deployed
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID, range=f"{TARGET_TAB}!H{i+1}",
                    valueInputOption="RAW", body={'values': [["Fully Deployed"]]}
                ).execute()
                print(f"💾 Updated row {i+1} status matrix to 'Fully Deployed'.\n")
                
            except Exception as e:
                print(f"❌ YouTube API Deployment Failure for row {i+1}: {e}")

if __name__ == "__main__":
    process_youtube_upload_pipeline()