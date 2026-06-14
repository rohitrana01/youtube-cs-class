"""
modules/thumbnail_generator.py
Creates a professional 1280x720 YouTube thumbnail using Pillow.
Dark theme with the day number, topic title, level badge, and channel branding.
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720

LEVEL_COLORS = {
    "Beginner":     (34, 197, 94),    # green
    "Intermediate": (250, 204, 21),   # amber
    "Advanced":     (239, 68, 68),    # red
}


def _load_font(paths, name_candidates, size):
    for base in paths:
        for name in name_candidates:
            try:
                return ImageFont.truetype(os.path.join(base, name), size)
            except Exception:
                pass
    return ImageFont.load_default()


def _wrap(draw, text, x, y, font, color, max_w):
    lh = font.size + 8
    words = text.split()
    line = []
    lines_drawn = 0
    for word in words:
        line.append(word)
        bb = draw.textbbox((0, 0), " ".join(line), font=font)
        if bb[2] > max_w and len(line) > 1:
            line.pop()
            if lines_drawn < 3:
                draw.text((x, y), " ".join(line), font=font, fill=color)
            y += lh
            lines_drawn += 1
            line = [word]
    if line and lines_drawn < 3:
        draw.text((x, y), " ".join(line), font=font, fill=color)
        y += lh
    return y


def create_thumbnail(topic: dict, output_dir: str) -> str:
    """
    Generate and save a YouTube thumbnail.
    Returns the path to the saved JPEG.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "thumbnail.jpg")

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/",
        "/usr/share/fonts/truetype/liberation/",
        "C:/Windows/Fonts/",
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts") + "/",
    ]
    bold_names    = ["DejaVuSans-Bold.ttf",    "LiberationSans-Bold.ttf", "arialbd.ttf", "seguib.ttf"]
    regular_names = ["DejaVuSans.ttf",         "LiberationSans-Regular.ttf", "arial.ttf", "segoeui.ttf"]

    f_title  = _load_font(font_paths, bold_names,    62)
    f_sub    = _load_font(font_paths, regular_names, 30)
    f_badge  = _load_font(font_paths, bold_names,    24)
    f_small  = _load_font(font_paths, regular_names, 22)
    f_module = _load_font(font_paths, bold_names,    26)

    # ── Background gradient ──────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), (15, 20, 40))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        r = int(15  + t * 12)
        g = int(20  + t * 15)
        b = int(40  + t * 20)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ── Left accent bar ──────────────────────────────────────────────────────
    draw.rectangle([0, 0, 8, H], fill=(99, 102, 241))

    # ── Diagonal decorative stripe (subtle) ─────────────────────────────────
    for i in range(0, 200, 30):
        draw.line([(W - 300 + i, 0), (W + i, H)],
                  fill=(99, 102, 241), width=1)

    # ── Day badge ────────────────────────────────────────────────────────────
    day = topic.get("day", 1)
    badge_text = f"DAY {day}"
    draw.rounded_rectangle([36, 48, 200, 92], radius=20, fill=(99, 102, 241))
    draw.text((52, 57), badge_text, font=f_badge, fill=(255, 255, 255))

    # ── Module label ─────────────────────────────────────────────────────────
    module = topic.get("module", "Computer Science")
    draw.text((36, 108), module.upper(), font=f_module, fill=(99, 102, 241))

    # ── Title ────────────────────────────────────────────────────────────────
    title_y = _wrap(draw, topic["title"], 36, 165, f_title,
                    (255, 255, 255), W - 320)

    # ── Divider ──────────────────────────────────────────────────────────────
    draw.rectangle([36, title_y + 12, 36 + 140, title_y + 17],
                   fill=(99, 102, 241))

    # ── Subtitle ─────────────────────────────────────────────────────────────
    draw.text((36, title_y + 32), "5-min animated lesson", font=f_sub, fill=(148, 163, 184))

    # ── Level badge ─────────────────────────────────────────────────────────
    level = topic.get("level", "Beginner")
    lc    = LEVEL_COLORS.get(level, (99, 102, 241))
    lbb   = draw.textbbox((0, 0), f"● {level}", font=f_badge)
    lw    = lbb[2] - lbb[0] + 24
    lx    = W - lw - 36
    draw.rounded_rectangle([lx, H - 58, lx + lw, H - 26], radius=12,
                            fill=(*lc, 40), outline=lc, width=1)
    draw.text((lx + 12, H - 53), f"● {level}", font=f_badge, fill=lc)

    # ── Channel branding ─────────────────────────────────────────────────────
    channel = topic.get("channel", "LearnCS Daily")
    draw.text((36, H - 54), f"🖥  {channel}", font=f_small, fill=(99, 102, 241))

    # ── Progress bar (day / 100) ─────────────────────────────────────────────
    bar_x, bar_y = 36, H - 20
    bar_w = W - 72
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 8],
                            radius=4, fill=(30, 41, 59))
    filled = int(bar_w * (day / 100))
    draw.rounded_rectangle([bar_x, bar_y, bar_x + filled, bar_y + 8],
                            radius=4, fill=(99, 102, 241))

    img.save(out_path, "JPEG", quality=95, optimize=True)
    print(f"  [thumbnail] Saved → {out_path}")
    return out_path
