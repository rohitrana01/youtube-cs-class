"""
modules/animator.py
Generates a styled silent MP4 animation from the script data.
Uses Pillow for frame rendering and MoviePy for video assembly.
Downloads public domain, educational images from Wikimedia Commons for hardware visual aids.
"""
import os
import io
import re
import urllib.parse
import requests
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
    for line in lines:
        if line.strip().startswith("#"):
            draw.text((x+16, cy), line, font=f["code"], fill=(107, 174, 91))
        elif any(f'"{w}' in line or f"'{w}" in line for w in ["", " "]):
            draw.text((x+16, cy), line, font=f["code"], fill=(206, 145, 120))
        else:
            tx = x + 16
            draw.text((tx, cy), line, font=f["code"], fill=(212, 212, 212))
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
    text_max_w = 900 if ref_img else W - 200

    y = 150
    for i, point in enumerate(all_points[:show_n]):
        is_current = i == show_n - 1
        col   = (255, 255, 255) if is_current else MUTED
        b_col = ACCENT            if is_current else (51, 65, 85)

        d.ellipse([80, y + 10, 100, y + 30], fill=b_col)
        y = _wrap(d, point, 120, y, f["body"] if not is_current else f["body_b"], col, text_max_w)
        y += 12

    if code and show_n >= len(all_points):
        _code_block(d, code, 80, y + 10, H - 60)

    # Reference image on the right side
    if ref_img:
        max_iw = 800
        max_ih = 750
        
        iw, ih = ref_img.size
        aspect = iw / ih
        if iw > max_iw or ih > max_ih:
            if aspect > (max_iw / max_ih):
                new_w = max_iw
                new_h = int(new_w / aspect)
            else:
                new_h = max_ih
                new_w = int(new_h * aspect)
        else:
            new_w = iw
            new_h = ih
            
        ref_img_resized = ref_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        mask = Image.new("L", (new_w, new_h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle([0, 0, new_w, new_h], radius=24, fill=255)
        
        ix = 1040 + (max_iw - new_w) // 2
        iy = 130 + (max_ih - new_h) // 2
        
        d.rounded_rectangle([ix - 4, iy - 4, ix + new_w + 4, iy + new_h + 4], radius=28, fill=None, outline=ACCENT, width=3)
        img.paste(ref_img_resized, (ix, iy), mask)

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
    correct_opt = quiz_data.get("correct_answer", "").strip().upper()

    for idx, opt in enumerate(quiz_data["options"]):
        row = idx // 2
        col = idx % 2
        ox = 80 if col == 0 else (W // 2 + 20)
        oy = y + row * (opt_h + 30)

        opt_letter = opt.strip()[0].upper()
        
        bg_color = CODE_BG
        border_color = MUTED
        text_color = TEXT

        if show_answer:
            if opt_letter == correct_opt:
                bg_color = (22, 101, 52)
                border_color = GREEN
                text_color = (255, 255, 255)
            else:
                bg_color = (20, 25, 45)
                border_color = (40, 50, 75)
                text_color = MUTED

        d.rounded_rectangle([ox, oy, ox + opt_w, oy + opt_h], radius=12, fill=bg_color, outline=border_color, width=2)
        d.text((ox + 30, oy + (opt_h - f["body"].size) // 2), opt, font=f["body_b"] if (show_answer and opt_letter == correct_opt) else f["body"], fill=text_color)

    bottom_y = H - 240
    if not show_answer:
        timer_w = W - 160
        timer_h = 16
        d.rounded_rectangle([80, bottom_y, 80 + timer_w, bottom_y + timer_h], radius=8, fill=(30, 41, 59))
        fill_w = int(timer_w * timer_pct)
        if fill_w > 0:
            d.rounded_rectangle([80, bottom_y, 80 + fill_w, bottom_y + timer_h], radius=8, fill=ACCENT)
        
        from config import LANGUAGE
        hint_text = "Choose your answer in the comments! (कमेंट्स में अपना जवाब दें!)" if LANGUAGE == "hi" else f"Choose your answer in the comments! (Remaining: {int(5 * timer_pct) + 1}s)"
        d.text((80, bottom_y - 40), hint_text, font=f["small"], fill=MUTED)
    else:
        d.rounded_rectangle([80, bottom_y, W - 80, bottom_y + 130], radius=12, fill=(30, 41, 59), outline=GREEN, width=1)
        d.text((100, bottom_y + 15), "Explanation (स्पष्टीकरण):", font=f["badge"], fill=GREEN)
        _wrap(d, quiz_data["explanation"], 100, bottom_y + 45, f["small"], TEXT, W - 200)

    _progress(d, pct)
    return np.array(img)


# ── Wikimedia Commons API Integration ──────────────────────────────────────────

def clean_prompt_to_keyword(prompt):
    if not prompt:
        return ""
    cleaned = re.sub(
        r'^(an?\s+)?(ultra-)?realistic\s+(photograph|photo|3d\s+digital\s+render|render|illustration|drawing|image|close-up)\s+(of|showing)\s+a?\s*',
        '', prompt, flags=re.IGNORECASE
    )
    cleaned = re.sub(r'^(a\s+close-up,\s+ultra-realistic\s+photograph\s+of\s+a?|a\s+close-up\s+photograph\s+of\s+a?)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^a\s+', '', cleaned, flags=re.IGNORECASE)
    
    splitters = [r'\s+with\b', r'\s+showing\b', r'\s+highlighting\b', r'\s+acting\b', r'\s+on\b', r'\s+implying\b', r'\s+for\b', r'\s+indicating\b', r'\s+symbolizing\b', r'\bshowing\b', r',', r'\(']
    pattern = '|'.join(splitters)
    parts = re.split(pattern, cleaned, flags=re.IGNORECASE)
    
    keyword = parts[0].strip()
    if keyword and len(keyword.split()) <= 5:
        return keyword
    return ""


def extract_wikimedia_query(prompt, segment_title):
    prompt_lower = prompt.lower()
    
    terms = []
    if "hdmi" in prompt_lower:
        terms.append("HDMI port")
    if "displayport" in prompt_lower or "dp" in prompt_lower.split():
        terms.append("DisplayPort")
    if "usb-c" in prompt_lower:
        terms.append("USB-C port")
    if "vga" in prompt_lower:
        terms.append("VGA port")
    if "dvi" in prompt_lower:
        terms.append("DVI port")
    if "vram" in prompt_lower:
        terms.append("VRAM")
    if "gpu" in prompt_lower or "graphics card" in prompt_lower:
        if "cpu" in prompt_lower:
            terms.append("CPU GPU")
        else:
            terms.append("GPU graphics card")
    elif "cpu" in prompt_lower or "processor" in prompt_lower:
        terms.append("CPU chip")
        
    if "refresh rate" in prompt_lower or "hz" in prompt_lower:
        terms.append("monitor refresh rate")
    if "resolution" in prompt_lower or "pixels" in prompt_lower:
        terms.append("screen resolution pixels")
        
    if terms:
        return " ".join(terms)
        
    keyword = clean_prompt_to_keyword(prompt)
    if keyword:
        return keyword
        
    return segment_title


def get_wikimedia_image_url(query):
    search_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,  # File namespace
        "srlimit": 8,
        "origin": "*"
    }
    headers = {"User-Agent": "LearnCSBot/1.0 (rohit86036@gmail.com)"}
    try:
        resp = requests.get(search_url, params=params, headers=headers, timeout=10)
        data = resp.json()
        search_results = data.get("query", {}).get("search", [])
        if not search_results:
            return None
        
        for result in search_results:
            title = result.get("title", "")
            lower_title = title.lower()
            if not any(lower_title.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".svg"]):
                continue
            
            info_params = {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "titles": title,
                "iiprop": "url",
                "iiurlwidth": 800
            }
            info_resp = requests.get(search_url, params=info_params, headers=headers, timeout=10)
            info_data = info_resp.json()
            pages = info_data.get("query", {}).get("pages", {})
            for page_id, page_info in pages.items():
                imageinfos = page_info.get("imageinfo", [])
                if imageinfos:
                    return imageinfos[0].get("thumburl") or imageinfos[0].get("url")
    except Exception as e:
        print(f"  [animator] Wikimedia search error: {e}")
    return None


def _get_wikimedia_image(prompt, out_dir, img_id, segment_title=""):
    if not prompt:
        return None
    path = os.path.join(out_dir, f"img_{img_id}.png")
    if os.path.exists(path):
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            pass

    query = extract_wikimedia_query(prompt, segment_title)
    print(f"  [animator] Fetching Wikimedia image for '{query}'...")
    url = get_wikimedia_image_url(query)
    
    if not url and segment_title:
        print(f"  [animator] Specific query failed, trying segment title: '{segment_title}'...")
        url = get_wikimedia_image_url(segment_title)
        
    if not url:
        print(f"  [animator] No Wikimedia image found for '{query}' or '{segment_title}'")
        return None
        
    headers = {
        "User-Agent": "LearnCSBot/1.0 (rohit86036@gmail.com)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        img.save(path)
        return img
    except Exception as e:
        print(f"  [animator] Failed to download image from {url}: {e}")
        return None


# ── Main Entry Points ──────────────────────────────────────────────────────────

def create_animation(script_data: dict, topic: dict,
                     durations: dict, output_path: str) -> str:
    """
    Build a silent widescreen MP4 timed to match individual section audio durations.
    Uses static slide ImageClips concatenated together (chain method) to prevent OOM/corruption.
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
            img = _get_wikimedia_image(prompt, os.path.dirname(output_path), img_id, seg.get("title", ""))
            ref_imgs.append(img)
            
        n       = max(len(points), 1)
        pt_dur  = seg_dur / n

        for i in range(1, n + 1):
            pct = elapsed / total_duration
            ref_img = ref_imgs[i-1] if (i-1) < len(ref_imgs) else None
            frame = _content_slide(seg.get("title", ""), points, i, code, pct, ref_img)
            clips.append(ImageClip(frame, duration=pt_dur))
            elapsed += pt_dur

    # ── Interactive Pop Quiz ──
    if quiz:
        quiz_dur = durations["quiz"]
        countdown_dur = 5.0 if quiz_dur >= 10.0 else quiz_dur * 0.5
        reveal_dur = (quiz_dur - countdown_dur) if quiz_dur >= 10.0 else quiz_dur * 0.5
        
        steps = 5
        step_dur = countdown_dur / steps
        for i in range(steps):
            timer_pct = (steps - i) / steps
            pct = elapsed / total_duration
            frame = _quiz_slide(quiz, show_answer=False, timer_pct=timer_pct, pct=pct)
            clips.append(ImageClip(frame, duration=step_dur))
            elapsed += step_dur
            
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
    video = concatenate_videoclips(clips, method="chain")
    video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio=False,
        threads=2,
        logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"]
    )
    
    video.close()
    for clip in clips:
        clip.close()
        
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

    # Draw Short visual image in top-center (width 920px, max height 800px)
    if short_img:
        max_iw = 920
        max_ih = 750
        iw, ih = short_img.size
        aspect = iw / ih
        
        if iw > max_iw or ih > max_ih:
            if aspect > (max_iw / max_ih):
                new_w = max_iw
                new_h = int(new_w / aspect)
            else:
                new_h = max_ih
                new_w = int(new_h * aspect)
        else:
            new_w = iw
            new_h = ih
            
        short_img_resized = short_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        mask = Image.new("L", (new_w, new_h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle([0, 0, new_w, new_h], radius=24, fill=255)
        
        ix = (SW - new_w) // 2
        iy = 320 + (max_ih - new_h) // 2
        
        d.rounded_rectangle([ix - 4, iy - 4, ix + new_w + 4, iy + new_h + 4], radius=28, fill=None, outline=ACCENT, width=3)
        img.paste(short_img_resized, (ix, iy), mask)

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
    """
    Build a silent vertical MP4 timed to match short audio duration.
    Uses static slide ImageClips concatenated together (chain method) to prevent OOM/corruption.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    short_data = script_data.get("short", {})
    narration  = short_data.get("narration", "")
    prompts    = short_data.get("image_prompts") or [short_data.get("image_prompt")]
    prompts    = [p for p in prompts if p]

    # Split narration into 3-4 semantic chunks/phrases
    raw_phrases = [p.strip() for p in re.split(r'[.!?।]', narration) if p.strip()]
    if not raw_phrases:
        raw_phrases = [narration]

    # Download Wikimedia images for the short
    short_imgs = []
    for p_idx, prompt in enumerate(prompts):
        img_id = f"short_{p_idx}"
        img = _get_wikimedia_image(prompt, os.path.dirname(output_path), img_id, topic.get("title", ""))
        if img:
            short_imgs.append(img)

    n = len(raw_phrases)
    phrase_dur = audio_duration / n
    elapsed = 0.0

    clips = []
    for idx, phrase in enumerate(raw_phrases):
        for f_idx in range(3):
            sub_pct = (f_idx + 1) / 3
            current_elapsed = elapsed + (sub_pct * phrase_dur)
            timer_pct = min(current_elapsed / audio_duration, 1.0)
            
            ref_img = short_imgs[idx] if idx < len(short_imgs) else (short_imgs[-1] if short_imgs else None)
            frame = _short_frame(phrase, ref_img, timer_pct, timer_pct)
            clips.append(ImageClip(frame, duration=phrase_dur / 3))
        
        elapsed += phrase_dur

    video = concatenate_videoclips(clips, method="chain")
    video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio=False,
        threads=2,
        logger=None,
        ffmpeg_params=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"]
    )
    
    video.close()
    for clip in clips:
        clip.close()
        
    return output_path
