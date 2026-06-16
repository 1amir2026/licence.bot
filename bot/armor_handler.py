# ====================== ARMOR TRIM HANDLER ======================
# connected to bot.py - va inke
from pathlib import Path
import io

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ====================== CONSTANTS ======================

ARMOR_TYPES = ["leather", "iron", "chainmail", "golden", "diamond", "netherite"]

ARMOR_FILE_MAP = {
    "leather":    "leather",
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

# رنگ‌های دقیق مواد تریم ماینکرافت Java
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

BASE_DIR = Path(__file__).resolve().parent
ARMORS_DIR = BASE_DIR / "armors"

# state ذخیره اطلاعات هر کاربر
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
            text="✅ پایان و ساخت آرمور",
            callback_data="a_finish"
        )],
    ])


# ====================== IMAGE PROCESSING ======================

def colorize_trim(trim_img: Image.Image, color_rgb: tuple) -> Image.Image:
    """
    رنگ‌آمیزی تریم grayscale با رنگ ماده.
    
    در ماینکرافت تریم‌ها grayscale هستند:
    - سفید (255,255,255) = رنگ ماده کامل
    - سیاه (0,0,0) = شفاف
    - خاکستری = ترکیب
    
    فرمول: new_pixel = material_color * (gray_intensity / 255)
    """
    img = trim_img.convert("RGBA")
    w, h = img.size
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    
    src = img.load()
    dst = result.load()
    mr, mg, mb = color_rgb
    
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a == 0:
                continue
            # شدت grayscale
            intensity = (r + g + b) / (3 * 255.0)
            dst[x, y] = (
                int(mr * intensity),
                int(mg * intensity),
                int(mb * intensity),
                a
            )
    return result


def build_layer(armor_key: str, trim_name: str, mat_color: tuple, layer: str) -> bytes | None:
    """
    ساخت یک لایه آرمور با تریم رنگ‌شده.
    
    layer = "humanoid" یا "humanoid_leggings"
    
    مراحل:
    1. آرمور پایه: armors/{layer}/{armor_file}.png
    2. تریم: armors/trims/{layer}/{trim_name}.png
    3. رنگ‌آمیزی تریم با رنگ ماده
    4. overlay تریم رنگ‌شده روی آرمور
    """
    if not PIL_AVAILABLE:
        return None

    armor_file = ARMOR_FILE_MAP.get(armor_key, armor_key)
    armor_path = ARMORS_DIR / layer / f"{armor_file}.png"

    if not armor_path.exists():
        print(f"[armor] ❌ فایل پیدا نشد: {armor_path}")
        return None

    try:
        base = Image.open(armor_path).convert("RGBA")
        result = base.copy()

        if trim_name != "none":
            trim_path = ARMORS_DIR / "trims" / layer / f"{trim_name}.png"
            if trim_path.exists():
                trim_img = Image.open(trim_path).convert("RGBA")
                if trim_img.size != base.size:
                    trim_img = trim_img.resize(base.size, Image.NEAREST)
                colored = colorize_trim(trim_img, mat_color)
                result = Image.alpha_composite(result, colored)
            else:
                print(f"[armor] ⚠️ تریم پیدا نشد: {trim_path}")

        buf = io.BytesIO()
        result.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    except Exception as e:
        print(f"[armor] خطا در build_layer: {e}")
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
            "armor":    ARMOR_TYPES[0],
            "trim":     0,
            "material": list(TRIM_MATERIALS.keys())[0],
        }
        await message.answer(
            "🛡 <b>مرحله ۱ — نوع آرمور</b>\n\n"
            "روی دکمه کلیک کنید تا آرمور تغییر کند:",
            parse_mode="HTML",
            reply_markup=kb_armor(ARMOR_TYPES[0]),
        )

    # ─── مرحله ۱ ───────────────────────────────────────────────────

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

    @dp.callback_query(F.data == "a_to_trim")
    async def to_trim(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("دوباره از منو شروع کنید.", show_alert=True); return
        await cb.message.edit_text(
            f"🎨 <b>مرحله ۲ — تریم</b>\n\n"
            f"آرمور: <b>{s['armor'].upper()}</b>\n\n"
            f"روی دکمه کلیک کنید تا تریم تغییر کند.\n"
            f"<code>none</code> = بدون تریم",
            parse_mode="HTML",
            reply_markup=kb_trim(s["trim"]),
        )

    # ─── مرحله ۲ ───────────────────────────────────────────────────

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

        # اگر none → مستقیم بساز
        if trim_name == "none":
            await cb.message.edit_text(
                "⚙️ تریم <b>none</b> — در حال ساخت آرمور بدون تریم...",
                parse_mode="HTML"
            )
            await _build_and_send(cb, s)
            return

        await cb.message.edit_text(
            f"💎 <b>مرحله ۳ — ماده تریم</b>\n\n"
            f"آرمور: <b>{s['armor'].upper()}</b>  |  تریم: <b>{trim_name}</b>\n\n"
            f"ماده رنگ تریم را انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=kb_material(s["material"]),
        )

    # ─── مرحله ۳ ───────────────────────────────────────────────────

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

    @dp.callback_query(F.data == "a_finish")
    async def finish(cb: types.CallbackQuery):
        uid = cb.from_user.id
        s = armor_build_state.get(uid)
        if not s:
            await cb.answer("دوباره از منو شروع کنید.", show_alert=True); return
        await _build_and_send(cb, s)

    # ─── ساخت و ارسال ──────────────────────────────────────────────

    async def _build_and_send(cb: types.CallbackQuery, s: dict):
        uid = cb.from_user.id
        armor     = s["armor"]
        trim_name = ARMOR_TRIMS[s["trim"]]
        material  = s["material"]
        mat_color = TRIM_MATERIALS.get(material, (255, 255, 255))

        await cb.message.answer("⏳ در حال ساخت تکسچر آرمور...")

        if not PIL_AVAILABLE:
            await cb.message.answer(
                "❌ Pillow نصب نیست:\n<code>pip install Pillow</code>",
                parse_mode="HTML"
            )
            armor_build_state.pop(uid, None)
            return

        caption = (
            f"🛡 <b>{armor.upper()}</b>\n"
            f"تریم: <b>{trim_name}</b>"
            + (f"  |  ماده: <b>{material}</b>" if trim_name != "none" else "")
        )

        sent = 0
        for layer, label, emoji in [
            ("humanoid",           "Layer 1 — Main Body", "🔵"),
            ("humanoid_leggings",  "Layer 2 — Leggings",  "🟢"),
        ]:
            data = build_layer(armor, trim_name, mat_color, layer)
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
                    f"⚠️ فایل لایه پیدا نشد:\n"
                    f"<code>armors/{layer}/{fname}.png</code>",
                    parse_mode="HTML"
                )

        if sent:
            await cb.message.answer("✅ آرمور با موفقیت ساخته شد!")

        armor_build_state.pop(uid, None)

