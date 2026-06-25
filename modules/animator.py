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
from moviepy.editor import ImageClip, concatenate_videoclips, ImageSequenceClip

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


_VIGNETTE_CACHE = {}

def _get_vignette_image(width, height):
    key = (width, height)
    if key in _VIGNETTE_CACHE:
        return _VIGNETTE_CACHE[key]
    
    cx, cy = width / 2.0, height / 2.0
    x = np.linspace(0, width - 1, width)
    y = np.linspace(0, height - 1, height)
    xv, yv = np.meshgrid(x, y)
    
    rx = width / 2.0
    ry = height / 2.0
    dist = np.sqrt(((xv - cx) / rx) ** 2 + ((yv - cy) / ry) ** 2)
    
    alpha = np.zeros_like(dist)
    mask_ramp = dist > 0.35
    alpha[mask_ramp] = (dist[mask_ramp] - 0.35) / (1.0 - 0.35) * 153.0
    alpha = np.clip(alpha, 0, 153).astype(np.uint8)
    
    vignette_np = np.zeros((height, width, 4), dtype=np.uint8)
    vignette_np[:, :, 3] = alpha
    vignette = Image.fromarray(vignette_np, "RGBA")
    
    _VIGNETTE_CACHE[key] = vignette
    return vignette


def _apply_ken_burns(ref_img, width, height, progress, scale_start=1.0, scale_end=1.08):
    scale = scale_start + (scale_end - scale_start) * progress
    img_w, img_h = ref_img.size
    target_aspect = width / height
    img_aspect = img_w / img_h
    
    if img_aspect > target_aspect:
        crop_h = img_h / scale
        crop_w = crop_h * target_aspect
    else:
        crop_w = img_w / scale
        crop_h = crop_w / target_aspect
        
    cx, cy = img_w / 2.0, img_h / 2.0
    x0 = max(0.0, cx - crop_w / 2.0)
    y0 = max(0.0, cy - crop_h / 2.0)
    x1 = min(float(img_w), cx + crop_w / 2.0)
    y1 = min(float(img_h), cy + crop_h / 2.0)
    
    cropped = ref_img.crop((int(x0), int(y0), int(x1), int(y1)))
    return cropped.resize((width, height), Image.Resampling.LANCZOS)


def _apply_overlay_and_vignette(img, overlay_opacity=0.55):
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (15, 23, 42, int(255 * overlay_opacity)))
    rgba_img = Image.alpha_composite(img.convert("RGBA"), overlay)
    vignette = _get_vignette_image(w, h)
    return Image.alpha_composite(rgba_img, vignette)


def _blend_multiple_images(ref_imgs, width, height, t, seg_dur, seg_progress):
    num_images = len(ref_imgs)
    if num_images == 0:
        return None
    if num_images == 1:
        return _apply_ken_burns(ref_imgs[0], width, height, seg_progress)
        
    img_slot = seg_dur / num_images
    xfade_dur = min(1.0, img_slot * 0.3)
    
    slot_idx = int(t / img_slot)
    slot_idx = min(slot_idx, num_images - 1)
    
    t_slot = t - slot_idx * img_slot
    
    if slot_idx > 0 and t_slot < xfade_dur:
        alpha = t_slot / xfade_dur
        img_prev = _apply_ken_burns(ref_imgs[slot_idx - 1], width, height, seg_progress)
        img_curr = _apply_ken_burns(ref_imgs[slot_idx], width, height, seg_progress)
        return Image.blend(img_prev, img_curr, alpha)
    else:
        return _apply_ken_burns(ref_imgs[slot_idx], width, height, seg_progress)


