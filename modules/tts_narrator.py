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
def generate_course_narration(script_data: dict, output_dir: str) -> tuple[str, float, dict]:
    """
    Generate audio narration for the entire course video by generating individual
    audio clips for each section and then concatenating them.
    
    Returns:
        (concatenated_audio_path, total_duration_seconds, durations_dict)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Define sections and text
    sections = []
    
    # Intro
    sections.append(("intro", script_data["intro"]["narration"], "narration_intro.mp3"))
    
    # Segments
    for idx, seg in enumerate(script_data.get("segments", [])):
        sections.append((f"seg_{idx}", seg["narration"], f"narration_seg_{idx}.mp3"))
        
    # Quiz
    sections.append(("quiz", script_data["quiz"]["narration"], "narration_quiz.mp3"))
    
    # Summary
    sections.append(("summary", script_data["summary"]["narration"], "narration_summary.mp3"))
    
    # Outro
    sections.append(("outro", script_data["outro"]["narration"], "narration_outro.mp3"))
    
    # 2. Generate audio for each section and record durations
    durations = {
        "intro": 0.0,
        "segments": [],
        "quiz": 0.0,
        "summary": 0.0,
        "outro": 0.0
    }
    
    audio_paths = []
    
    for sec_name, text, filename in sections:
        path, dur = generate_narration(text, output_dir, filename=filename)
        audio_paths.append(path)
        
        if sec_name == "intro":
            durations["intro"] = dur
        elif sec_name.startswith("seg_"):
            durations["segments"].append(dur)
        elif sec_name == "quiz":
            durations["quiz"] = dur
        elif sec_name == "summary":
            durations["summary"] = dur
        elif sec_name == "outro":
            durations["outro"] = dur
            
    # 3. Concatenate by binary joining MP3 data
    final_audio_path = os.path.join(output_dir, "narration.mp3")
    print(f"  [tts] Concatenating {len(audio_paths)} narration files...")
    try:
        with open(final_audio_path, "wb") as outfile:
            for p in audio_paths:
                with open(p, "rb") as infile:
                    outfile.write(infile.read())
    except Exception as e:
        print(f"  [tts] Narration concatenation failed: {e}")
        raise
        
    # Clean up intermediate audio files
    for p in audio_paths:
        if os.path.exists(p):
            os.remove(p)
            
    total_duration = _get_audio_duration(final_audio_path, "")
    print(f"  [tts] Final concatenated audio: {total_duration:.1f}s  →  {final_audio_path}")
    
    return final_audio_path, total_duration, durations


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
