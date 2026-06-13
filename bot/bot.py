import asyncio
import os
import random
import string
import zipfile
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import aiohttp

from config import TOKEN, ADMIN_ID
from database import Session, License

# ====================== FSM ======================
class BroadcastState(StatesGroup):
    waiting_message = State()
    waiting_buttons = State()

class AdminState(StatesGroup):
    waiting_search = State()

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_modes = {}
user_data = {}  # برای ذخیره اطلاعات بین دو مرحله JSON و Texture

# ====================== PATHS ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSOR_DIR = os.path.join(BASE_DIR, "..", "processor")

NODE_SCRIPT = os.path.join(PROCESSOR_DIR, "processor.mjs")
ITEM3D_SCRIPT = os.path.join(PROCESSOR_DIR, "item3d.mjs")
JSON_TO_OBJ_SCRIPT = os.path.join(PROCESSOR_DIR, "json_to_obj.mjs")

INPUT_DIR = os.path.join(PROCESSOR_DIR, "input")
OUTPUT_DIR = os.path.join(PROCESSOR_DIR, "output")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ====================== LICENSE ======================
LICENSE_REGEX = r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"


def generate_license():
    chars = string.ascii_uppercase + string.digits
    return '-'.join(''.join(random.choices(chars, k=4)) for _ in range(4))


def is_admin(user_id: int):
    return user_id == ADMIN_ID


def is_user_banned(user_id: int) -> bool:
    session = Session()
    try:
        banned = session.query(License).filter(
            License.user_id == user_id,
            License.banned == True
        ).first()
        return banned is not None
    finally:
        session.close()


# ====================== HELPERS ======================
async def run_node_processor(input_path: str, output_path: str, xp_percent: float = 0.7, upscale_rate: int = 1):
    proc = await asyncio.create_subprocess_exec(
        "node", NODE_SCRIPT, input_path, output_path,
        str(xp_percent), str(upscale_rate),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=PROCESSOR_DIR
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Node processor failed: {stderr.decode()}")


async def run_item3d(input_path: str, output_obj: str):
    proc = await asyncio.create_subprocess_exec(
        "node", ITEM3D_SCRIPT, input_path, output_obj,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=PROCESSOR_DIR
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Item3D failed:\n{stderr.decode()}")

    zip_path = output_obj.replace(".obj", ".zip")
    if os.path.exists(zip_path):
        return zip_path
    elif os.path.exists(output_obj):
        return output_obj
    else:
        raise RuntimeError("No output file was generated")


async def run_json_to_obj(json_path: str, output_obj: str):
    os.makedirs(os.path.dirname(output_obj), exist_ok=True)
    
    proc = await asyncio.create_subprocess_exec(
        "node", JSON_TO_OBJ_SCRIPT, json_path, output_obj,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=PROCESSOR_DIR
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        raise RuntimeError(f"JSON to OBJ failed:\n{stderr.decode()}")
    
    if not os.path.exists(output_obj):
        raise RuntimeError(f"Output file not created: {output_obj}")
    
    return output_obj


def create_zip_with_texture(base_name: str, obj_path: str, texture_path: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    zip_path = os.path.join(OUTPUT_DIR, f"{base_name}.zip")
    texture_name = os.path.basename(texture_path)
    mtl_path = obj_path.replace('.obj', '.mtl')
    
    if os.path.exists(mtl_path):
        with open(mtl_path, 'r', encoding='utf-8') as f:
            mtl_content = f.read()
        mtl_content = mtl_content.replace('texture.png', texture_name)
        with open(mtl_path, 'w', encoding='utf-8') as f:
            f.write(mtl_content)

    with zipfile.ZipFile(zip_path, 'w') as z:
        z.write(obj_path, os.path.basename(obj_path))
        if os.path.exists(mtl_path):
            z.write(mtl_path, os.path.basename(mtl_path))
        z.write(texture_path, texture_name)
    
    return zip_path


# ====================== ADMIN PANEL HELPERS ======================
PAGE_SIZE = 5


def make_cb(a: str, **kwargs) -> str:
    data = {"a": a}
    data.update(kwargs)
    return json.dumps(data, separators=(",", ":"))


def parse_cb(data: str):
    return json.loads(data)


def admin_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔑 ساخت لایسنس جدید")],
            [KeyboardButton(text="📢 اطلاع‌رسانی")],
            [KeyboardButton(text="🛠 سیستم مدیریت")],
        ],
        resize_keyboard=True
    )


def build_management_panel_kb():
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="👥 لیست کاربران", callback_data=make_cb("list", p=1))],
        [types.InlineKeyboardButton(text="🚫 لیست بن‌شده‌ها", callback_data=make_cb("banned", p=1))],
        [types.InlineKeyboardButton(text="🔍 جستجو کاربر", callback_data=make_cb("search"))],
        [types.InlineKeyboardButton(text="↩️ بستن پنل", callback_data=make_cb("back"))],
    ])
    return kb


