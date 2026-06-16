# ====================== ARMOR TRIM HANDLER ======================
# قرار دادن کنار bot.py  →  /app/bot/armor_handler.py
#
# در bot.py:
#   from armor_handler import register_armor_handlers
#   register_armor_handlers(dp, bot)
#   کیبورد: [KeyboardButton(text="🛡 ساخت آرمور با تریم")]
#
# ساختار پوشه armors/ کنار bot.py:
#   armors/
#     humanoid/
#       leather.png                  ← تکسچر پایه چرم (خاکستری/سفید)
#       leather_overlay.png          ← ماسک رنگ چرم (grayscale، روی leather.png رنگ می‌شود)
#       iron.png, diamond.png, gold.png, chainmail.png, netherite.png
#     humanoid_leggings/
#       leather.png
#       leather_overlay.png
#       iron.png, diamond.png, ...
#     trims/
#       humanoid/          coat.png, dune.png, ...  (grayscale)
#       humanoid_leggings/ coat.png, dune.png, ...
#
# pip install Pillow

from pathlib import Path
import io

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ====================== CONSTANTS ======================

# آرمورهای موجود (stone و wooden حذف شدند)
ARMOR_TYPES = ["leather", "iron", "chainmail", "golden", "diamond", "netherite"]

ARMOR_FILE_MAP = {
    "leather":   "leather",
    "iron":      "iron",
    "chainmail": "chainmail",
    "golden":    "gold",
    "diamond":   "diamond",
    "netherite": "netherite",
}

ARMOR_TRIMS = [
    "none", "coast", "dune", "eye", "host", "raiser", "rib",
    "sentry", "shaper", "silence", "snout", "spire", "tide",
    "vex", "ward", "wayfinder", "wild",
]

# رنگ‌های دقیق مواد تریم
TRIM_MATERIALS = {
    "amethyst":  (154,  90, 200),
    "copper":    (178, 100,  72),
    "diamond":   ( 68, 214, 202),
    "emerald":   ( 71, 201,  95),
    "gold":      (237, 197,  58),
    "iron":      (216, 216, 216),
    "lapis":     ( 45,  78, 167),
    "netherite": ( 52,  47,  55),
    "quartz":    (226, 219, 210),
    "redstone":  (171,   9,   9),
}

# 16 رنگ دقیق ماینکرافت Java برای آرمور چرمی
# رنگ‌ها از کد منبع ماینکرافت (DyeColor RGB)
LEATHER_COLORS = {
    "none":       ( 160, 101,  64),   # قهوه‌ای پیش‌فرض چرم
    "white":      (249, 255, 254),
    "orange":     (249, 128,  29),
    "magenta":    (199,  78, 189),
    "light_blue": ( 58, 179, 218),
    "yellow":     (254, 216,  61),
    "lime":       (128, 199,  31),
    "pink":       (243, 139, 170),
    "gray":       ( 71,  79,  82),
    "light_gray": (157, 157, 151),
    "cyan":       ( 22, 156, 156),
    "purple":     (137,  50, 184),
    "blue":       ( 60,  68, 170),
    "brown":      (131,  84,  50),
    "green":      ( 94, 124,  22),
    "red":        (176,  46,  38),
    "black":      ( 29,  29,  33),
}

LEATHER_COLOR_EMOJI = {
    "none":       "🟫",
    "white":      "⬜",
    "orange":     "🟠",
    "magenta":    "🟣",
    "light_blue": "🔵",
    "yellow":     "🟡",
    "lime":       "🟢",
    "pink":       "🩷",
    "gray":       "⬛",
    "light_gray": "🩶",
    "cyan":       "🩵",
    "purple":     "💜",
    "blue":       "🔷",
    "brown":      "🟤",
    "green":      "🌿",
    "red":        "🔴",
    "black":      "🖤",
}

LEATHER_COLOR_NAMES_FA = {
    "none":       "پیش‌فرض (قهوه‌ای)",
    "white":      "سفید",
    "orange":     "نارنجی",
    "magenta":    "ارغوانی",
    "light_blue": "آبی روشن",
    "yellow":     "زرد",
    "lime":       "سبز لیمویی",
    "pink":       "صورتی",
    "gray":       "خاکستری",
    "light_gray": "خاکستری روشن",
    "cyan":       "فیروزه‌ای",
    "purple":     "بنفش",
    "blue":       "آبی",
    "brown":      "قهوه‌ای تیره",
    "green":      "سبز",
    "red":        "قرمز",
    "black":      "مشکی",
}

