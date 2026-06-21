"""
config.py — central configuration for the YouTube automation pipeline
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# YouTube OAuth
YOUTUBE_CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

# Channel settings
CHANNEL_NAME  = os.getenv("CHANNEL_NAME", "LearnCS Daily")
VIDEO_PRIVACY = os.getenv("VIDEO_PRIVACY", "public")

# Language and Voice settings
LANGUAGE      = os.getenv("LANGUAGE", "en").lower()
if LANGUAGE == "hi":
    TTS_VOICE = os.getenv("TTS_VOICE", "hi-IN-MadhurNeural")
    TTS_RATE  = os.getenv("TTS_RATE", "+12%")  # Slightly faster for natural Hindi flow
else:
    TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")
    TTS_RATE  = os.getenv("TTS_RATE", "+0%")   # Standard speed for English

# Paths
OUTPUT_DIR       = "output"
CURRICULUM_FILE  = "curriculum.json"

# Video settings
VIDEO_WIDTH   = 1920
VIDEO_HEIGHT  = 1080
VIDEO_FPS     = 24
TARGET_DURATION = 300   # 5 minutes in seconds