def render_user_line(idx: int, lic: License) -> str:
    uname = lic.username or "بدون یوزرنیم"
    status = "بن‌شده" if lic.banned else "فعال"
    used_at = lic.used_at.strftime("%Y-%m-%d %H:%M") if lic.used_at else "نامشخص"
    return (
        f"{idx}. ID: {lic.user_id}\n"
        f"   Username: @{uname}\n"
        f"   License: {lic.key}\n"
        f"   Used at: {used_at}\n"
        f"   Status: {status}\n"
    )


async def send_users_page(callback: types.CallbackQuery, page: int, banned_only: bool = False):
    session = Session()
    try:
        q = session.query(License).filter(License.used == True)
        if banned_only:
            q = q.filter(License.banned == True)
        q = q.order_by(License.id)

        total = q.count()
        if total == 0:
            text = "هیچ کاربری یافت نشد." if not banned_only else "هیچ کاربر بن‌شده‌ای وجود ندارد."
            await callback.message.edit_text(text, reply_markup=build_management_panel_kb())
            return

        max_page = (total + PAGE_SIZE - 1) // PAGE_SIZE
        if page < 1:
            page = 1
        if page > max_page:
            page = max_page

        items = q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()

        lines = []
        for i, lic in enumerate(items, start=1 + (page - 1) * PAGE_SIZE):
            lines.append(render_user_line(i, lic))

        header = "👥 لیست کاربران\n\n" if not banned_only else "🚫 لیست کاربران بن‌شده\n\n"
        text = header + "\n".join(lines) + f"\n\nصفحه {page} از {max_page}"

        kb_rows = []

        # دکمه پروفایل برای هر کاربر
        for lic in items:
            uname = lic.username or "بدون یوزرنیم"
            btn_text = f"👤 {lic.user_id} (@{uname})"
            kb_rows.append([
                types.InlineKeyboardButton(
                    text=btn_text,
                    callback_data=make_cb("profile", u=lic.user_id)
                )
            ])

        nav_row = []
        if page > 1:
            nav_row.append(
                types.InlineKeyboardButton(
                    text="⬅️ قبلی",
                    callback_data=make_cb("banned" if banned_only else "list", p=page - 1)
                )
            )
        if page < max_page:
            nav_row.append(
                types.InlineKeyboardButton(
                    text="➡️ بعدی",
                    callback_data=make_cb("banned" if banned_only else "list", p=page + 1)
                )
            )
        if nav_row:
            kb_rows.append(nav_row)

        kb_rows.append([
            types.InlineKeyboardButton(text="↩️ بازگشت به پنل", callback_data=make_cb("panel"))
        ])

        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await callback.message.edit_text(text, reply_markup=kb)

    finally:
        session.close()


async def send_user_profile(callback: types.CallbackQuery, user_id: int):
    session = Session()
    try:
        licenses = session.query(License).filter(License.user_id == user_id).all()
        if not licenses:
            await callback.answer("کاربر یافت نشد.", show_alert=True)
            return

        banned = any(l.banned for l in licenses)
        uname = licenses[0].username or "بدون یوزرنیم"

        lines = [
            "👤 پروفایل کاربر",
            "",
            f"ID: {user_id}",
            f"Username: @{uname}",
            f"Status: {'بن‌شده' if banned else 'فعال'}",
            "",
            "لایسنس‌ها:"
        ]
        for lic in licenses:
            used_at = lic.used_at.strftime("%Y-%m-%d %H:%M") if lic.used_at else "نامشخص"
            lines.append(f"- {lic.key} (Used at: {used_at})")

        text = "\n".join(lines)

        kb_rows = []
        if banned:
            kb_rows.append([
                types.InlineKeyboardButton(
                    text="♻️ آن‌بن کاربر",
                    callback_data=make_cb("unban", u=user_id)
                )
            ])
        else:
            kb_rows.append([
                types.InlineKeyboardButton(
                    text="🚫 بن کاربر",
                    callback_data=make_cb("ban", u=user_id)
                )
            ])

        kb_rows.append([
            types.InlineKeyboardButton(
                text="↩️ بازگشت به پنل",
                callback_data=make_cb("panel")
            )
        ])

        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await callback.message.edit_text(text, reply_markup=kb)

    finally:
        session.close()


