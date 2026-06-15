# ====================== ARMOR TRIM HANDLER ======================
# Claude Genarate ( tnx help )
from pathlib import Path
import io
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ====================== CONSTANTS ======================

ARMOR_TYPES = ["wooden", "stone", "iron", "chainmail", "golden", "diamond", "netherite"]

# نگاشت نام آرمور به نام فایل (بدون .png)
ARMOR_FILE_MAP = {
    "wooden":    "wooden",
    "stone":     "stone",
    "iron":      "iron",
    "chainmail": "chainmail",
    "golden":    "gold",
    "diamond":   "diamond",
    "netherite": "netherite",
}

# تمام تریم‌های ماینکرافت Java به ترتیب الفبا (none اول)
ARMOR_TRIMS = [
    "none",
    "coast",
    "dune",
    "eye",
    "host",
    "raiser",
    "rib",
    "sentry",
    "shaper",
    "silence",
    "snout",
    "spire",
    "tide",
    "vex",
    "ward",
    "wayfinder",
    "wild",
]

TRIM_SLOTS = ["helmet", "chestplate", "leggings", "boots"]
TRIM_SLOT_EMOJI = {
    "helmet":     "⛑",
    "chestplate": "🥋",
    "leggings":   "👖",
    "boots":      "👟",
}

BASE_DIR = Path(__file__).resolve().parent
ARMORS_DIR = BASE_DIR / "armors"

# state: user_id -> {"armor": str, "trims": {slot: int}}
armor_build_state: dict[int, dict] = {}


# ====================== KEYBOARD BUILDERS ======================

def armor_select_keyboard(current_armor: str) -> InlineKeyboardMarkup:
    idx = ARMOR_TYPES.index(current_armor) if current_armor in ARMOR_TYPES else 0
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔄 نوع آرمور: {current_armor.upper()}  ({idx + 1}/{len(ARMOR_TYPES)})",
            callback_data="armor_cycle"
        )],
        [InlineKeyboardButton(
            text="➡️ مرحله بعد: انتخاب تریم",
            callback_data="armor_next_trim"
        )],
    ])


