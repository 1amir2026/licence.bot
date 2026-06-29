"""
achievement_processor.py
موتور ساخت تصویر Achievement سبک Minecraft کلاسیک
"""
from __future__ import annotations

import io
import os
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── مسیرها ───────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR  = ASSETS_DIR / "icons"
FONTS_DIR  = ASSETS_DIR / "fonts"

# فونت‌های سیستمی (fallback)
_FONT_REGULAR = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
_FONT_BOLD    = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

# ─── رنگ‌های Minecraft Achievement Toast ─────────────────────────────────────
COLORS = {
    "border_out":   (0,   0,   0,   255),   # حاشیه بیرونی مشکی
    "border_gold":  (92,  58,   4,   255),   # حاشیه طلایی
    "border_gold2": (140, 92,  10,   255),   # حاشیه طلایی روشن
    "panel_bg":     (34,  22,   4,   255),   # پس‌زمینه اصلی
    "panel_mid":    (48,  30,   6,   255),   # لایه میانی
    "icon_bg":      (18,  10,   2,   255),   # پس‌زمینه آیکون
    "icon_border":  (70,  44,   6,   255),   # حاشیه آیکون
    "header_clr":   (85,  255,  85,  255),   # "دستاورد جدید" - سبز
    "title_clr":    (255, 255,  85,  255),   # عنوان - زرد
    "desc_clr":     (220, 220, 220,  255),   # توضیح - خاکستری روشن
    "shadow_clr":   (30,  20,   0,   180),   # سایه متن
}

# ─── آیکون‌های پیش‌فرض ────────────────────────────────────────────────────────
PRESET_ICONS: dict[str, str] = {
    "💎 الماس":     "diamond",
    "⚔️ شمشیر":    "sword",
    "⛏️ کلنگ":     "pickaxe",
    "💣 تی‌ان‌تی":  "tnt",
    "👾 کریپر":    "creeper",
    "🛏️ تخت":      "bed",
    "⭐ ستاره":    "star",
    "🍎 سیب":      "apple",
    "🛡️ سپر":      "shield",
}

# نقشه معکوس: icon_filename → emoji_label
PRESET_ICONS_REVERSE = {v: k for k, v in PRESET_ICONS.items()}


# ─── ابزارهای فارسی/RTL ──────────────────────────────────────────────────────

def _is_rtl_char(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x0600 <= cp <= 0x06FF or   # Arabic/Persian
        0x0750 <= cp <= 0x077F or   # Arabic Supplement
        0xFB50 <= cp <= 0xFDFF or   # Arabic Presentation Forms-A
        0xFE70 <= cp <= 0xFEFF      # Arabic Presentation Forms-B
    )

def _is_rtl_text(text: str) -> bool:
    return any(_is_rtl_char(c) for c in text if c.strip())

def _rtl_display(text: str) -> str:
    """
    تبدیل متن برای نمایش RTL در PIL.
    ترتیب کلمات رو معکوس می‌کنه (بدون نیاز به arabic-reshaper).
    """
    if not _is_rtl_text(text):
        return text
    words = text.split()
    words.reverse()
    return " ".join(words)


# ─── لودر فونت ────────────────────────────────────────────────────────────────

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []

    # ۱. فونت Minecraft سفارشی داخل assets/fonts
    mc_font = FONTS_DIR / ("minecraft_bold.ttf" if bold else "minecraft.ttf")
    if mc_font.exists():
        candidates.append(str(mc_font))

    # ۲. فونت‌های سیستمی
    candidates += [_FONT_BOLD if bold else _FONT_REGULAR, _FONT_REGULAR, _FONT_BOLD]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    return ImageFont.load_default()


# ─── ابزار رسم متن RTL ────────────────────────────────────────────────────────

def _draw_text_rtl(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    align: str = "right",
    shadow: bool = True,
    shadow_color: tuple = (0, 0, 0, 200),
):
    display = _rtl_display(text)
    bbox = font.getbbox(display)
    tw = bbox[2] - bbox[0]

    if align == "right":
        tx = x - tw
    elif align == "center":
        tx = x - tw // 2
    else:
        tx = x

    if shadow:
        draw.text((tx + 2, y + 2), display, font=font, fill=shadow_color)
    draw.text((tx, y), display, font=font, fill=fill)


# ─── موتور ساخت achievement ───────────────────────────────────────────────────