# ====================== COMMANDS ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    if is_admin(message.from_user.id):
        keyboard = admin_main_keyboard()
        await message.answer(
            "سلام ادمین گرامی\n\nبرای مدیریت از دکمه‌های زیر استفاده کن:",
            reply_markup=keyboard
        )
    else:
        if is_user_banned(message.from_user.id):
            await message.answer("❌ شما از استفاده از ربات بن شده‌اید.")
            return

        await message.answer(
            "سلام! اگر از قبل لایسنس دارید نادیده بگیرید.\n\n"
            "برای دریافت لایسنس به ادمین مراجعه کنید:\n"
            "@Amirmah198"
        )


@dp.message(F.text == "🔑 ساخت لایسنس جدید")
async def create_license(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    key = generate_license()
    session = Session()
    session.add(License(key=key))
    session.commit()
    session.close()

    await message.answer(f"✅ لایسنس جدید ساخته شد:\n\n`{key}`\n\nکپی کن و بفرست.")


# ====================== LICENSE CHECK ======================
@dp.message(F.text.regexp(LICENSE_REGEX))
async def check_license(message: types.Message):
    if is_admin(message.from_user.id):
        return

    if is_user_banned(message.from_user.id):
        await message.answer("❌ شما از استفاده از ربات بن شده‌اید.")
        return

    session = Session()
    try:
        license_glb = session.query(License).filter_by(
            key=message.text.strip(), used=False
        ).first()

        if license_glb:
            license_glb.used = True
            license_glb.user_id = message.from_user.id
            license_glb.username = message.from_user.username or "بدون یوزرنیم"
            license_glb.used_at = datetime.utcnow()
            session.commit()

            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📦 دریافت ریسورس پک ریلیز تکسچر")],
                    [KeyboardButton(text="🧊 ساخت آیتم سه‌بعدی ماینکرافت")],
                    [KeyboardButton(text="🔄 تبدیل JSON به OBJ")],
                    [KeyboardButton(text="📥 گرفتن فایل‌های ماینکرافت")]  # دکمه جدید
                ],
                resize_keyboard=True
            )

            await message.answer("✅ لایسنس فعال شد!\n\nبه پنل خوش آمدید 🎉", reply_markup=keyboard)
        else:
            await message.answer("❌ لایسنس نامعتبر یا قبلاً استفاده شده.")
    finally:
        session.close()


# ====================== BROADCAST ======================
@dp.message(F.text == "📢 اطلاع‌رسانی")
async def start_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(BroadcastState.waiting_message)
    await message.answer(
        "📨 پیام خود را ارسال کنید.\n\n"
        "می‌توانید متن، عکس، ویدیو یا فایل بفرستید."
    )


@dp.message(BroadcastState.waiting_message)
async def receive_broadcast_message(message: types.Message, state: FSMContext):
    content = {}

    if message.text:
        content["type"] = "text"
        content["text"] = message.text

    elif message.photo:
        content["type"] = "photo"
        content["file_id"] = message.photo[-1].file_id
        content["caption"] = message.caption or ""

    elif message.video:
        content["type"] = "video"
        content["file_id"] = message.video.file_id
        content["caption"] = message.caption or ""

    elif message.document:
        content["type"] = "document"
        content["file_id"] = message.document.file_id
        content["caption"] = message.caption or ""

    else:
        await message.answer("❌ فرمت پیام پشتیبانی نمی‌شود.")
        return

    await state.update_data(content=content, buttons=[])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append([types.InlineKeyboardButton(text="➕ افزودن دکمه", callback_data="add_btn")])
    keyboard.inline_keyboard.append([types.InlineKeyboardButton(text="✔️ تکمیل و ارسال", callback_data="finish")])
    keyboard.inline_keyboard.append([types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="back")])

    await state.set_state(BroadcastState.waiting_buttons)
    await message.answer("پیام ذخیره شد.\n\nاکنون می‌توانید دکمه اضافه کنید.", reply_markup=keyboard)


