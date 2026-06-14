"""
modules/animator.py
Generates a styled silent MP4 animation from the script data.
Uses Pillow for frame rendering and MoviePy for video assembly.
No heavy 3D renderer needed — clean dark-theme slide animations.
"""
import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips

# ── Palette ─────────────────────────────────────────────────────────────────
BG       = (15, 20, 40)
ACCENT   = (99, 102, 241)
TEXT     = (226, 232, 240)
MUTED    = (148, 163, 184)
CODE_BG  = (30, 41, 59)
GREEN    = (34, 197, 94)
AMBER    = (250, 204, 21)
W, H     = 1920, 1080


# ── Font loader ──────────────────────────────────────────────────────────────
def _load_fonts():
    """Try DejaVu (always on Ubuntu/GitHub Actions), fall back to default."""
    paths = [
        "/usr/share/fonts/truetype/dejavu/",
        "/usr/share/fonts/truetype/liberation/",
        "/usr/share/fonts/",
        "C:/Windows/Fonts/",
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts") + "/",
    ]
    families = {
        "bold":  ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf", "seguib.ttf"],
        "regular": ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "arial.ttf", "segoeui.ttf"],
        "mono":  ["DejaVuSansMono.ttf", "LiberationMono-Regular.ttf", "consola.ttf", "cour.ttf"],
        "mono_bold": ["DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf", "consolab.ttf", "courbd.ttf"],
    }

    def try_load(family_keys, size):
        for fam in family_keys:
            for p in paths:
                try:
                    return ImageFont.truetype(os.path.join(p, fam), size)
                except Exception:
                    pass
        return ImageFont.load_default()

    return {
        "title":   try_load(families["bold"], 68),
        "heading": try_load(families["bold"], 50),
        "body":    try_load(families["regular"], 34),
        "body_b":  try_load(families["bold"], 34),
        "code":    try_load(families["mono"], 28),
        "code_b":  try_load(families["mono_bold"], 28),
        "small":   try_load(families["regular"], 22),
        "badge":   try_load(families["bold"], 20),
    }


FONTS = None  # Loaded lazily


def _fonts():
    global FONTS
    if FONTS is None:
        FONTS = _load_fonts()
    return FONTS


# ── Drawing helpers ───────────────────────────────────────────────────────────
def _base(draw):
    """Draw gradient background + top accent bar."""
    for y in range(H):
        shade = int(y / H * 8)
        draw.line([(0, y), (W, y)], fill=(BG[0]+shade, BG[1]+shade+3, BG[2]+shade+5))
    draw.rectangle([0, 0, W, 7], fill=ACCENT)


def _progress(draw, pct):
    draw.rectangle([0, H-5, W, H], fill=(30, 41, 59))
    draw.rectangle([0, H-5, int(W * pct), H], fill=ACCENT)


def _wrap(draw, text, x, y, font, color, max_w):
    """Word-wrap text, return final y."""
    lh = font.size + 10
    words = text.split()
    line = []
    for word in words:
        line.append(word)
        bb = draw.textbbox((0, 0), " ".join(line), font=font)
        if bb[2] > max_w and len(line) > 1:
            line.pop()
            draw.text((x, y), " ".join(line), font=font, fill=color)
            y += lh
            line = [word]
    if line:
        draw.text((x, y), " ".join(line), font=font, fill=color)
        y += lh
    return y


def _code_block(draw, code, x, y, max_h):
    """Render a syntax-highlighted code block."""
    f = _fonts()
    lines = (code or "").split("\n")[:8]
    bh = min(len(lines) * 38 + 44, max_h - y - 20)
    bw = W - x - 80

    draw.rounded_rectangle([x, y, x+bw, y+bh], radius=8, fill=CODE_BG)
    draw.rounded_rectangle([x, y, x+bw, y+38], radius=8, fill=(51, 65, 85))
    draw.text((x+16, y+10), "● code", font=f["small"], fill=MUTED)

    cy = y + 44
    keywords = {"def", "class", "import", "from", "return", "if", "else",
                "elif", "for", "while", "in", "not", "and", "or", "True",
                "False", "None", "pass", "break", "continue", "lambda"}
    for line in lines:
        if line.strip().startswith("#"):
            draw.text((x+16, cy), line, font=f["code"], fill=(107, 174, 91))
        elif any(f'"{w}' in line or f"'{w}" in line for w in ["", " "]):
            draw.text((x+16, cy), line, font=f["code"], fill=(206, 145, 120))
        else:
            # Token-level keyword highlight
            tokens = line.split()
            tx = x + 16
            full_line = line
            draw.text((tx, cy), full_line, font=f["code"], fill=(212, 212, 212))
        cy += 38


