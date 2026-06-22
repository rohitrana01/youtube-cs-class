"""
pipeline.py — Main automation orchestrator
Run this daily (via GitHub Actions cron) to:
  1. Pick the next topic from curriculum.json
  2. Generate script with Claude API
  3. Create TTS narration audio
  4. Render animated video slides
  5. Assemble final video (video + audio)
  6. Generate thumbnail
  7. Upload to YouTube
  8. Mark topic as uploaded in curriculum.json
"""
import os
import sys
import json
import shutil
from datetime import datetime, timezone

from config import OUTPUT_DIR, CURRICULUM_FILE, LANGUAGE
from modules.script_generator   import generate_script
from modules.tts_narrator       import generate_narration, generate_course_narration
from modules.animator           import create_animation, create_short_animation
from modules.video_assembler    import assemble_video
from modules.thumbnail_generator import create_thumbnail
from modules.youtube_uploader   import upload_video


# ── Curriculum helpers ────────────────────────────────────────────────────────

def load_curriculum() -> dict:
    with open(CURRICULUM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_curriculum(data: dict):
    with open(CURRICULUM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_next_topic(curriculum: dict) -> dict | None:
    for topic in curriculum["topics"]:
        if not topic.get("uploaded", False):
            return topic
    return None


def mark_uploaded(curriculum: dict, topic_id: str, video_id: str):
    for t in curriculum["topics"]:
        if t["id"] == topic_id:
            t["uploaded"]    = True
            t["video_id"]    = video_id
            t["upload_date"] = datetime.now(timezone.utc).isoformat()
            break


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run():
    print("\n" + "═" * 60)
    print("  🚀  YouTube Automation Pipeline")
    print("═" * 60)

    dry_run = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
    if dry_run:
        print("🔍  DRY RUN MODE ENABLED — No actual upload or curriculum save will occur.")

    # ── 0. Load curriculum ──────────────────────────────────────────────────
    curriculum = load_curriculum()
    topic = get_next_topic(curriculum)

    if topic is None:
        print("✅  All 100 topics have been uploaded! Course complete.")
        sys.exit(0)

    print(f"\n📚  Day {topic['day']:03d}: {topic['title']}")
    print(f"     Module  : {topic['module']}")
    print(f"     Level   : {topic['level']}")

    # ── Output directory for this topic ────────────────────────────────────
    out = os.path.join(OUTPUT_DIR, topic["id"])
    os.makedirs(out, exist_ok=True)

    # ── 1. Generate script ───────────────────────────────────────────────────
    print("\n[1/6] 🤖  Generating script via Claude API…")
    script_data = generate_script(topic)
    print(f"       Title  : {script_data['video_title']}")
    print(f"       Segs   : {len(script_data.get('segments', []))} segments")

    # Save script for debugging
    with open(os.path.join(out, "script.json"), "w") as f:
        json.dump(script_data, f, indent=2)

    # ── 2. Generate TTS narration ────────────────────────────────────────────
    print("\n[2/6] 🎙️   Generating TTS narrations…")
    # Main Video
    audio_path, audio_duration, durations = generate_course_narration(
        script_data, out
    )
    print(f"       Main Video Duration: {audio_duration:.1f}s")
    
    # YouTube Short
    short_audio_path, short_audio_dur = generate_narration(
        script_data["short"]["narration"], out, filename="narration_short.mp3"
    )
    print(f"       Short Duration: {short_audio_dur:.1f}s")

    # ── 3. Render animation ──────────────────────────────────────────────────
    print("\n[3/6] 🎨  Rendering animation slides…")
    topic["channel"] = "LearnCS Daily"   # inject channel for branding
    
    # Main Video
    anim_path = os.path.join(out, "animation.mp4")
    create_animation(script_data, topic, durations, anim_path)
    
    # YouTube Short (1080x1920 vertical)
    short_anim_path = os.path.join(out, "animation_short.mp4")
    create_short_animation(script_data, topic, short_audio_dur, short_anim_path)

    # ── 4. Assemble final videos ──────────────────────────────────────────────
    print("\n[4/6] 🎬  Assembling final videos…")
    final_path = assemble_video(anim_path, audio_path, out)
    short_final_path = assemble_video(
        short_anim_path, short_audio_path, out, 
        filename=f"final_short_{LANGUAGE}.mp4", is_short=True
    )

    # ── 5. Generate thumbnail ────────────────────────────────────────────────
    print("\n[5/6] 🖼️   Generating thumbnail…")
    thumb_path = create_thumbnail(topic, out)

    # ── 6. Upload to YouTube ─────────────────────────────────────────────────
    print("\n[6/6] 📤  Uploading to YouTube…")
    if dry_run:
        print("       [DRY RUN] Skipping YouTube upload. Using mock video ID.")
        video_id = "mock_video_id"
    else:
        # Upload Main Video
        video_id = upload_video(
            video_path=final_path,
            thumbnail_path=thumb_path,
            title=script_data["video_title"],
            description=script_data["video_description"],
            tags=script_data.get("tags", []) + topic.get("tags", []),
        )
        # Upload Short
        print("       Uploading Short to YouTube…")
        try:
            upload_video(
                video_path=short_final_path,
                thumbnail_path=None,
                title=script_data["short"]["title"],
                description=script_data["short"]["description"],
                tags=script_data["short"].get("tags", []),
            )
            print("       Short uploaded successfully!")
        except Exception as e:
            print(f"       Short upload failed: {e}")

    # ── 7. Mark as uploaded & save ───────────────────────────────────────────
    if dry_run:
        print("       [DRY RUN] Skipping curriculum.json updates.")
    else:
        mark_uploaded(curriculum, topic["id"], video_id)
        save_curriculum(curriculum)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print(f"  ✅  SUCCESS — Day {topic['day']} uploaded!")
    print(f"  🔗  https://www.youtube.com/watch?v={video_id}")
    remaining = sum(1 for t in curriculum["topics"] if not t.get("uploaded"))
    print(f"  📅  {remaining} topics remaining in the course")
    print("═" * 60 + "\n")

    # ── Optional: clean up large intermediates ───────────────────────────────
    keep_files = ["script.json", "thumbnail.jpg"]
    if dry_run:
        keep_files.append(f"final_video_{LANGUAGE}.mp4")
        keep_files.append(f"final_short_{LANGUAGE}.mp4")
    _cleanup(out, keep=keep_files)


def _cleanup(out_dir: str, keep: list[str]):
    """Remove large video intermediates to save disk space."""
    for fname in ["animation.mp4", "narration.mp3", f"final_video_{LANGUAGE}.mp4",
                  "animation_short.mp4", "narration_short.mp3", f"final_short_{LANGUAGE}.mp4"]:
        if fname not in keep:
            p = os.path.join(out_dir, fname)
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    run()