@dp.callback_query(F.data == "finish")
async def finish_broadcast(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    content = data.get("content")
    buttons = data.get("buttons", [])

    if not content:
        await callback.answer("❌ محتوا پیدا نشد!", show_alert=True)
        return

    kb = None
    if buttons:
        inline_buttons = []
        for btn in buttons:
            if btn["action"].startswith("copy:"):
                msg_id = btn["action"].replace("copy:", "")
                inline_buttons.append([
                    types.InlineKeyboardButton(
                        text=btn["title"],
                        callback_data=f"copy_{msg_id}"
                    )
                ])
            else:
                inline_buttons.append([
                    types.InlineKeyboardButton(
                        text=btn["title"],
                        url=btn["action"]
                    )
                ])
        kb = types.InlineKeyboardMarkup(inline_keyboard=inline_buttons)

    session = Session()
    try:
        users = session.query(License).filter(License.used == True).all()
        success = 0
        failed = 0

        for u in users:
            if not u.user_id:
                failed += 1
                continue

            if u.banned:
                failed += 1
                continue
                
            try:
                if content["type"] == "text":
                    await bot.send_message(
                        u.user_id,
                        content["text"],
                        reply_markup=kb,
                        disable_web_page_preview=True
                    )
                elif content["type"] == "photo":
                    await bot.send_photo(
                        u.user_id,
                        content["file_id"],
                        caption=content.get("caption", ""),
                        reply_markup=kb
                    )
                elif content["type"] == "video":
                    await bot.send_video(
                        u.user_id,
                        content["file_id"],
                        caption=content.get("caption", ""),
                        reply_markup=kb
                    )
                elif content["type"] == "document":
                    await bot.send_document(
                        u.user_id,
                        content["file_id"],
                        caption=content.get("caption", ""),
                        reply_markup=kb
                    )
                success += 1

                await asyncio.sleep(0.05)

            except Exception as e:
                failed += 1
                print(f"Failed to send to {u.user_id}: {e}")

        await callback.message.edit_text(
            f"✅ اطلاع‌رسانی تمام شد!\n\n"
            f"✅ موفق: {success}\n"
            f"❌ ناموفق: {failed}\n"
            f"👥 کل کاربران: {len(users)}"
        )

    except Exception as e:
        await callback.message.edit_text(f"❌ خطای کلی: {e}")
    finally:
        session.close()
        await state.clear()


@dp.callback_query(F.data == "back")
async def back_to_admin(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard = admin_main_keyboard()
    await callback.message.answer("به منوی ادمین برگشتی.", reply_markup=keyboard)


@dp.callback_query(F.data == "add_btn")
async def ask_button(callback: types.CallbackQuery):
    await callback.message.answer(
        "فرمت دکمه:\n\n"
        "`عنوان دکمه | لینک`\n"
        "یا\n"
        "`عنوان دکمه | copy:MESSAGE_ID`\n",
        parse_mode="Markdown"
    )


@dp.message(F.text.contains("|"), BroadcastState.waiting_buttons)
async def add_button(message: types.Message, state: FSMContext):
    title, action = message.text.split("|", 1)
    title = title.strip()
    action = action.strip()

    data = await state.get_data()
    buttons = data["buttons"]

    buttons.append({"title": title, "action": action})
    await state.update_data(buttons=buttons)

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➕ افزودن دکمه", callback_data="add_btn")],
        [types.InlineKeyboardButton(text="✔️ تکمیل و ارسال", callback_data="finish")],
        [types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="back")]
    ])

    await message.answer(f"دکمه «{title}» اضافه شد.", reply_markup=keyboard)


# ===================== COPY BUTTON ======================
@dp.callback_query(F.data.startswith("copy_"))
async def copy_message_handler(callback: types.CallbackQuery):
    msg_id = callback.data.replace("copy_", "")
    try:
        await bot.copy_message(
            chat_id=callback.from_user.id,
            from_chat_id=ADMIN_ID,
            message_id=int(msg_id)
        )
    except:
        await callback.answer("❌ پیام یافت نشد.", show_alert=True)


# ====================== ADMIN MANAGEMENT PANEL ======================
@dp.message(F.text == "🛠 سیستم مدیریت")
async def open_management_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    kb = build_management_panel_kb()
    await message.answer("🛠 پنل مدیریت کاربران:", reply_markup=kb)


