"""
modules/animator.py
Generates a styled silent MP4 animation from the script data.
Uses Pillow for frame rendering and MoviePy for video assembly.
No heavy 3D renderer needed — clean dark-theme slide animations.
"""
import os
import io
import math
import requests
import urllib.parse
import re
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
    """Load Poppins fonts if available, else fallback to system fonts."""
    fonts_dir = "fonts"
    def try_load_file(filename, size):
        path = os.path.join(fonts_dir, filename)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return None

    poppins_reg = try_load_file("Poppins-Regular.ttf", 34)
    if poppins_reg:
        return {
            "title":   ImageFont.truetype(os.path.join(fonts_dir, "Poppins-Bold.ttf"), 68),
            "heading": ImageFont.truetype(os.path.join(fonts_dir, "Poppins-Bold.ttf"), 50),
            "body":    ImageFont.truetype(os.path.join(fonts_dir, "Poppins-Regular.ttf"), 34),
            "body_b":  ImageFont.truetype(os.path.join(fonts_dir, "Poppins-SemiBold.ttf"), 34),
            "code":    ImageFont.truetype(os.path.join(fonts_dir, "Poppins-Regular.ttf"), 28),
            "code_b":  ImageFont.truetype(os.path.join(fonts_dir, "Poppins-SemiBold.ttf"), 28),
            "small":   ImageFont.truetype(os.path.join(fonts_dir, "Poppins-Regular.ttf"), 22),
            "badge":   ImageFont.truetype(os.path.join(fonts_dir, "Poppins-Bold.ttf"), 20),
        }

    # Fallback to system fonts
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


WATERMARK_IMG = None

def _load_watermark():
    global WATERMARK_IMG
    if WATERMARK_IMG is None:
        if os.path.exists("watermark.png"):
            WATERMARK_IMG = Image.open("watermark.png").convert("RGBA")
            aspect = WATERMARK_IMG.width / WATERMARK_IMG.height
            WATERMARK_IMG = WATERMARK_IMG.resize((int(80 * aspect), 80), Image.Resampling.LANCZOS)
            # Add transparency (opacity 0.7)
            alpha = WATERMARK_IMG.getchannel('A')
            WATERMARK_IMG.putalpha(alpha.point(lambda i: int(i * 0.7)))
        else:
            WATERMARK_IMG = False
    return WATERMARK_IMG

# ── Drawing helpers ───────────────────────────────────────────────────────────
def _base(draw, img=None):
    """Draw gradient background + top accent bar."""
    for y in range(H):
        shade = int(y / H * 8)
        draw.line([(0, y), (W, y)], fill=(BG[0]+shade, BG[1]+shade+3, BG[2]+shade+5))
    draw.rectangle([0, 0, W, 7], fill=ACCENT)
    
    if img:
        wm = _load_watermark()
        if wm:
            img.paste(wm, (W - wm.width - 40, 40), wm)


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
    _base(d, img)
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


