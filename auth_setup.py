"""
auth_setup.py — Run this ONCE locally to get your YouTube refresh token.

Steps:
  1. Create a project at console.cloud.google.com
  2. Enable "YouTube Data API v3"
  3. Create OAuth 2.0 credentials → Desktop app
  4. Download client_secrets.json to this folder
  5. Run:  python auth_setup.py
  6. A browser window opens — log in with your YouTube channel account
  7. Copy the printed credentials into GitHub Secrets

GitHub Secrets to add:
  ANTHROPIC_API_KEY      → your Anthropic key
  YOUTUBE_CLIENT_ID      → printed below
  YOUTUBE_CLIENT_SECRET  → printed below
  YOUTUBE_REFRESH_TOKEN  → printed below
"""

import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

SECRETS_FILE = "client_secrets.json"


def main():
    if not os.path.exists(SECRETS_FILE):
        print(f"❌  {SECRETS_FILE} not found.")
        print("   Download it from Google Cloud Console:")
        print("   console.cloud.google.com → APIs & Services → Credentials")
        print("   → Create Credentials → OAuth 2.0 Client ID → Desktop app")
        return

    print("🔐  Starting OAuth flow — a browser window will open…\n")

    flow = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n" + "═" * 60)
    print("  ✅  Authentication successful!")
    print("  Copy these values into your GitHub repository Secrets:")
    print("  (Settings → Secrets and variables → Actions → New secret)")
    print("═" * 60)
    print(f"\n  YOUTUBE_CLIENT_ID:\n    {creds.client_id}")
    print(f"\n  YOUTUBE_CLIENT_SECRET:\n    {creds.client_secret}")
    print(f"\n  YOUTUBE_REFRESH_TOKEN:\n    {creds.refresh_token}")
    print("\n" + "═" * 60)

    # Also save to a local .env for testing
    with open(".env", "a") as f:
        f.write(f"\nYOUTUBE_CLIENT_ID={creds.client_id}")
        f.write(f"\nYOUTUBE_CLIENT_SECRET={creds.client_secret}")
        f.write(f"\nYOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
    print("\n  Also appended to .env for local testing.")


if __name__ == "__main__":
    main()