@dp.callback_query(F.data.startswith("{"))
async def management_router(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return

    try:
        data = parse_cb(callback.data)
    except Exception:
        await callback.answer("خطای داده.", show_alert=True)
        return

    action = data.get("a")

    if action == "panel":
        kb = build_management_panel_kb()
        await callback.message.edit_text("🛠 پنل مدیریت کاربران:", reply_markup=kb)

    elif action == "list":
        page = int(data.get("p", 1))
        await send_users_page(callback, page, banned_only=False)

    elif action == "banned":
        page = int(data.get("p", 1))
        await send_users_page(callback, page, banned_only=True)

    elif action == "profile":
        uid = int(data.get("u"))
        await send_user_profile(callback, uid)

    elif action == "ban":
        uid = int(data.get("u"))
        session = Session()
        try:
            licenses = session.query(License).filter(License.user_id == uid).all()
            if not licenses:
                await callback.answer("کاربر یافت نشد.", show_alert=True)
                return
            for lic in licenses:
                lic.banned = True
            session.commit()
        finally:
            session.close()
        await send_user_profile(callback, uid)

    elif action == "unban":
        uid = int(data.get("u"))
        session = Session()
        try:
            licenses = session.query(License).filter(License.user_id == uid).all()
            if not licenses:
                await callback.answer("کاربر یافت نشد.", show_alert=True)
                return
            for lic in licenses:
                lic.banned = False
            session.commit()
        finally:
            session.close()
        await send_user_profile(callback, uid)

    elif action == "search":
        await state.set_state(AdminState.waiting_search)
        await callback.message.edit_text(
            "🔍 آیدی عددی، یوزرنیم (بدون @) یا کد لایسنس را ارسال کنید.\n\n"
            "مثال‌ها:\n"
            "`123456789`\n"
            "`testuser`\n"
            "`ABCD-EFGH-IJKL-MNOP`",
            parse_mode="Markdown"
        )

    elif action == "back":
        kb = build_management_panel_kb()
        await callback.message.edit_text("🛠 پنل مدیریت کاربران:", reply_markup=kb)


@dp.message(AdminState.waiting_search)
async def admin_search_user(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    query = message.text.strip()
    session = Session()
    try:
        user = None

        if query.isdigit():
            user = session.query(License).filter(License.user_id == int(query)).first()
        if not user and not query.isdigit():
            user = session.query(License).filter(License.username == query).first()
        if not user and "-" in query:
            user = session.query(License).filter(License.key == query).first()

        if not user:
            await message.answer("❌ کاربر یا لایسنس یافت نشد.")
            await state.clear()
            return

        uid = user.user_id
        if not uid:
            await message.answer("❌ این لایسنس هنوز به کاربری متصل نشده.")
            await state.clear()
            return

        await state.clear()
        fake_callback = types.CallbackQuery(
            id="0",
            from_user=message.from_user,
            chat_instance="",
            message=message,
            data=make_cb("profile", u=uid)
        )
        await management_router(fake_callback, state)

    finally:
        session.close()


# ====================== MODES ======================
@dp.message(F.text == "📦 دریافت ریسورس پک ریلیز تکسچر")
async def ask_for_pack(message: types.Message):
    if is_user_banned(message.from_user.id):
        await message.answer("❌ شما از استفاده از ربات بن شده‌اید.")
        return

    user_modes[message.from_user.id] = "resource_pack"
    await message.answer("📤 لطفاً فایل ریسورس پک خود را ارسال کنید.\nفقط فرمت‌های .zip یا .mcpack")


@dp.message(F.text == "🧊 ساخت آیتم سه‌بعدی ماینکرافت")
async def minecraft_3d(message: types.Message):
    if is_user_banned(message.from_user.id):
        await message.answer("❌ شما از استفاده از ربات بن شده‌اید.")
        return

    user_modes[message.from_user.id] = "minecraft_3d"
    await message.answer("🧊 فایل PNG آیتم را ارسال کنید.")


@dp.message(F.text == "🔄 تبدیل JSON به OBJ")
async def json_to_obj_mode(message: types.Message):
    if is_user_banned(message.from_user.id):
        await message.answer("❌ شما از استفاده از ربات بن شده‌اید.")
        return

    user_modes[message.from_user.id] = "json_to_obj"
    user_data.pop(message.from_user.id, None)
    await message.answer("📤 **فایل JSON** مدل ماینکرافت را ارسال کنید.", parse_mode="Markdown")

# ====================== MINECRAFT ASSETS DOWNLOADER ======================
@dp.message(F.text == "📥 گرفتن فایل‌های ماینکرافت")
async def minecraft_assets_mode(message: types.Message):
    if is_user_banned(message.from_user.id):
        await message.answer("❌ شما از استفاده از ربات بن شده‌اید.")
        return

    user_modes[message.from_user.id] = "minecraft_assets"
    await message.answer(
        "<b>📥 نام آیتم ماینکرافت را وارد کنید</b>\n\n"
        "مثال:\n"
        "<code>diamond_sword</code>\n"
        "<code>emerald</code>\n"
        "<code>oak_planks</code>",
        parse_mode="HTML"
    )

@dp.message(F.text, lambda m: user_modes.get(m.from_user.id) == "minecraft_assets")
async def handle_minecraft_asset_name(message: types.Message):
    if is_user_banned(message.from_user.id):
        return

    raw_input = message.text.strip()
    user_id = message.from_user.id

    # ====================== NORMALIZATION & SMART SEARCH ======================
    # تبدیل فضای خالی به آندرلاین + حذف فاصله‌های اضافی
    normalized = raw_input.lower().replace(" ", "_").replace(".", "").replace("-", "_")
    
    # لیست کلمات جستجو (برای مواردی مثل golden apple)
    search_terms = [normalized]
    
    # اگر چند کلمه‌ای بود، آخرین کلمه را هم جداگانه جستجو کن (مثل apple)
    if "_" in normalized:
        parts = normalized.split("_")
        if len(parts) > 1:
            search_terms.append(parts[-1])   # مثلاً apple
            search_terms.append("_".join(parts[-2:]))  # مثلاً golden_apple

    await message.answer(f"🔍 جستجوی هوشمند برای <b>{raw_input}</b> ...", parse_mode="HTML")

    version = "26.1.2"
    base_url = f"https://assets.mcasset.cloud/{version}/assets/minecraft/"

    search_paths = ["textures/item/", "textures/block/", "models/item/", "models/block/"]

    found_files = []
    seen = set()  # جلوگیری از تکراری

    async with aiohttp.ClientSession() as session:
        for term in search_terms:
            for folder in search_paths:
                for ext in [".png", ".json"]:
                    url = f"{base_url}{folder}{term}{ext}"
                    try:
                        async with session.head(url, allow_redirects=True) as resp:
                            if resp.status == 200 and url not in seen:
                                seen.add(url)
                                display_name = f"{term}{ext}"
                                found_files.append({
                                    "name": display_name,
                                    "url": url,
                                    "type": ext
                                })
                    except:
                        pass

    if not found_files:
        await message.answer(
            "❌ هیچ فایلی پیدا نشد.\n\n"
            "نکات:\n"
            "• از آندرلاین استفاده کن (diamond_sword)\n"
            "• املای درست را چک کن\n"
            "• برای بلوک‌ها هم امتحان کن (oak_planks)",
            parse_mode="HTML"
        )
        user_modes.pop(user_id, None)
        return

    # ساخت کیبورد
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, file in enumerate(found_files[:12]):  # حداکثر ۱۲ نتیجه
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📄 {file['name']}",
                callback_data=f"asset_select:{i}:{normalized}"
            )
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="✅ ارسال انتخاب‌ها (حداکثر ۲)", callback_data="asset_send")
    ])

    await message.answer(
        f"✅ <b>{len(found_files)} فایل پیدا شد!</b>\n"
        f"جستجو شده برای: <code>{', '.join(search_terms)}</code>\n"
        "تا حداکثر ۲ فایل را انتخاب کنید و دکمه ارسال را بزنید.",
        reply_markup=kb,
        parse_mode="HTML"
    )

    user_selections[user_id] = []
    user_data[user_id] = {"files": found_files, "item_name": normalized}