def trim_select_keyboard(trims: dict) -> InlineKeyboardMarkup:
    rows = []
    for slot in TRIM_SLOTS:
        idx = trims.get(slot, 0)
        name = ARMOR_TRIMS[idx]
        emoji = TRIM_SLOT_EMOJI[slot]
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {slot.capitalize()}: {name}  ({idx}/{len(ARMOR_TRIMS) - 1})",
            callback_data=f"trim_cycle:{slot}"
        )])
    rows.append([InlineKeyboardButton(
        text="✅ پایان و ساخت آرمور",
        callback_data="trim_finish"
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ====================== IMAGE PROCESSING ======================

def get_armor_path(armor_key: str, layer: str) -> Path:
    return ARMORS_DIR / layer / f"{ARMOR_FILE_MAP.get(armor_key, armor_key)}.png"

def get_trim_path(trim_name: str, layer: str) -> Optional[Path]:
    if trim_name == "none":
        return None
    return ARMORS_DIR / "trims" / layer / f"{trim_name}.png"

def compose_layer(armor_key: str, trims: dict, layer: str) -> Optional[bytes]:
    """
    ترکیب تکسچر پایه آرمور با تریم‌ها روی یک لایه.
    layer 'humanoid'         → helmet, chestplate, boots
    layer 'humanoid_leggings' → leggings
    """
    if not PIL_AVAILABLE:
        return None

    base_path = get_armor_path(armor_key, layer)
    if not base_path.exists():
        return None

    try:
        base = Image.open(base_path).convert("RGBA")
        result = base.copy()

        slots_for_layer = (
            ["helmet", "chestplate", "boots"] if layer == "humanoid"
            else ["leggings"]
        )

        for slot in slots_for_layer:
            trim_idx = trims.get(slot, 0)
            trim_name = ARMOR_TRIMS[trim_idx]
            trim_path = get_trim_path(trim_name, layer)
            if trim_path and trim_path.exists():
                overlay = Image.open(trim_path).convert("RGBA")
                if overlay.size != base.size:
                    overlay = overlay.resize(base.size, Image.NEAREST)
                result = Image.alpha_composite(result, overlay)

        buf = io.BytesIO()
        result.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    except Exception as e:
        print(f"[armor_handler] خطا در ترکیب لایه {layer}: {e}")
        return None


# ====================== HANDLER REGISTRATION ======================

def register_armor_handlers(dp: Dispatcher, bot: Bot):

    @dp.message(F.text == "🛡 ساخت آرمور با تریم")
    async def armor_trim_start(message: types.Message):
        user_id = message.from_user.id

        try:
            from bot import is_user_banned
            if is_user_banned(user_id):
                await message.answer("❌ شما از استفاده از ربات بن شده‌اید.")
                return
        except ImportError:
            pass

        armor_build_state[user_id] = {
            "armor": ARMOR_TYPES[0],
            "trims": {slot: 0 for slot in TRIM_SLOTS},
        }

        await message.answer(
            "🛡 <b>انتخاب نوع آرمور ماینکرافت خود</b>\n\n"
            "روی دکمه زیر کلیک کنید تا بین آرمورها جابجا شوید،\n"
            "سپس <b>مرحله بعد</b> را بزنید:",
            parse_mode="HTML",
            reply_markup=armor_select_keyboard(ARMOR_TYPES[0]),
        )

    @dp.callback_query(F.data == "armor_cycle")
    async def armor_cycle(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        state = armor_build_state.get(user_id)
        if not state:
            await callback.answer("❌ لطفاً دوباره از منو شروع کنید.", show_alert=True)
            return

        idx = ARMOR_TYPES.index(state["armor"]) if state["armor"] in ARMOR_TYPES else 0
        state["armor"] = ARMOR_TYPES[(idx + 1) % len(ARMOR_TYPES)]

        await callback.message.edit_reply_markup(
            reply_markup=armor_select_keyboard(state["armor"])
        )
        await callback.answer(f"✅ {state['armor'].upper()}")

    @dp.callback_query(F.data == "armor_next_trim")
    async def armor_next_trim(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        state = armor_build_state.get(user_id)
        if not state:
            await callback.answer("❌ لطفاً دوباره از منو شروع کنید.", show_alert=True)
            return

        await callback.message.edit_text(
            f"🎨 <b>حالا تریم را انتخاب کنید</b>\n\n"
            f"آرمور انتخابی: <b>{state['armor'].upper()}</b>\n\n"
            f"برای هر قطعه کلیک کنید تا تریم تغییر کند.\n"
            f"<b>none</b> = بدون تریم",
            parse_mode="HTML",
            reply_markup=trim_select_keyboard(state["trims"]),
        )

    @dp.callback_query(F.data.startswith("trim_cycle:"))
    async def trim_cycle(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        slot = callback.data.split(":")[1]

        state = armor_build_state.get(user_id)
        if not state or slot not in TRIM_SLOTS:
            await callback.answer("❌ خطا", show_alert=True)
            return

        current = state["trims"].get(slot, 0)
        state["trims"][slot] = (current + 1) % len(ARMOR_TRIMS)

        await callback.message.edit_reply_markup(
            reply_markup=trim_select_keyboard(state["trims"])
        )
        await callback.answer(f"✅ {slot}: {ARMOR_TRIMS[state['trims'][slot]]}")

    @dp.callback_query(F.data == "trim_finish")
    async def trim_finish(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        state = armor_build_state.get(user_id)
        if not state:
            await callback.answer("❌ لطفاً دوباره از منو شروع کنید.", show_alert=True)
            return

        armor = state["armor"]
        trims = state["trims"]

        await callback.message.answer("⏳ در حال ساخت تکسچر آرمور...")

        trim_summary = "\n".join(
            f"  {TRIM_SLOT_EMOJI[s]} {s.capitalize()}: {ARMOR_TRIMS[trims[s]]}"
            for s in TRIM_SLOTS
        )
        caption_base = (
            f"🛡 <b>آرمور {armor.upper()}</b>\n"
            f"تریم‌ها:\n{trim_summary}"
        )

        if not PIL_AVAILABLE:
            await callback.message.answer(
                "❌ کتابخانه Pillow نصب نیست.\n"
                "دستور زیر را اجرا کنید:\n<code>pip install Pillow</code>",
                parse_mode="HTML",
            )
            armor_build_state.pop(user_id, None)
            return

        sent = 0

        # لایه ۱ - main body (humanoid)
        layer1 = compose_layer(armor, trims, "humanoid")
        if layer1:
            await callback.message.answer_document(
                types.BufferedInputFile(layer1, filename=f"{armor}_layer_1.png"),
                caption=caption_base + "\n\n🔵 <b>Layer 1 — Main (humanoid)</b>",
                parse_mode="HTML",
            )
            sent += 1
        else:
            file_name = ARMOR_FILE_MAP.get(armor, armor)
            await callback.message.answer(
                f"⚠️ فایل لایه ۱ پیدا نشد:\n"
                f"<code>armors/humanoid/{file_name}.png</code>",
                parse_mode="HTML",
            )

        # لایه ۲ - leggings (humanoid_leggings)
        layer2 = compose_layer(armor, trims, "humanoid_leggings")
        if layer2:
            await callback.message.answer_document(
                types.BufferedInputFile(layer2, filename=f"{armor}_layer_2.png"),
                caption=caption_base + "\n\n🟢 <b>Layer 2 — Leggings (humanoid_leggings)</b>",
                parse_mode="HTML",
            )
            sent += 1
        else:
            file_name = ARMOR_FILE_MAP.get(armor, armor)
            await callback.message.answer(
                f"⚠️ فایل لایه ۲ پیدا نشد:\n"
                f"<code>armors/humanoid_leggings/{file_name}.png</code>",
                parse_mode="HTML",
            )

        if sent > 0:
            await callback.message.answer("✅ آرمور با موفقیت ساخته شد!")

        armor_build_state.pop(user_id, None)