BASE_DIR = Path(__file__).resolve().parent
ARMORS_DIR = BASE_DIR / "armors"

# state هر کاربر
armor_build_state: dict[int, dict] = {}


# ====================== KEYBOARDS ======================

def kb_armor(current: str) -> InlineKeyboardMarkup:
    idx = ARMOR_TYPES.index(current) if current in ARMOR_TYPES else 0
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔄 آرمور: {current.upper()}  ({idx+1}/{len(ARMOR_TYPES)})",
            callback_data="a_armor_cycle"
        )],
        [InlineKeyboardButton(
            text="➡️ مرحله بعد",
            callback_data="a_after_armor"
        )],
    ])


def kb_leather_color(current_key: str) -> InlineKeyboardMarkup:
    keys = list(LEATHER_COLORS.keys())
    idx = keys.index(current_key) if current_key in keys else 0
    emoji = LEATHER_COLOR_EMOJI.get(current_key, "🟫")
    fa = LEATHER_COLOR_NAMES_FA.get(current_key, current_key)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔄 رنگ: {emoji} {fa}  ({idx+1}/{len(keys)})",
            callback_data="a_lcolor_cycle"
        )],
        [InlineKeyboardButton(
            text="➡️ مرحله بعد: تریم",
            callback_data="a_to_trim"
        )],
    ])


def kb_trim(trim_idx: int) -> InlineKeyboardMarkup:
    name = ARMOR_TRIMS[trim_idx]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔄 تریم: {name}  ({trim_idx}/{len(ARMOR_TRIMS)-1})",
            callback_data="a_trim_cycle"
        )],
        [InlineKeyboardButton(
            text="➡️ مرحله بعد: ماده تریم",
            callback_data="a_to_material"
        )],
    ])


def kb_material(current: str) -> InlineKeyboardMarkup:
    mat_list = list(TRIM_MATERIALS.keys())
    idx = mat_list.index(current) if current in mat_list else 0
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔄 ماده: {current}  ({idx+1}/{len(mat_list)})",
            callback_data="a_mat_cycle"
        )],
        [InlineKeyboardButton(
            text="➡️ مرحله بعد: اینچنت",
            callback_data="a_to_enchant"
        )],
    ])


def kb_enchant(enchanted: bool) -> InlineKeyboardMarkup:
    status = "✨ روشن" if enchanted else "⬛ خاموش"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔄 اینچنت: {status}",
            callback_data="a_enchant_toggle"
        )],
        [InlineKeyboardButton(
            text="✅ پایان و ساخت آرمور",
            callback_data="a_finish"
        )],
    ])


# ====================== IMAGE PROCESSING ======================