# ====================== FILE HANDLER ======================
@dp.message(F.document)
async def handle_document(message: types.Message):
    user_id = message.from_user.id

    if is_user_banned(user_id):
        await message.answer("❌ شما از استفاده از ربات بن شده‌اید.")
        return

    mode = user_modes.get(user_id)
    doc = message.document

    if not doc or not mode:
        return

    # RESOURCE PACK
    if mode == "resource_pack":
        if not (doc.file_name.endswith(".zip") or doc.file_name.endswith(".mcpack")):
            await message.answer("❌ فقط ZIP یا MCPACK")
            return

        await message.answer("🔄 در حال پردازش...")
        input_path = os.path.join(INPUT_DIR, doc.file_name)
        output_name = os.path.splitext(doc.file_name)[0] + "_ui.png"
        output_path = os.path.join(OUTPUT_DIR, output_name)

        file = await bot.get_file(doc.file_id)
        await bot.download_file(file.file_path, destination=input_path)

        try:
            await run_node_processor(input_path, output_path)
            user_modes.pop(user_id, None)
            await message.answer_document(FSInputFile(output_path), caption="✅ ریسورس پک پردازش و UI ساخته شد!")
        except Exception as e:
            await message.answer(f"❌ خطا:\n{e}")

    # MINECRAFT 3D ITEM
    elif mode == "minecraft_3d":
        if not doc.file_name.lower().endswith(".png"):
            await message.answer("❌ فقط فایل PNG مجاز است")
            return

        await message.answer("🔄 در حال ساخت مدل سه‌بعدی...")
        input_path = os.path.join(INPUT_DIR, doc.file_name)
        output_obj = os.path.join(OUTPUT_DIR, os.path.splitext(doc.file_name)[0] + ".obj")

        file = await bot.get_file(doc.file_id)
        await bot.download_file(file.file_path, destination=input_path)

        try:
            output_file = await run_item3d(input_path, output_obj)
            user_modes.pop(user_id, None)
            await message.answer_document(FSInputFile(output_file), caption="✅ مدل سه‌بعدی با موفقیت ساخته شد!")
            if os.path.exists(input_path):
                os.remove(input_path)
        except Exception as e:
            await message.answer(f"❌ خطا در ساخت مدل:\n{str(e)}")

    # JSON TO OBJ - STEP 1
    elif mode == "json_to_obj":
        if not doc.file_name.lower().endswith(".json"):
            await message.answer("❌ فقط فایل JSON مجاز است.")
            return

        await message.answer("✅ JSON دریافت شد.\n\n📤 حالا **فایل تکسچر (PNG)** را ارسال کنید.")

        json_path = os.path.join(INPUT_DIR, doc.file_name)
        file = await bot.get_file(doc.file_id)
        await bot.download_file(file.file_path, destination=json_path)

        user_data[user_id] = {
            "json_path": json_path,
            "base_name": os.path.splitext(doc.file_name)[0]
        }
        user_modes[user_id] = "json_to_obj_waiting_texture"

    # JSON TO OBJ - STEP 2
    elif mode == "json_to_obj_waiting_texture":
        if not doc.file_name.lower().endswith(".png"):
            await message.answer("❌ فقط فایل PNG مجاز است.")
            return

        await message.answer("🔄 در حال ساخت OBJ + MTL + ZIP...")

        data = user_data.get(user_id)
        if not data:
            await message.answer("❌ خطا: اطلاعات مدل پیدا نشد.")
            return

        json_path = data["json_path"]
        base_name = data["base_name"]
        texture_path = os.path.join(INPUT_DIR, doc.file_name)
        output_obj = os.path.join(OUTPUT_DIR, base_name + ".obj")

        file = await bot.get_file(doc.file_id)
        await bot.download_file(file.file_path, destination=texture_path)

        try:
            await run_json_to_obj(json_path, output_obj)
            zip_path = create_zip_with_texture(base_name, output_obj, texture_path)

            await message.answer_document(
                FSInputFile(zip_path),
                caption=f"✅ تبدیل با موفقیت انجام شد!\n\n"
                        f"📦 فایل‌ها داخل ZIP:\n"
                        f"• {base_name}.obj\n"
                        f"• {base_name}.mtl\n"
                        f"• {os.path.basename(texture_path)}"
            )

        except Exception as e:
            await message.answer(f"❌ خطا:\n{str(e)}")

        finally:
            for p in [json_path, texture_path, output_obj, output_obj.replace('.obj', '.mtl')]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass
            user_modes.pop(user_id, None)
            user_data.pop(user_id, None)


