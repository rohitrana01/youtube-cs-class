"""
modules/tts_narrator.py
Generates narration audio from the script using Microsoft Edge TTS.
This is completely free — it uses the same neural voices as Edge browser.
Returns the path to the generated MP3 and its duration in seconds.
"""
import asyncio
import os
import subprocess
from config import TTS_VOICE, TTS_RATE


async def _generate_async(text: str, output_path: str, voice: str, rate: str):
    """Run edge-tts and save to output_path."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


def generate_narration(narration_text: str, output_dir: str,
                       voice: str = None, filename: str = "narration.mp3") -> tuple[str, float]:
    """
    Generate TTS audio from narration_text.

    Returns:
        (audio_path, duration_seconds)

    Available high-quality voices (en-US):
        en-US-AriaNeural      — warm, friendly female (default)
        en-US-GuyNeural       — clear male
        en-US-JennyNeural     — professional female
        en-US-BrianNeural     — engaging male
        en-GB-SoniaNeural     — British female
    """
    voice = voice or TTS_VOICE
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, filename)

    print(f"  [tts] Generating audio with voice: {voice} at speed {TTS_RATE}")

    try:
        asyncio.run(_generate_async(narration_text, audio_path, voice, TTS_RATE))
    except RuntimeError:
        # Handle case where there's already a running event loop (Jupyter, etc.)
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_generate_async(narration_text, audio_path, voice, TTS_RATE))

    # Get duration via ffprobe
    duration = _get_audio_duration(audio_path, narration_text)
    print(f"  [tts] Audio generated: {duration:.1f}s  →  {audio_path}")
    return audio_path, duration


def _get_audio_duration(path: str, narration_text: str) -> float:
    """Use ffprobe to get precise audio duration in seconds."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path
            ],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except Exception:
        # Fallback: estimate from word count (~140 wpm)
        word_count = len(narration_text.split())
        return max(word_count / 140 * 60, 60)
