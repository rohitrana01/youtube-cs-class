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

env_voice     = os.getenv("TTS_VOICE", "").strip()
env_rate      = os.getenv("TTS_RATE", "").strip()

if LANGUAGE == "hi":
    TTS_VOICE = env_voice if env_voice else "hi-IN-MadhurNeural"
    TTS_RATE  = env_rate if env_rate else "+12%"  # Slightly faster for natural Hindi flow
else:
    TTS_VOICE = env_voice if env_voice else "en-US-AriaNeural"
    TTS_RATE  = env_rate if env_rate else "+0%"   # Standard speed for English

# Paths
OUTPUT_DIR       = "output"
CURRICULUM_FILE  = "curriculum.json"

# Video settings
VIDEO_WIDTH   = 1920
VIDEO_HEIGHT  = 1080
VIDEO_FPS     = 24
TARGET_DURATION = 300   # 5 minutes in seconds