# ====================== MINECRAFT ASSETS DOWNLOADER ======================
# ذخیره انتخاب‌های کاربر (user_id -> list of selected urls)
user_selections = {}

@dp.message(F.text, lambda m: user_modes.get(m.from_user.id) == "minecraft_assets")
async def handle_minecraft_asset_name(message: types.Message):
    if is_user_banned(message.from_user.id):
        return

    item_name = message.text.strip().lower().replace(".png", "").replace(".json", "")
    user_id = message.from_user.id

    await message.answer(f"🔍 جستجو برای <b>{item_name}</b> ...", parse_mode="HTML")

    version = "26.1.2"
    base_url = f"https://assets.mcasset.cloud/{version}/assets/minecraft/"

    # جستجو در پوشه‌های رایج
    search_paths = [
        f"textures/item/{item_name}",
        f"textures/block/{item_name}",
        f"models/item/{item_name}",
        f"models/block/{item_name}",
    ]

    found_files = []
    async with aiohttp.ClientSession() as session:
        for path in search_paths:
            for ext in [".png", ".json"]:
                url = f"{base_url}{path}{ext}"
                try:
                    async with session.head(url) as resp:
                        if resp.status == 200:
                            found_files.append({
                                "name": f"{item_name}{ext}",
                                "url": url,
                                "type": ext
                            })
                except:
                    pass

    if not found_files:
        await message.answer("❌ هیچ فایلی پیدا نشد. نام را دقیق‌تر بنویسید.")
        user_modes.pop(user_id, None)
        return

    # ساخت کیبورد با دکمه‌ها
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, file in enumerate(found_files):
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📄 {file['name']}",
                callback_data=f"asset_select:{i}:{item_name}"
            )
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="✅ ارسال انتخاب‌ها (حداکثر ۲)", callback_data="asset_send")
    ])

    await message.answer(
        f"✅ <b>{len(found_files)} فایل پیدا شد!</b>\n"
        "تا ۲ فایل را انتخاب کنید و سپس دکمه ارسال را بزنید.",
        reply_markup=kb,
        parse_mode="HTML"
    )

    user_selections[user_id] = []
    user_data[user_id] = {"files": found_files, "item_name": item_name}