def colorize_grayscale(img: Image.Image, color_rgb: tuple) -> Image.Image:
    """
    رنگ‌آمیزی تصویر با رنگ داده‌شده.
    ابتدا تصویر به luminance خالص تبدیل می‌شود، سپس رنگ اعمال می‌شود.
    این تضمین می‌کند رنگ اصلی تکسچر تأثیری نگذارد.
    فرمول: output = color * (luminance / 255)
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    src = rgba.load()
    dst = result.load()
    mr, mg, mb = color_rgb
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a == 0:
                continue
            # luminance استاندارد — رنگ اصلی پیکسل نادیده گرفته می‌شود
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            dst[x, y] = (int(mr * lum), int(mg * lum), int(mb * lum), a)
    return result


def lighten_color(color_rgb: tuple, factor: float = 1.42) -> tuple:
    """
    رنگ روشن‌تر برای overlay چرم.
    ماینکرافت از فاکتور ~1.42 استفاده می‌کند (مقدار دقیق از کد Java).
    مقادیر بالاتر از 255 کلمپ می‌شوند.
    """
    r, g, b = color_rgb
    return (
        min(255, int(r * factor)),
        min(255, int(g * factor)),
        min(255, int(b * factor)),
    )


def apply_leather_color(base: Image.Image, overlay_path: Path, color_rgb: tuple) -> Image.Image:
    """
    رنگ‌آمیزی دقیق آرمور چرمی مثل ماینکرافت Java:

    مشکل: leather.png یک تکسچر رنگی است (قهوه‌ای/خاکستری).
    اگر مستقیم colorize_grayscale بزنیم، رنگ اصلی تکسچر با رنگ
    کاربر ضرب می‌شود و نتیجه اشتباه می‌دهد.

    راه‌حل صحیح (مثل ماینکرافت Java):
      ۱. leather.png را به grayscale تبدیل کن (فقط روشنایی بگیر)
      ۲. آن grayscale را با رنگ کاربر رنگ کن  ← رنگ دقیق
      ۳. leather_overlay.png را با رنگ روشن‌تر رنگ کن و روی نتیجه بگذار
    """
    # مرحله ۱: تبدیل به grayscale خالص (حفظ آلفا)
    rgba = base.convert("RGBA")
    w, h = rgba.size
    gray_base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    src = rgba.load()
    dst = gray_base.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a == 0:
                continue
            # luminance استاندارد
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            dst[x, y] = (lum, lum, lum, a)

    # مرحله ۲: رنگ‌آمیزی grayscale با رنگ کاربر
    result = colorize_grayscale(gray_base, color_rgb)

    # مرحله ۳: overlay با رنگ روشن‌تر (highlight)
    if overlay_path and overlay_path.exists():
        overlay_img = Image.open(overlay_path).convert("RGBA")
        if overlay_img.size != (w, h):
            overlay_img = overlay_img.resize((w, h), Image.NEAREST)

        # overlay هم باید grayscale شود قبل از رنگ‌آمیزی
        ov_rgba = overlay_img.load()
        gray_ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gray_ov_px = gray_ov.load()
        for y in range(h):
            for x in range(w):
                r, g, b, a = ov_rgba[x, y]
                if a == 0:
                    continue
                lum = int(0.299 * r + 0.587 * g + 0.114 * b)
                gray_ov_px[x, y] = (lum, lum, lum, a)

        highlight_color = lighten_color(color_rgb, factor=1.42)
        colored_overlay = colorize_grayscale(gray_ov, highlight_color)
        result = Image.alpha_composite(result, colored_overlay)

    return result


def apply_enchant_glint(img: Image.Image) -> Image.Image:
    """
    افکت enchant glint بنفش/آبی.
    - آرمور روشن (iron, diamond): glint واضح
    - آرمور تیره (netherite): glint ملایم ولی قابل دید
    - آرمور چرمی: glint متوسط
    """
    base = img.convert("RGBA")
    w, h = base.size
    GR, GG, GB = 103, 25, 255
    MAX_ALPHA = 80    # حداکثر برای روشن‌ترین پیکسل‌ها
    MIN_ALPHA = 30    # حداقل برای تاریک‌ترین (netherite همیشه دیده شود)

    glint_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    src = base.load()
    gl_px = glint_layer.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a == 0:
                continue
            intensity = (r + g + b) / (3 * 255.0)
            # MIN_ALPHA تضمین می‌کند آرمور تیره هم glint دارد
            glint_a = int(MIN_ALPHA + (MAX_ALPHA - MIN_ALPHA) * intensity)
            gl_px[x, y] = (GR, GG, GB, min(255, glint_a))

    # screen blend با وزن آلفای glint
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    res = result.load()
    gl2 = glint_layer.load()

    for y in range(h):
        for x in range(w):
            br, bg, bb, ba = src[x, y]
            gr, gg, gb, ga = gl2[x, y]
            if ba == 0:
                continue
            t = ga / 255.0
            screen_r = 255 - int((255 - br) * (255 - gr) / 255)
            screen_g = 255 - int((255 - bg) * (255 - gg) / 255)
            screen_b = 255 - int((255 - bb) * (255 - gb) / 255)
            # blend بین base و screen با وزن t
            nr = int(br + (screen_r - br) * t)
            ng = int(bg + (screen_g - bg) * t)
            nb = int(bb + (screen_b - bb) * t)
            res[x, y] = (min(255, nr), min(255, ng), min(255, nb), ba)

    return result


def apply_enchant_glint(img: Image.Image) -> Image.Image:
    """
    اعمال enchanted_glint.png از فایل واقعی ماینکرافت.
    
    در ماینکرافت Java، glint با blend mode خاصی اعمال می‌شود:
    - glint.png روی تمام سطح آرمور tile می‌شود
    - فقط روی پیکسل‌های غیرشفاف آرمور نمایش داده می‌شود
    - با آلفای ~50% و screen/additive blend
    """
    glint_path = ARMORS_DIR / "enchanted_glint.png"
    base = img.convert("RGBA")
    w, h = base.size

    if glint_path.exists():
        glint_src = Image.open(glint_path).convert("RGBA")
        
        # tile کردن glint روی کل canvas اگر کوچک‌تر بود
        if glint_src.size != (w, h):
            tiled = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            gw, gh = glint_src.size
            for ty in range(0, h, gh):
                for tx in range(0, w, gw):
                    tiled.paste(glint_src, (tx, ty))
            glint_src = tiled.crop((0, 0, w, h))
        
        # mask: فقط جایی که آرمور غیرشفاف است glint نمایش داده شود
        armor_mask = base.split()[3]  # آلفای آرمور
        
        # آلفای glint را با mask آرمور ضرب کن + کاهش به 60%
        glint_rgba = glint_src.copy()
        glint_pixels = glint_rgba.load()
        mask_pixels = armor_mask.load()
        
        for y in range(h):
            for x in range(w):
                gr, gg, gb, ga = glint_pixels[x, y]
                armor_a = mask_pixels[x, y]
                # glint فقط روی آرمور، با 60% شفافیت
                new_a = int(ga * (armor_a / 255.0) * 0.60)
                glint_pixels[x, y] = (gr, gg, gb, new_a)
        
        # screen blend: glint روی آرمور
        result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        src_px = base.load()
        gl_px = glint_rgba.load()
        res_px = result.load()
        
        for y in range(h):
            for x in range(w):
                br, bg, bb, ba = src_px[x, y]
                gr, gg, gb, ga = gl_px[x, y]
                if ba == 0:
                    continue
                t = ga / 255.0
                # screen blend
                sr = 255 - int((255 - br) * (255 - gr) / 255)
                sg = 255 - int((255 - bg) * (255 - gg) / 255)
                sb = 255 - int((255 - bb) * (255 - gb) / 255)
                # mix بین base و screen
                nr = int(br + (sr - br) * t)
                ng = int(bg + (sg - bg) * t)
                nb = int(bb + (sb - bb) * t)
                res_px[x, y] = (min(255, nr), min(255, ng), min(255, nb), ba)
        
        return result

    else:
        # fallback اگر فایل نبود: glint ساده بنفش
        print(f"[armor] ⚠️ enchanted_glint.png پیدا نشد: {glint_path}")
        result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        src_px = base.load()
        res_px = result.load()
        GR, GG, GB = 103, 25, 255
        for y in range(h):
            for x in range(w):
                br, bg, bb, ba = src_px[x, y]
                if ba == 0:
                    continue
                intensity = (r + g + b) / (3 * 255.0) if False else (br + bg + bb) / (3 * 255.0)
                t = 0.25 + 0.20 * intensity
                sr = 255 - int((255 - br) * (255 - GR) / 255)
                sg = 255 - int((255 - bg) * (255 - GG) / 255)
                sb = 255 - int((255 - bb) * (255 - GB) / 255)
                res_px[x, y] = (
                    min(255, int(br + (sr - br) * t)),
                    min(255, int(bg + (sg - bg) * t)),
                    min(255, int(bb + (sb - bb) * t)),
                    ba
                )
        return result


def build_layer(armor_key: str, leather_color_key: str,
                trim_name: str, mat_color: tuple, layer: str,
                enchanted: bool = False) -> bytes | None:
    """
    ترتیب صحیح لایه‌ها (مثل ماینکرافت Java):
    
    برای چرم:
      1. leather.png  رنگ‌شده با رنگ کاربر
      2. leather_overlay.png  رنگ‌شده با رنگ روشن‌تر (highlight)
      3. trim  رنگ‌شده با رنگ ماده تریم  ← جدا از رنگ چرم
      4. (enchant glint)
    
    برای بقیه:
      1. armor.png  (base)
      2. trim  رنگ‌شده با رنگ ماده تریم
      3. (enchant glint)
    
    نکته مهم: رنگ چرم و رنگ ماده تریم کاملاً مجزا هستند و
    هیچ‌وقت با هم قاطی نمی‌شوند.
    """
    if not PIL_AVAILABLE:
        return None

    armor_file = ARMOR_FILE_MAP.get(armor_key, armor_key)
    armor_path = ARMORS_DIR / layer / f"{armor_file}.png"

    if not armor_path.exists():
        print(f"[armor] ❌ آرمور پیدا نشد: {armor_path}")
        return None

    try:
        base = Image.open(armor_path).convert("RGBA")

        if armor_key == "leather":
            # مرحله ۱+۲: رنگ‌آمیزی چرم (base + overlay)
            color_rgb = LEATHER_COLORS.get(leather_color_key, LEATHER_COLORS["none"])
            overlay_path = ARMORS_DIR / layer / "leather_overlay.png"
            result = apply_leather_color(base, overlay_path, color_rgb)
        else:
            result = base.copy()

        # مرحله ۳: تریم — با رنگ ماده تریم، کاملاً مستقل از رنگ چرم
        if trim_name != "none":
            trim_path = ARMORS_DIR / "trims" / layer / f"{trim_name}.png"
            if trim_path.exists():
                trim_img = Image.open(trim_path).convert("RGBA")
                if trim_img.size != result.size:
                    trim_img = trim_img.resize(result.size, Image.NEAREST)
                # mat_color = رنگ ماده تریم (emerald, diamond, ...)
                # این کاملاً جدا از leather_color است
                colored_trim = colorize_grayscale(trim_img, mat_color)
                result = Image.alpha_composite(result, colored_trim)
            else:
                print(f"[armor] ⚠️ تریم پیدا نشد: {trim_path}")

        # مرحله ۴: enchant glint
        if enchanted:
            result = apply_enchant_glint(result)

        buf = io.BytesIO()
        result.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    except Exception as e:
        print(f"[armor] خطا در build_layer({armor_key}, {layer}): {e}")
        import traceback; traceback.print_exc()
        return None


# ====================== HANDLERS ======================

def register_armor_handlers(dp: Dispatcher, bot: Bot):

    @dp.message(F.text == "🛡 ساخت آرمور با تریم")
    async def start(message: types.Message):
        uid = message.from_user.id
        try:
            from bot import is_user_banned
            if is_user_banned(uid):
                await message.answer("❌ شما بن شده‌اید.")
                return
        except ImportError:
            pass

        armor_build_state[uid] = {
            "armor":         ARMOR_TYPES[0],   # leather
            "leather_color": "none",
            "trim":          0,
            "material":      list(TRIM_MATERIALS.keys())[0],
            "enchanted":     False,
        }
        await message.answer(
            "🛡 <b>مرحله ۱ — نوع آرمور</b>\n\n"
            "روی دکمه کلیک کنید تا آرمور تغییر کند:",
            parse_mode="HTML",
            reply_markup=kb_armor(ARMOR_TYPES[0]),
        )

    # ─── مرحله ۱: چرخش آرمور ──────────────────────────────────────

    @dp.callback_query(F.data == "a_armor_cycle")
    async def armor_cycle(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("دوباره از منو شروع کنید.", show_alert=True); return
        idx = ARMOR_TYPES.index(s["armor"]) if s["armor"] in ARMOR_TYPES else 0
        s["armor"] = ARMOR_TYPES[(idx + 1) % len(ARMOR_TYPES)]
        await cb.message.edit_reply_markup(reply_markup=kb_armor(s["armor"]))
        await cb.answer(s["armor"].upper())

    @dp.callback_query(F.data == "a_after_armor")
    async def after_armor(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("دوباره از منو شروع کنید.", show_alert=True); return

        # اگر چرم → مرحله رنگ چرم
        if s["armor"] == "leather":
            s["leather_color"] = "none"
            color_key = "none"
            emoji = LEATHER_COLOR_EMOJI["none"]
            fa = LEATHER_COLOR_NAMES_FA["none"]
            keys = list(LEATHER_COLORS.keys())
            await cb.message.edit_text(
                f"🎨 <b>مرحله ۲ — رنگ آرمور چرمی</b>\n\n"
                f"روی دکمه کلیک کنید تا رنگ تغییر کند.\n"
                f"<b>none</b> = رنگ پیش‌فرض قهوه‌ای چرم",
                parse_mode="HTML",
                reply_markup=kb_leather_color("none"),
            )
        else:
            # سایر آرمورها → مستقیم به تریم
            await cb.message.edit_text(
                f"🎨 <b>مرحله ۲ — تریم</b>\n\n"
                f"آرمور: <b>{s['armor'].upper()}</b>\n\n"
                f"روی دکمه کلیک کنید تا تریم تغییر کند.\n"
                f"<code>none</code> = بدون تریم",
                parse_mode="HTML",
                reply_markup=kb_trim(s["trim"]),
            )

    # ─── مرحله ۲ (فقط چرم): چرخش رنگ ────────────────────────────

    @dp.callback_query(F.data == "a_lcolor_cycle")
    async def lcolor_cycle(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("خطا", show_alert=True); return
        keys = list(LEATHER_COLORS.keys())
        idx = keys.index(s["leather_color"]) if s["leather_color"] in keys else 0
        s["leather_color"] = keys[(idx + 1) % len(keys)]
        await cb.message.edit_reply_markup(reply_markup=kb_leather_color(s["leather_color"]))
        emoji = LEATHER_COLOR_EMOJI.get(s["leather_color"], "")
        fa = LEATHER_COLOR_NAMES_FA.get(s["leather_color"], s["leather_color"])
        await cb.answer(f"{emoji} {fa}")

    @dp.callback_query(F.data == "a_to_trim")
    async def to_trim(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("دوباره از منو شروع کنید.", show_alert=True); return

        armor_label = s["armor"].upper()
        extra = ""
        if s["armor"] == "leather":
            fa = LEATHER_COLOR_NAMES_FA.get(s["leather_color"], s["leather_color"])
            emoji = LEATHER_COLOR_EMOJI.get(s["leather_color"], "")
            extra = f"  |  رنگ: {emoji} {fa}"

        await cb.message.edit_text(
            f"🎨 <b>مرحله ۳ — تریم</b>\n\n"
            f"آرمور: <b>{armor_label}</b>{extra}\n\n"
            f"روی دکمه کلیک کنید تا تریم تغییر کند.\n"
            f"<code>none</code> = بدون تریم",
            parse_mode="HTML",
            reply_markup=kb_trim(s["trim"]),
        )

    # ─── مرحله ۳: چرخش تریم ──────────────────────────────────────

    @dp.callback_query(F.data == "a_trim_cycle")
    async def trim_cycle(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("خطا", show_alert=True); return
        s["trim"] = (s["trim"] + 1) % len(ARMOR_TRIMS)
        await cb.message.edit_reply_markup(reply_markup=kb_trim(s["trim"]))
        await cb.answer(ARMOR_TRIMS[s["trim"]])

    @dp.callback_query(F.data == "a_to_material")
    async def to_material(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("دوباره از منو شروع کنید.", show_alert=True); return

        trim_name = ARMOR_TRIMS[s["trim"]]
        if trim_name == "none":
            # بدون تریم → مستقیم به مرحله اینچنت
            await cb.message.edit_text(
                f"✨ <b>مرحله آخر — اینچنت</b>\n\n"
                f"آرمور: <b>{s['armor'].upper()}</b>  |  تریم: <b>none</b>\n\n"
                f"آیا می‌خواهید آرمور اینچنت باشد؟\n"
                f"(افکت بنفش درخشان روی تکسچر)",
                parse_mode="HTML",
                reply_markup=kb_enchant(s.get("enchanted", False)),
            )
            return

        await cb.message.edit_text(
            f"💎 <b>مرحله ۴ — ماده تریم</b>\n\n"
            f"آرمور: <b>{s['armor'].upper()}</b>  |  تریم: <b>{trim_name}</b>\n\n"
            f"ماده رنگ تریم را انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=kb_material(s["material"]),
        )

    # ─── مرحله ۴: چرخش ماده ──────────────────────────────────────

    @dp.callback_query(F.data == "a_mat_cycle")
    async def mat_cycle(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("خطا", show_alert=True); return
        mat_list = list(TRIM_MATERIALS.keys())
        idx = mat_list.index(s["material"]) if s["material"] in mat_list else 0
        s["material"] = mat_list[(idx + 1) % len(mat_list)]
        await cb.message.edit_reply_markup(reply_markup=kb_material(s["material"]))
        await cb.answer(s["material"])

    @dp.callback_query(F.data == "a_to_enchant")
    async def to_enchant(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("دوباره از منو شروع کنید.", show_alert=True); return
        trim_name = ARMOR_TRIMS[s["trim"]]
        await cb.message.edit_text(
            f"✨ <b>مرحله آخر — اینچنت</b>\n\n"
            f"آرمور: <b>{s['armor'].upper()}</b>  |  تریم: <b>{trim_name}</b>  |  ماده: <b>{s['material']}</b>\n\n"
            f"آیا می‌خواهید آرمور اینچنت باشد؟\n"
            f"(افکت بنفش درخشان روی تکسچر)",
            parse_mode="HTML",
            reply_markup=kb_enchant(s.get("enchanted", False)),
        )

    # ─── مرحله آخر: toggle اینچنت ────────────────────────────────

    @dp.callback_query(F.data == "a_enchant_toggle")
    async def enchant_toggle(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("خطا", show_alert=True); return
        s["enchanted"] = not s.get("enchanted", False)
        await cb.message.edit_reply_markup(reply_markup=kb_enchant(s["enchanted"]))
        status = "✨ روشن" if s["enchanted"] else "⬛ خاموش"
        await cb.answer(f"اینچنت: {status}")

    @dp.callback_query(F.data == "a_finish")
    async def finish(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("دوباره از منو شروع کنید.", show_alert=True); return
        await _build_and_send(cb, s)

    # ─── ساخت و ارسال ─────────────────────────────────────────────

    async def _build_and_send(cb: types.CallbackQuery, s: dict):
        uid = cb.from_user.id
        armor         = s["armor"]
        leather_color = s.get("leather_color", "none")
        trim_name     = ARMOR_TRIMS[s["trim"]]
        material      = s["material"]
        mat_color     = TRIM_MATERIALS.get(material, (255, 255, 255))
        enchanted     = s.get("enchanted", False)

        await cb.message.answer("⏳ در حال ساخت تکسچر آرمور...")

        if not PIL_AVAILABLE:
            await cb.message.answer(
                "❌ Pillow نصب نیست:\n<code>pip install Pillow</code>",
                parse_mode="HTML"
            )
            armor_build_state.pop(uid, None)
            return

        lines = [f"🛡 <b>{armor.upper()}</b>"]
        if armor == "leather":
            fa    = LEATHER_COLOR_NAMES_FA.get(leather_color, leather_color)
            emoji = LEATHER_COLOR_EMOJI.get(leather_color, "")
            lines.append(f"رنگ چرم: {emoji} {fa}")
        lines.append(f"تریم: <b>{trim_name}</b>")
        if trim_name != "none":
            lines.append(f"ماده تریم: <b>{material}</b>")
        lines.append(f"اینچنت: {'✨ بله' if enchanted else '⬛ خیر'}")
        caption = "\n".join(lines)

        sent = 0
        for layer, label, emoji in [
            ("humanoid",          "Layer 1 — Main Body", "🔵"),
            ("humanoid_leggings", "Layer 2 — Leggings",  "🟢"),
        ]:
            data = build_layer(armor, leather_color, trim_name, mat_color, layer, enchanted)
            if data:
                await cb.message.answer_document(
                    types.BufferedInputFile(data, filename=f"{armor}_{layer}.png"),
                    caption=caption + f"\n\n{emoji} <b>{label}</b>",
                    parse_mode="HTML",
                )
                sent += 1
            else:
                fname = ARMOR_FILE_MAP.get(armor, armor)
                await cb.message.answer(
                    f"⚠️ فایل پیدا نشد:\n<code>armors/{layer}/{fname}.png</code>",
                    parse_mode="HTML"
                )

        if sent:
            await cb.message.answer("✅ آرمور با موفقیت ساخته شد!")

        armor_build_state.pop(uid, None)
