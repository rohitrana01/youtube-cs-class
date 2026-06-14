"""
modules/youtube_uploader.py
Uploads video + thumbnail to YouTube using the Data API v3.

Authentication uses a refresh token stored in env vars — no browser popup
needed in CI. Run auth_setup.py once locally to generate the refresh token.

Free quota: 10,000 units/day. Each upload costs ~1,600 units → ~6 uploads/day.
For 1 video/day this is completely within the free tier.
"""
import os
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from config import (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET,
                    YOUTUBE_REFRESH_TOKEN, VIDEO_PRIVACY)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]


def _get_service():
    """Build an authenticated YouTube service using the stored refresh token."""
    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str, thumbnail_path: str,
                 title: str, description: str, tags: list[str]) -> str:
    """
    Upload video to YouTube and set its thumbnail.

    Returns the YouTube video ID (e.g. 'dQw4w9WgXcQ').
    Retries up to 3 times on transient errors.
    """
    youtube = _get_service()

    body = {
        "snippet": {
            "title": title[:100],          # YouTube max
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": "27",            # Education
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": VIDEO_PRIVACY,
            "selfDeclaredMadeForKids": False,
            "madeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024,   # 8 MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    print(f"  [uploader] Uploading: {title}")
    video_id = _resumable_upload(request)

    # Set thumbnail
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()
            print(f"  [uploader] Thumbnail set ✓")
        except HttpError as e:
            print(f"  [uploader] Thumbnail failed (non-fatal): {e}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  [uploader] Live at: {url}")
    return video_id


def _resumable_upload(request, max_retries: int = 3) -> str:
    """Drive a resumable upload with retry logic."""
    response = None
    error    = None
    retry    = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"  [uploader] Progress: {pct}%", end="\r")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retry < max_retries:
                retry += 1
                wait = 2 ** retry
                print(f"  [uploader] Retry {retry} in {wait}s…")
                time.sleep(wait)
            else:
                raise

    print()   # newline after progress
    return response["id"]