# ================== CallbackData ==================
@dp.callback_query(F.data.startswith("asset_select:"))
async def select_asset(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    _, idx_str, item_name = callback.data.split(":", 2)
    idx = int(idx_str)

    if user_id not in user_selections:
        user_selections[user_id] = []

    if len(user_selections[user_id]) >= 2:
        await callback.answer("⚠️ فقط می‌توانید ۲ فایل انتخاب کنید!", show_alert=True)
        return

    files = user_data.get(user_id, {}).get("files", [])
    if idx < len(files):
        selected = files[idx]
        user_selections[user_id].append(selected)
        await callback.answer(f"✅ {selected['name']} انتخاب شد")

@dp.callback_query(F.data == "asset_send")
async def send_selected_assets(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    selected = user_selections.get(user_id, [])

    if not selected:
        await callback.answer("هیچ فایلی انتخاب نشده!", show_alert=True)
        return

    await callback.message.answer("📤 در حال ارسال فایل‌های انتخابی...")

    async with aiohttp.ClientSession() as session:
        for file in selected:
            try:
                async with session.get(file["url"]) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        temp_path = os.path.join(OUTPUT_DIR, file["name"])
                        with open(temp_path, "wb") as f:
                            f.write(data)

                        await callback.message.answer_document(
                            FSInputFile(temp_path),
                            caption=f"📎 <b>{file['name']}</b>",
                            parse_mode="HTML"
                        )
                        os.remove(temp_path)
            except Exception as e:
                await callback.message.answer(f"❌ خطا در ارسال {file['name']}")

    await callback.message.answer("✅ تمام فایل‌های انتخابی ارسال شدند!")
    
    user_selections.pop(user_id, None)
    user_data.pop(user_id, None)
    user_modes.pop(user_id, None)

# ====================== ASSET SELECTION CALLBACKS ======================
user_selections = {}  # user_id -> list of selected files

@dp.callback_query(F.data.startswith("asset_select:"))
async def select_asset(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    _, idx_str, _ = callback.data.split(":", 2)
    idx = int(idx_str)

    if user_id not in user_selections:
        user_selections[user_id] = []

    if len(user_selections[user_id]) >= 2:
        await callback.answer("⚠️ فقط می‌توانید ۲ فایل انتخاب کنید!", show_alert=True)
        return

    files = user_data.get(user_id, {}).get("files", [])
    if idx < len(files):
        selected = files[idx]
        user_selections[user_id].append(selected)
        await callback.answer(f"✅ {selected['name']} انتخاب شد")


@dp.callback_query(F.data == "asset_send")
async def send_selected_assets(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    selected = user_selections.get(user_id, [])

    if not selected:
        await callback.answer("هیچ فایلی انتخاب نشده!", show_alert=True)
        return

    await callback.message.answer("📤 در حال ارسال فایل‌های انتخابی...")

    async with aiohttp.ClientSession() as session:
        for file in selected:
            try:
                async with session.get(file["url"]) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        temp_path = os.path.join(OUTPUT_DIR, file["name"])
                        with open(temp_path, "wb") as f:
                            f.write(data)

                        await callback.message.answer_document(
                            FSInputFile(temp_path),
                            caption=f"📎 <b>{file['name']}</b>",
                            parse_mode="HTML"
                        )
                        os.remove(temp_path)
            except:
                await callback.message.answer(f"❌ خطا در ارسال {file['name']}")

    await callback.message.answer("✅ تمام فایل‌های انتخابی ارسال شدند!")

    user_selections.pop(user_id, None)
    user_data.pop(user_id, None)
    user_modes.pop(user_id, None)
    
# ====================== MAIN ======================
async def main():
    print("🚀 Bot started successfully")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