def _content_slide(seg_title, all_points, show_n, code, pct, ref_img=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _base(d, img)
    f = _fonts()

    # Section heading
    d.text((80, 40), seg_title, font=f["heading"], fill=(255, 255, 255))
    tw = d.textbbox((0, 0), seg_title, font=f["heading"])[2]
    d.rectangle([80, 104, 80 + tw, 109], fill=ACCENT)

    # If there's an image, text takes up 900px, otherwise W - 200
    text_max_w = 800 if ref_img else W - 200

    # Bullet points
    y = 150
    for i, point in enumerate(all_points[:show_n]):
        is_current = i == show_n - 1
        col   = (255, 255, 255) if is_current else MUTED
        b_col = ACCENT            if is_current else (51, 65, 85)

        # Bullet dot
        d.ellipse([80, y + 10, 100, y + 30], fill=b_col)
        y = _wrap(d, point, 120, y, f["body"] if not is_current else f["body_b"],
                  col, text_max_w)
        y += 12

    # Code block if it's the last point revealed
    if code and show_n >= len(all_points):
        _code_block(d, code, 80, y + 10, H - 60)

    # Reference image
    if ref_img and show_n >= len(all_points) // 2:
        # Paste image on the right side
        ix = W - ref_img.width - 80
        iy = (H - ref_img.height) // 2
        img.paste(ref_img, (ix, iy), ref_img)

    _progress(d, pct)
    return np.array(img)


def _summary_slide(title, points, pct):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _base(d, img)
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
    _base(d, img)
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


def _quiz_slide(quiz_data, show_answer, timer_pct, pct):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _base(d, img)
    f = _fonts()

    # Section heading
    d.text((80, 40), "❓ Pop Quiz (क्विज़)", font=f["heading"], fill=(255, 255, 255))
    d.rectangle([80, 104, 80 + 350, 109], fill=ACCENT)

    # Draw Question
    y = 150
    y = _wrap(d, quiz_data["question"], 80, y, f["title"] if len(quiz_data["question"]) < 60 else f["heading"], (255, 255, 255), W - 160)
    y += 40

    # Draw Options (2x2 grid)
    opt_w, opt_h = 800, 120
    correct_opt = quiz_data.get("correct_answer", "").strip().upper() # "A", "B", "C", "D"

    for idx, opt in enumerate(quiz_data["options"]):
        # Determine grid position
        row = idx // 2
        col = idx % 2
        ox = 80 if col == 0 else (W // 2 + 20)
        oy = y + row * (opt_h + 30)

        # Get option letter
        opt_letter = opt.strip()[0].upper() # "A", "B", "C", "D"
        
        bg_color = CODE_BG
        border_color = MUTED
        text_color = TEXT

        if show_answer:
            if opt_letter == correct_opt:
                bg_color = (22, 101, 52) # Dark green
                border_color = GREEN
                text_color = (255, 255, 255)
            else:
                bg_color = (20, 25, 45) # Faded
                border_color = (40, 50, 75)
                text_color = MUTED

        d.rounded_rectangle([ox, oy, ox + opt_w, oy + opt_h], radius=12, fill=bg_color, outline=border_color, width=2)
        d.text((ox + 30, oy + (opt_h - f["body"].size) // 2), opt, font=f["body_b"] if (show_answer and opt_letter == correct_opt) else f["body"], fill=text_color)

    # Timer or Explanation section at the bottom
    bottom_y = H - 240
    if not show_answer:
        # Draw Countdown Timer Bar
        timer_w = W - 160
        timer_h = 16
        # Draw outline
        d.rounded_rectangle([80, bottom_y, 80 + timer_w, bottom_y + timer_h], radius=8, fill=(30, 41, 59))
        # Draw fill (shrinks based on timer_pct)
        fill_w = int(timer_w * timer_pct)
        if fill_w > 0:
            d.rounded_rectangle([80, bottom_y, 80 + fill_w, bottom_y + timer_h], radius=8, fill=ACCENT)
        
        # Display instructions in English or Hindi
        from config import LANGUAGE
        hint_text = "Choose your answer in the comments! (कमेंट्स में अपना जवाब दें!)" if LANGUAGE == "hi" else f"Choose your answer in the comments! (Remaining: {int(5 * timer_pct) + 1}s)"
        d.text((80, bottom_y - 40), hint_text, font=f["small"], fill=MUTED)
    else:
        # Draw Explanation
        d.rounded_rectangle([80, bottom_y, W - 80, bottom_y + 130], radius=12, fill=(30, 41, 59), outline=GREEN, width=1)
        d.text((100, bottom_y + 15), "Explanation (स्पष्टीकरण):", font=f["badge"], fill=GREEN)
        _wrap(d, quiz_data["explanation"], 100, bottom_y + 45, f["small"], TEXT, W - 200)

    _progress(d, pct)
    return np.array(img)


def _get_ai_image(prompt, out_dir, seg_idx):
    if not prompt:
        return None
    path = os.path.join(out_dir, f"img_{seg_idx}.png")
    if os.path.exists(path):
        return Image.open(path)
    print(f"  [animator] Fetching AI image for segment {seg_idx}...")
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=800&height=600&nologo=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        
        # Round corners
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, img.size[0], img.size[1]], radius=20, fill=255)
        img.putalpha(mask)
        
        img.save(path)
        return img
    except Exception as e:
        print(f"  [animator] Failed to fetch image: {e}")
        return None


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
    quiz       = script_data.get("quiz", {})

    INTRO_DUR  = 10
    OUTRO_DUR  = 12
    SUMM_DUR   = 12
    QUIZ_DUR   = 10  # 5s countdown + 5s answer reveal
    
    content_dur = max(audio_duration - INTRO_DUR - OUTRO_DUR - SUMM_DUR - QUIZ_DUR, 60)

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
    for seg_idx, (seg, raw_dur) in enumerate(zip(segments, raw_totals)):
        seg_dur = raw_dur * scale
        points  = seg.get("points", [])
        code    = seg.get("code")
        prompt  = seg.get("image_prompt")
        n       = max(len(points), 1)
        pt_dur  = seg_dur / n
        
        ref_img = _get_ai_image(prompt, os.path.dirname(output_path), seg_idx)

        for i in range(1, n + 1):
            pct   = elapsed / audio_duration
            frame = _content_slide(seg.get("title", ""), points, i, code, pct, ref_img)
            clips.append(ImageClip(frame, duration=pt_dur))
            elapsed += pt_dur

    # ── Interactive Pop Quiz ──
    if quiz:
        # 5 seconds countdown: render 5 distinct frames (one for each second) to animate timer bar
        for i in range(5):
            timer_pct = (5 - i) / 5
            pct = elapsed / audio_duration
            frame = _quiz_slide(quiz, show_answer=False, timer_pct=timer_pct, pct=pct)
            clips.append(ImageClip(frame, duration=1.0))
            elapsed += 1.0
            
        # 5 seconds answer reveal: show the correct answer and the explanation
        pct = elapsed / audio_duration
        frame = _quiz_slide(quiz, show_answer=True, timer_pct=0.0, pct=pct)
        clips.append(ImageClip(frame, duration=5.0))
        elapsed += 5.0

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
        ffmpeg_params=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"]
    )
    return output_path


def _short_frame(phrase, short_img, pct, timer_pct):
    SW, SH = 1080, 1920
    img = Image.new("RGB", (SW, SH), BG)
    d = ImageDraw.Draw(img)
    f = _fonts()

    # Draw vertical gradient background
    for y in range(SH):
        shade = int(y / SH * 12)
        d.line([(0, y), (SW, y)], fill=(BG[0]+shade, BG[1]+shade+3, BG[2]+shade+5))
    d.rectangle([0, 0, SW, 12], fill=ACCENT)

    # Centered Watermark Logo near the top
    wm = _load_watermark()
    if wm:
        w_w = int(wm.width * 1.5)
        w_h = int(wm.height * 1.5)
        wm_resized = wm.resize((w_w, w_h), Image.Resampling.LANCZOS)
        img.paste(wm_resized, ((SW - w_w) // 2, 100), wm_resized)

    # Draw short visual image
    if short_img:
        iw = 920
        aspect = short_img.width / short_img.height
        ih = int(iw / aspect)
        if ih > 800:
            ih = 800
            iw = int(ih * aspect)
        
        short_img_resized = short_img.resize((iw, ih), Image.Resampling.LANCZOS)
        
        mask = Image.new("L", (iw, ih), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle([0, 0, iw, ih], radius=24, fill=255)
        short_img_resized.putalpha(mask)

        img.paste(short_img_resized, ((SW - iw) // 2, 320), short_img_resized)

    # Draw Large Centered Text Card on the bottom half
    card_y = 1180
    card_w = 920
    card_h = 500
    card_x = (SW - card_w) // 2
    
    d.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=20, fill=(20, 28, 50), outline=ACCENT, width=3)
    
    short_font = ImageFont.truetype("fonts/Poppins-Bold.ttf", 46) if os.path.exists("fonts/Poppins-Bold.ttf") else f["heading"]
    
    lh = short_font.size + 15
    words = phrase.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        bb = d.textbbox((0, 0), " ".join(current_line), font=short_font)
        if bb[2] > card_w - 80 and len(current_line) > 1:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    total_text_h = len(lines) * lh
    start_y = card_y + (card_h - total_text_h) // 2
    for line in lines:
        bb = d.textbbox((0, 0), line, font=short_font)
        line_w = bb[2]
        d.text((card_x + (card_w - line_w) // 2, start_y), line, font=short_font, fill=(255, 255, 255))
        start_y += lh

    # Draw a bottom progress bar
    prog_w = SW - 160
    prog_h = 10
    prog_y = SH - 100
    d.rounded_rectangle([80, prog_y, 80 + prog_w, prog_y + prog_h], radius=5, fill=(30, 41, 59))
    d.rounded_rectangle([80, prog_y, 80 + int(prog_w * timer_pct), prog_y + prog_h], radius=5, fill=ACCENT)

    return np.array(img)


def create_short_animation(script_data: dict, topic: dict,
                           audio_duration: float, output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    short_data = script_data.get("short", {})
    narration  = short_data.get("narration", "")
    prompt     = short_data.get("image_prompt", "")

    # Split narration into 3-4 semantic chunks/phrases
    raw_phrases = [p.strip() for p in re.split(r'[.!?।]', narration) if p.strip()]
    if not raw_phrases:
        raw_phrases = [narration]

    # Download AI image for the short
    ref_img = _get_ai_image(prompt, os.path.dirname(output_path), "short")

    n = len(raw_phrases)
    phrase_dur = audio_duration / n

    clips = []
    elapsed = 0.0

    for idx, phrase in enumerate(raw_phrases):
        for f_idx in range(3):
            sub_pct = (f_idx + 1) / 3
            current_elapsed = elapsed + (sub_pct * phrase_dur)
            timer_pct = min(current_elapsed / audio_duration, 1.0)
            
            frame = _short_frame(phrase, ref_img, timer_pct, timer_pct)
            clips.append(ImageClip(frame, duration=phrase_dur / 3))
        
        elapsed += phrase_dur

    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio=False,
        threads=4,
        logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"]
    )
    return output_path
