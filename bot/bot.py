import asyncio
import os
import random
import string
import zipfile
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import TOKEN, ADMIN_ID
from database import Session, License

# ====================== FSM ======================
class BroadcastState(StatesGroup):
    waiting_message = State()
    waiting_buttons = State()

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


# ====================== COMMANDS ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    if is_admin(message.from_user.id):
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔑 ساخت لایسنس جدید")],
                [KeyboardButton(text="📢 اطلاع‌رسانی")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "سلام ادمین گرامی\n\nبرای ساخت لایسنس جدید دکمه زیر را بزن:",
            reply_markup=keyboard
        )
    else:
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

    session = Session()
    license_glb = session.query(License).filter_by(
        key=message.text.strip(), used=False
    ).first()

    if license_glb:
        license_glb.used = True
        license_glb.user_id = message.from_user.id
        license_glb.used_at = datetime.utcnow()
        session.commit()

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📦 دریافت ریسورس پک ریلیز تکسچر")],
                [KeyboardButton(text="🧊 ساخت آیتم سه‌بعدی ماینکرافت")],
                [KeyboardButton(text="🔄 تبدیل JSON به OBJ")]
            ],
            resize_keyboard=True
        )

        await message.answer("✅ لایسنس فعال شد!\n\nبه پنل خوش آمدید 🎉", reply_markup=keyboard)
    else:
        await message.answer("❌ لایسنس نامعتبر یا قبلاً استفاده شده.")

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

keyboard = types.InlineKeyboardMarkup()
keyboard.add(types.InlineKeyboardButton(text="➕ افزودن دکمه", callback_data="add_btn"))
keyboard.add(types.InlineKeyboardButton(text="✔️ تکمیل و ارسال", callback_data="finish"))
keyboard.add(types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="back"))

await state.set_state(BroadcastState.waiting_buttons)
await message.answer("پیام ذخیره شد.\n\nاکنون می‌توانید دکمه اضافه کنید.", reply_markup=keyboard)

@dp.callback_query(F.data == "finish")
async def finish_broadcast(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    content = data["content"]
    buttons = data["buttons"]

    kb = types.InlineKeyboardMarkup()
    for btn in buttons:
        if btn["action"].startswith("copy:"):
            msg_id = btn["action"].replace("copy:", "")
            kb.add(types.InlineKeyboardButton(text=btn["title"], callback_data=f"copy_{msg_id}"))
        else:
            kb.add(types.InlineKeyboardButton(text=btn["title"], url=btn["action"]))

    session = Session()
    users = session.query(License).filter(License.used == True).all()

    for u in users:
        try:
            if content["type"] == "text":
                await bot.send_message(u.user_id, content["text"], reply_markup=kb)
            elif content["type"] == "photo":
                await bot.send_photo(u.user_id, content["file_id"], caption=content["caption"], reply_markup=kb)
            elif content["type"] == "video":
                await bot.send_video(u.user_id, content["file_id"], caption=content["caption"], reply_markup=kb)
            elif content["type"] == "document":
                await bot.send_document(u.user_id, content["file_id"], caption=content["caption"], reply_markup=kb)
        except:
            pass

    await state.clear()
    await callback.message.answer("✅ اطلاع‌رسانی با موفقیت ارسال شد.")

@dp.callback_query(F.data == "back")
async def back_to_admin(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔑 ساخت لایسنس جدید")],
            [KeyboardButton(text="📢 اطلاع‌رسانی")]
        ],
        resize_keyboard=True
    )

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

    await message.answer(f"دکمه «{title}» اضافه شد.")

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


# ====================== MODES ======================
@dp.message(F.text == "📦 دریافت ریسورس پک ریلیز تکسچر")
async def ask_for_pack(message: types.Message):
    user_modes[message.from_user.id] = "resource_pack"
    await message.answer("📤 لطفاً فایل ریسورس پک خود را ارسال کنید.\nفقط فرمت‌های .zip یا .mcpack")


@dp.message(F.text == "🧊 ساخت آیتم سه‌بعدی ماینکرافت")
async def minecraft_3d(message: types.Message):
    user_modes[message.from_user.id] = "minecraft_3d"
    await message.answer("🧊 فایل PNG آیتم را ارسال کنید.")


@dp.message(F.text == "🔄 تبدیل JSON به OBJ")
async def json_to_obj_mode(message: types.Message):
    user_modes[message.from_user.id] = "json_to_obj"
    user_data.pop(message.from_user.id, None)
    await message.answer("📤 **فایل JSON** مدل ماینکرافت را ارسال کنید.")


# ====================== FILE HANDLER ======================
@dp.message(F.document)
async def handle_document(message: types.Message):
    user_id = message.from_user.id
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


# ====================== MAIN ======================
async def main():
    print("🚀 Bot started successfully")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
