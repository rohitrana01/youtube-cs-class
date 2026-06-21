"""
modules/video_assembler.py
Merges the silent animation video with the TTS audio track.
Handles duration mismatches (loops or trims the video to match audio length).
"""
import os
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from config import LANGUAGE


def assemble_video(animation_path: str, audio_path: str, output_dir: str, filename: str = None, is_short: bool = False) -> str:
    """
    Combine silent animation with TTS narration audio.

    Strategy:
    - If video is longer than audio  → trim video end
    - If video is shorter than audio → loop the last frame to fill

    Returns path to the final MP4.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_name = filename or f"final_video_{LANGUAGE}.mp4"
    output_path = os.path.join(output_dir, out_name)

    print("  [assembler] Loading video and audio…")
    video = VideoFileClip(animation_path)
    audio = AudioFileClip(audio_path)

    vid_dur = video.duration
    aud_dur = audio.duration

    print(f"  [assembler] Video: {vid_dur:.1f}s  |  Audio: {aud_dur:.1f}s")

    if vid_dur >= aud_dur:
        # Trim video to audio length
        video = video.subclip(0, aud_dur)
    else:
        # Pad video: freeze last frame for remaining duration
        gap = aud_dur - vid_dur
        last_frame_time = max(vid_dur - 0.05, 0)
        freeze = video.subclip(last_frame_time, vid_dur).loop(duration=gap)
        video = concatenate_videoclips([video, freeze])

    # Attach audio
    final = video.set_audio(audio)

    # Do not append custom outro for Shorts
    if not is_short and os.path.exists("custom_outro.mp4"):
        print("  [assembler] Appending custom outro video...")
        outro_clip = VideoFileClip("custom_outro.mp4")
        if outro_clip.size != final.size:
            outro_clip = outro_clip.resize(final.size)
        final = concatenate_videoclips([final, outro_clip])

    print(f"  [assembler] Writing final video → {output_path}")
    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast", "-movflags", "+faststart", "-pix_fmt", "yuv420p"]
    )

    # Clean up
    video.close()
    audio.close()
    final.close()

    print(f"  [assembler] Done — {os.path.getsize(output_path) / 1e6:.1f} MB")
    return output_path