# ── Slide types ───────────────────────────────────────────────────────────────
def _title_slide(topic, pct):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _base(d)
    f = _fonts()

    # Day badge
    d.rounded_rectangle([80, 60, 210, 100], radius=20, fill=ACCENT)
    d.text((97, 68), f"DAY {topic['day']}", font=f["badge"], fill=(255, 255, 255))

    # Module label
    d.text((80, 120), topic["module"].upper(), font=f["small"], fill=ACCENT)

    # Title — large, centered vertically
    cy = H // 2 - 60
    cy = _wrap(d, topic["title"], 80, cy, f["title"], (255, 255, 255), W - 160)

    # Decorative bar
    d.rectangle([80, cy + 16, 80 + 120, cy + 22], fill=ACCENT)

    # Tagline
    d.text((80, cy + 40), f"5-minute lesson  ·  {topic['level']} level", font=f["body"], fill=MUTED)

    # Channel
    d.text((80, H - 60), f"🖥  {topic.get('channel', 'LearnCS Daily')}", font=f["small"], fill=ACCENT)

    _progress(d, pct)
    return np.array(img)


def _content_slide(seg_title, all_points, show_n, code, pct):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _base(d)
    f = _fonts()

    # Section heading
    d.text((80, 40), seg_title, font=f["heading"], fill=(255, 255, 255))
    tw = d.textbbox((0, 0), seg_title, font=f["heading"])[2]
    d.rectangle([80, 104, 80 + tw, 109], fill=ACCENT)

    # Bullet points
    y = 150
    for i, point in enumerate(all_points[:show_n]):
        is_current = i == show_n - 1
        col   = (255, 255, 255) if is_current else MUTED
        b_col = ACCENT            if is_current else (51, 65, 85)

        # Bullet dot
        d.ellipse([80, y + 10, 100, y + 30], fill=b_col)
        y = _wrap(d, point, 120, y, f["body"] if not is_current else f["body_b"],
                  col, W - 200)
        y += 12

    # Code block if it's the last point revealed
    if code and show_n >= len(all_points):
        _code_block(d, code, 80, y + 10, H - 60)

    _progress(d, pct)
    return np.array(img)


def _summary_slide(title, points, pct):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _base(d)
    f = _fonts()

    d.text((80, 40), "📋  Key Takeaways", font=f["heading"], fill=(255, 255, 255))
    d.rectangle([80, 104, 80 + 300, 109], fill=GREEN)

    y = 155
    for i, pt in enumerate(points[:5]):
        # Number badge
        d.ellipse([80, y, 114, y + 34], fill=ACCENT)
        d.text((91, y + 5), str(i + 1), font=f["badge"], fill=(255, 255, 255))
        y = _wrap(d, pt, 130, y, f["body_b"], TEXT, W - 200)
        y += 18

    _progress(d, pct)
    return np.array(img)


def _outro_slide(next_topic, pct):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _base(d)
    f = _fonts()

    cy = H // 2 - 90
    d.text((80, cy),       "Thanks for watching!", font=f["heading"], fill=(255, 255, 255))
    d.text((80, cy + 72),  "🔔  Subscribe for daily CS lessons", font=f["body_b"], fill=ACCENT)
    d.text((80, cy + 130), "👍  Like if this helped", font=f["body"], fill=MUTED)

    if next_topic:
        d.rectangle([80, cy + 195, W - 80, cy + 197], fill=(51, 65, 85))
        d.text((80, cy + 210), "Next →", font=f["small"], fill=MUTED)
        d.text((80, cy + 240), next_topic, font=f["body_b"], fill=(255, 255, 255))

    _progress(d, 1.0)
    return np.array(img)


# ── Main entry point ──────────────────────────────────────────────────────────
def create_animation(script_data: dict, topic: dict,
                     audio_duration: float, output_path: str) -> str:
    """
    Build a silent MP4 timed to audio_duration.
    Returns the path to the rendered video file.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    segments   = script_data.get("segments", [])
    summary    = script_data.get("summary_points", [])
    next_topic = script_data.get("next_topic", "")

    INTRO_DUR  = 10
    OUTRO_DUR  = 12
    SUMM_DUR   = 12
    content_dur = max(audio_duration - INTRO_DUR - OUTRO_DUR - SUMM_DUR, 60)

    # Distribute time across segments proportionally
    raw_totals = [s.get("duration_seconds", 40) for s in segments]
    total_raw  = sum(raw_totals) or len(segments) * 40
    scale      = content_dur / total_raw

    clips = []
    elapsed = 0.0

    # ── Intro ──
    frame = _title_slide(topic, elapsed / audio_duration)
    clips.append(ImageClip(frame, duration=INTRO_DUR))
    elapsed += INTRO_DUR

    # ── Content ──
    for seg, raw_dur in zip(segments, raw_totals):
        seg_dur = raw_dur * scale
        points  = seg.get("points", [])
        code    = seg.get("code")
        n       = max(len(points), 1)
        pt_dur  = seg_dur / n

        for i in range(1, n + 1):
            pct   = elapsed / audio_duration
            frame = _content_slide(seg.get("title", ""), points, i, code, pct)
            clips.append(ImageClip(frame, duration=pt_dur))
            elapsed += pt_dur

    # ── Summary ──
    frame = _summary_slide(topic["title"], summary, elapsed / audio_duration)
    clips.append(ImageClip(frame, duration=SUMM_DUR))
    elapsed += SUMM_DUR

    # ── Outro ──
    frame = _outro_slide(next_topic, 1.0)
    clips.append(ImageClip(frame, duration=OUTRO_DUR))

    # Concatenate and write
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio=False,
        threads=4,
        logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast"]
    )
    return output_path