def _content_slide(seg_title, all_points, show_n, code, pct, bg_img=None):
    f = _fonts()

    if bg_img:
        img = _apply_overlay_and_vignette(bg_img, overlay_opacity=0.55)
        d = ImageDraw.Draw(img)

        # Draw left card panel
        d.rounded_rectangle([80, 80, 1080, 1000], radius=24, fill=(15, 23, 42, 217), outline=(99, 102, 241, 128), width=2)

        # Title
        d.text((130, 130), seg_title, font=f["heading"], fill=(255, 255, 255, 255))
        tw = d.textbbox((0, 0), seg_title, font=f["heading"])[2]
        d.rectangle([130, 194, 130 + tw, 199], fill=(99, 102, 241, 255))

        # Bullet points
        y = 240
        text_max_w = 840
        for i, point in enumerate(all_points[:show_n]):
            is_current = i == show_n - 1
            col   = (255, 255, 255, 255) if is_current else (148, 163, 184, 255)
            b_col = (99, 102, 241, 255)  if is_current else (51, 65, 85, 255)

            # Bullet dot
            d.ellipse([130, y + 10, 150, y + 30], fill=b_col)
            y = _wrap(d, point, 170, y, f["body"] if not is_current else f["body_b"], col, text_max_w)
            y += 12

        # Code block
        if code and show_n >= len(all_points):
            _code_block(d, code, 130, y + 10, 950)

        # Paste watermark on the top right
        wm = _load_watermark()
        if wm:
            img.paste(wm, (W - wm.width - 40, 40), wm)

        _progress(d, pct)
        return np.array(img.convert("RGB"))
    else:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        _base(d, img)

        # Section heading
        d.text((80, 40), seg_title, font=f["heading"], fill=(255, 255, 255))
        tw = d.textbbox((0, 0), seg_title, font=f["heading"])[2]
        d.rectangle([80, 104, 80 + tw, 109], fill=ACCENT)

        y = 150
        text_max_w = W - 200
        for i, point in enumerate(all_points[:show_n]):
            is_current = i == show_n - 1
            col   = (255, 255, 255) if is_current else MUTED
            b_col = ACCENT            if is_current else (51, 65, 85)

            d.ellipse([80, y + 10, 100, y + 30], fill=b_col)
            y = _wrap(d, point, 120, y, f["body"] if not is_current else f["body_b"], col, text_max_w)
            y += 12

        if code and show_n >= len(all_points):
            _code_block(d, code, 80, y + 10, H - 60)

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


def _get_ai_image(prompt, out_dir, seg_idx, width=1920, height=1080):
    if not prompt:
        return None
    path = os.path.join(out_dir, f"img_{seg_idx}_{width}x{height}.png")
    if os.path.exists(path):
        try:
            return Image.open(path)
        except Exception:
            pass
    print(f"  [animator] Fetching AI image for segment {seg_idx} ({width}x{height})...")
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={width}&height={height}&nologo=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        img.save(path)
        return img
    except Exception as e:
        print(f"  [animator] Failed to fetch image: {e}")
        return None


# ── Main entry point ──────────────────────────────────────────────────────────