def create_achievement_image(
    title: str,
    description: str,
    icon_source,                  # str (نام آیکون پیش‌فرض) | bytes (عکس کاربر)
    scale: int = 4,               # ضریب بزرگ‌نمایی (1=کوچک، 4=HD)
) -> bytes:
    """
    می‌سازه یه تصویر Achievement به سبک Minecraft کلاسیک.

    Args:
        title:       عنوان (حداکثر 25 کاراکتر)
        description: توضیح (حداکثر 50 کاراکتر)
        icon_source: نام فایل آیکون پیش‌فرض (مثل 'diamond') یا bytes تصویر کاربر
        scale:       ضریب upscale (1 برای base, 4 برای HD)

    Returns:
        bytes: محتوای PNG
    """
    title       = title.strip()[:25]
    description = description.strip()[:50]

    # ─── ابعاد base (قبل از scale) ────────────────────────────────────────
    W, H = 320, 68

    # ─── canvas شفاف ──────────────────────────────────────────────────────
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ─── لایه‌های حاشیه (pixel-perfect) ──────────────────────────────────
    # ۱. حاشیه بیرونی مشکی (2px)
    draw.rectangle([0, 0, W-1, H-1], fill=COLORS["border_out"])
    # ۲. حاشیه طلایی تیره (1px)
    draw.rectangle([2, 2, W-3, H-3], fill=COLORS["border_gold"])
    # ۳. حاشیه طلایی روشن (1px)
    draw.rectangle([3, 3, W-4, H-4], fill=COLORS["border_gold2"])
    # ۴. پنل اصلی
    draw.rectangle([4, 4, W-5, H-5], fill=COLORS["panel_bg"])
    # ۵. خط داخلی تیره (top/bottom) - جلوه Minecraft
    for offset in range(4, 7):
        alpha = 60 - (offset - 4) * 15
        draw.rectangle([4, offset, W-5, offset], fill=(0, 0, 0, alpha))
        draw.rectangle([4, H-1-offset, W-5, H-1-offset], fill=(0, 0, 0, alpha))

    # ─── جعبه آیکون ───────────────────────────────────────────────────────
    icon_x1, icon_y1 = 6, 6
    icon_x2, icon_y2 = 58, H - 6
    icon_size = icon_y2 - icon_y1  # ارتفاع واقعی

    draw.rectangle([icon_x1, icon_y1, icon_x2, icon_y2], fill=COLORS["icon_bg"])
    # حاشیه جعبه آیکون (2px طلایی)
    draw.rectangle([icon_x1, icon_y1, icon_x2, icon_y2],
                   outline=COLORS["icon_border"], width=2)

    # ─── رسم آیکون ────────────────────────────────────────────────────────
    icon_img = _load_icon(icon_source, icon_size - 6)
    if icon_img:
        icon_pos = (icon_x1 + 3, icon_y1 + 3)
        img.paste(icon_img, icon_pos, icon_img)

    # ─── فونت‌ها ───────────────────────────────────────────────────────────
    font_header = _load_font(10)
    font_title  = _load_font(13, bold=True)
    font_desc   = _load_font(11)

    # ─── محدوده متن ───────────────────────────────────────────────────────
    text_right = W - 8     # نقطه راست متن (برای راست‌چین)
    text_left  = icon_x2 + 6

    # ─── "دستاورد جدید" (header) ──────────────────────────────────────────
    header_y = 8
    _draw_text_rtl(draw, "!دستاورد جدید", text_right, header_y,
                   font_header, COLORS["header_clr"], align="right")

    # ─── عنوان ────────────────────────────────────────────────────────────
    title_y = header_y + 14
    _draw_text_rtl(draw, title, text_right, title_y,
                   font_title, COLORS["title_clr"], align="right", shadow=True)

    # ─── توضیح ────────────────────────────────────────────────────────────
    desc_y = title_y + 18
    # شکستن توضیح به دو خط اگر لازم بود
    _draw_wrapped_text_rtl(draw, description, text_right, desc_y,
                           font_desc, COLORS["desc_clr"], max_width=W - icon_x2 - 16)

    # ─── جزئیات تزئینی (pixel art) ────────────────────────────────────────
    # نقاط گوشه (Minecraft style corner pixels)
    corner_color = COLORS["border_gold2"]
    for px, py in [(2, 2), (W-3, 2), (2, H-3), (W-3, H-3)]:
        draw.point((px, py), fill=corner_color)

    # ─── upscale با NEAREST برای pixel art ───────────────────────────────
    if scale > 1:
        img = img.resize((W * scale, H * scale), Image.NEAREST)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def create_achievement_hd(title: str, description: str, icon_source) -> bytes:
    """نسخه HD (x4)"""
    return create_achievement_image(title, description, icon_source, scale=4)


def create_achievement_base(title: str, description: str, icon_source) -> bytes:
    """نسخه معمولی (x2) - برای پیش‌نمایش"""
    return create_achievement_image(title, description, icon_source, scale=2)


# ─── ابزارهای داخلی ──────────────────────────────────────────────────────────

def _load_icon(icon_source, size: int) -> Image.Image | None:
    """
    لود آیکون از:
    - str → نام فایل پیش‌فرض (مثل 'diamond')
    - bytes → تصویر آپلودشده توسط کاربر
    """
    try:
        if isinstance(icon_source, bytes):
            icon = Image.open(io.BytesIO(icon_source)).convert("RGBA")
        elif isinstance(icon_source, str):
            path = ICONS_DIR / f"{icon_source}.png"
            if not path.exists():
                return None
            icon = Image.open(path).convert("RGBA")
        else:
            return None

        # Resize با NEAREST برای pixel art
        return icon.resize((size, size), Image.NEAREST)
    except Exception:
        return None


def _draw_wrapped_text_rtl(
    draw: ImageDraw.ImageDraw,
    text: str,
    x_right: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    max_width: int,
    line_height: int = 13,
):
    """رسم متن چندخطی RTL"""
    if not text:
        return

    words = text.split()
    is_rtl = _is_rtl_text(text)

    if is_rtl:
        # برای RTL: کلمات رو از راست به چپ جمع می‌کنیم
        words_reversed = list(reversed(words))
        lines = []
        current_line_words = []

        for word in words_reversed:
            test_line = " ".join(current_line_words + [word])
            bbox = font.getbbox(test_line)
            tw = bbox[2] - bbox[0]
            if tw <= max_width:
                current_line_words.append(word)
            else:
                if current_line_words:
                    lines.append(" ".join(current_line_words))
                current_line_words = [word]

        if current_line_words:
            lines.append(" ".join(current_line_words))

        for i, line in enumerate(lines[:2]):  # حداکثر 2 خط
            _draw_text_rtl(draw, line, x_right, y + i * line_height,
                          font, fill, align="right", shadow=True)
    else:
        # LTR معمولی
        lines = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = font.getbbox(test)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        for i, line in enumerate(lines[:2]):
            _draw_text_rtl(draw, line, x_right, y + i * line_height,
                          font, fill, align="right", shadow=True)