def create_animation(script_data: dict, topic: dict,
                     durations: dict, output_path: str) -> str:
    """
    Build a silent MP4 timed to matches individual section audio durations perfectly.
    Returns the path to the rendered video file.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    segments   = script_data.get("segments") or script_data.get("slides") or script_data.get("sections") or []
    summary_block = script_data.get("summary") or script_data.get("takeaways") or {}
    summary    = summary_block.get("points") or summary_block.get("key_points") or script_data.get("summary_points") or []
    outro_block = script_data.get("outro") or script_data.get("conclusion") or {}
    next_topic = outro_block.get("next_topic") or script_data.get("next_topic") or ""
    quiz       = script_data.get("quiz") or script_data.get("pop_quiz") or {}

    total_duration = (
        durations["intro"] +
        sum(durations["segments"]) +
        durations["quiz"] +
        durations["summary"] +
        durations["outro"]
    )

    clips = []
    elapsed = 0.0
    fps = 24

    # Temp base directory for all segment frames
    temp_base_dir = os.path.join(os.path.dirname(output_path), "temp_frames")
    os.makedirs(temp_base_dir, exist_ok=True)

    # ── Intro ──
    intro_dur = durations["intro"]
    frame = _title_slide(topic, elapsed / total_duration)
    clips.append(ImageClip(frame, duration=intro_dur))
    elapsed += intro_dur

    # ── Content ──
    for seg_idx, seg in enumerate(segments):
        seg_dur = durations["segments"][seg_idx] if (durations.get("segments") and seg_idx < len(durations["segments"])) else 40.0
        points  = seg.get("points") or seg.get("point") or seg.get("key_points") or seg.get("bullet_points") or []
        code    = seg.get("code")
        prompts = seg.get("image_prompts") or [seg.get("image_prompt") or seg.get("visual_prompt") or seg.get("image")]
        prompts = [p for p in prompts if p]
        
        ref_imgs = []
        for p_idx, prompt in enumerate(prompts):
            img_id = f"{seg_idx}_{p_idx}"
            img = _get_ai_image(prompt, os.path.dirname(output_path), img_id, width=1920, height=1080)
            if img:
                ref_imgs.append(img)
                
        n       = max(len(points), 1)
        pt_dur  = seg_dur / n

        total_seg_frames = int(seg_dur * fps)
        if total_seg_frames > 0:
            segment_frames = []
            seg_temp_dir = os.path.join(temp_base_dir, f"seg_{seg_idx}")
            os.makedirs(seg_temp_dir, exist_ok=True)

            for f in range(total_seg_frames):
                t = f / fps
                seg_progress = f / max(total_seg_frames - 1, 1)
                show_n = int(t / pt_dur) + 1
                show_n = min(show_n, n)
                
                # Dynamic crossfaded background
                bg_img = _blend_multiple_images(ref_imgs, W, H, t, seg_dur, seg_progress)
                
                pct = (elapsed + t) / total_duration
                frame = _content_slide(seg.get("title", ""), points, show_n, code, pct, bg_img)
                
                # Save to disk to avoid out-of-memory errors
                frame_path = os.path.join(seg_temp_dir, f"frame_{f:05d}.jpg")
                Image.fromarray(frame).save(frame_path, "JPEG", quality=90)
                segment_frames.append(frame_path)
                
            clips.append(ImageSequenceClip(segment_frames, fps=fps))
        else:
            # Fallback if duration is 0
            pct = elapsed / total_duration
            bg_img = _blend_multiple_images(ref_imgs, W, H, 0.0, seg_dur, 0.0)
            frame = _content_slide(seg.get("title", ""), points, n, code, pct, bg_img)
            clips.append(ImageClip(frame, duration=seg_dur))
            
        elapsed += seg_dur

    # ── Interactive Pop Quiz ──
    if quiz:
        quiz_dur = durations["quiz"]
        countdown_dur = 5.0 if quiz_dur >= 10.0 else quiz_dur * 0.5
        reveal_dur = (quiz_dur - countdown_dur) if quiz_dur >= 10.0 else quiz_dur * 0.5
        
        # Countdown: render 5 distinct frames to animate timer bar
        steps = 5
        step_dur = countdown_dur / steps
        for i in range(steps):
            timer_pct = (steps - i) / steps
            pct = elapsed / total_duration
            frame = _quiz_slide(quiz, show_answer=False, timer_pct=timer_pct, pct=pct)
            clips.append(ImageClip(frame, duration=step_dur))
            elapsed += step_dur
            
        # Answer reveal: show the correct answer and the explanation
        pct = elapsed / total_duration
        frame = _quiz_slide(quiz, show_answer=True, timer_pct=0.0, pct=pct)
        clips.append(ImageClip(frame, duration=reveal_dur))
        elapsed += reveal_dur

    # ── Summary ──
    summary_dur = durations["summary"]
    frame = _summary_slide(topic["title"], summary, elapsed / total_duration)
    clips.append(ImageClip(frame, duration=summary_dur))
    elapsed += summary_dur

    # ── Outro ──
    outro_dur = durations["outro"]
    frame = _outro_slide(next_topic, 1.0)
    clips.append(ImageClip(frame, duration=outro_dur))

    # Concatenate and write
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio=False,
        threads=4,
        logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"]
    )
    
    # Close clips to release files/resources
    video.close()
    for clip in clips:
        clip.close()
        
    # Clean up temp frames directory
    import shutil
    shutil.rmtree(temp_base_dir, ignore_errors=True)
    
    return output_path


def _short_frame(phrase, bg_img, pct, timer_pct):
    SW, SH = 1080, 1920
    f = _fonts()

    if bg_img:
        img = _apply_overlay_and_vignette(bg_img, overlay_opacity=0.65)
        d = ImageDraw.Draw(img)

        # Centered Watermark Logo near the top
        wm = _load_watermark()
        if wm:
            w_w = int(wm.width * 1.5)
            w_h = int(wm.height * 1.5)
            wm_resized = wm.resize((w_w, w_h), Image.Resampling.LANCZOS)
            img.paste(wm_resized, ((SW - w_w) // 2, 100), wm_resized)

        # Draw Large Centered Text Card on the bottom half
        card_y = 1180
        card_w = 920
        card_h = 500
        card_x = (SW - card_w) // 2

        d.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=20, fill=(20, 28, 50, 230), outline=(99, 102, 241, 255), width=3)

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
            d.text((card_x + (card_w - line_w) // 2, start_y), line, font=short_font, fill=(255, 255, 255, 255))
            start_y += lh

        # Draw a bottom progress bar
        prog_w = SW - 160
        prog_h = 10
        prog_y = SH - 100
        d.rounded_rectangle([80, prog_y, 80 + prog_w, prog_y + prog_h], radius=5, fill=(30, 41, 59, 255))
        d.rounded_rectangle([80, prog_y, 80 + int(prog_w * timer_pct), prog_y + prog_h], radius=5, fill=(99, 102, 241, 255))

        return np.array(img.convert("RGB"))
    else:
        img = Image.new("RGB", (SW, SH), BG)
        d = ImageDraw.Draw(img)

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
    prompts    = short_data.get("image_prompts") or [short_data.get("image_prompt")]
    prompts    = [p for p in prompts if p]

    # Split narration into 3-4 semantic chunks/phrases
    raw_phrases = [p.strip() for p in re.split(r'[.!?।]', narration) if p.strip()]
    if not raw_phrases:
        raw_phrases = [narration]

    # Download AI images for the short (vertical format 1080x1920)
    short_imgs = []
    for p_idx, prompt in enumerate(prompts):
        img_id = f"short_{p_idx}"
        img = _get_ai_image(prompt, os.path.dirname(output_path), img_id, width=1080, height=1920)
        if img:
            short_imgs.append(img)

    n = len(raw_phrases)
    phrase_dur = audio_duration / n
    fps = 24

    total_short_frames = int(audio_duration * fps)
    temp_dir = os.path.join(os.path.dirname(output_path), "temp_short_frames")
    
    if total_short_frames > 0:
        short_frames = []
        os.makedirs(temp_dir, exist_ok=True)
        
        for f in range(total_short_frames):
            t = f / fps
            short_progress = f / max(total_short_frames - 1, 1)
            
            phrase_idx = int(t / phrase_dur)
            phrase_idx = min(phrase_idx, n - 1)
            phrase = raw_phrases[phrase_idx]
            
            timer_pct = min(t / audio_duration, 1.0)
            
            # Dynamic crossfaded background
            bg_img = _blend_multiple_images(short_imgs, 1080, 1920, t, audio_duration, short_progress)
            
            frame = _short_frame(phrase, bg_img, timer_pct, timer_pct)
            
            # Save to disk to avoid out-of-memory errors
            frame_path = os.path.join(temp_dir, f"frame_{f:05d}.jpg")
            Image.fromarray(frame).save(frame_path, "JPEG", quality=90)
            short_frames.append(frame_path)
            
        clips = [ImageSequenceClip(short_frames, fps=fps)]
    else:
        # Fallback
        bg_img = _blend_multiple_images(short_imgs, 1080, 1920, 0.0, audio_duration, 0.0)
        frame = _short_frame(narration, bg_img, 1.0, 1.0)
        clips = [ImageClip(frame, duration=audio_duration)]

    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio=False,
        threads=4,
        logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"]
    )
    
    video.close()
    for clip in clips:
        clip.close()
        
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    return output_path
