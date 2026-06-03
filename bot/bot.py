import asyncio
import os
import random
import string
import zipfile
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile

from config import TOKEN, ADMIN_ID
from database import Session, License

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_modes = {}
user_data = {}

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
        "node", NODE_SCRIPT, input_path, output_path, str(xp_percent), str(upscale_rate),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=PROCESSOR_DIR
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Node processor failed: {stderr.decode()}")


async def run_item3d(input_path: str, output_obj: str):
    proc = await asyncio.create_subprocess_exec(
        "node", ITEM3D_SCRIPT, input_path, output_obj,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=PROCESSOR_DIR
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Item3D failed:\n{stderr.decode()}")
    zip_path = output_obj.replace(".obj", ".zip")
    return zip_path if os.path.exists(zip_path) else output_obj


async def run_json_to_obj(json_path: str, output_obj: str):
    proc = await asyncio.create_subprocess_exec(
        "node", JSON_TO_OBJ_SCRIPT, json_path, output_obj,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=PROCESSOR_DIR
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"JSON to OBJ failed:\n{stderr.decode()}")
    return output_obj


def create_zip_with_texture(base_name: str, obj_path: str, texture_path: str):
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
        z.write(mtl_path, os.path.basename(mtl_path))
        z.write(texture_path, texture_name)
    return zip_path


# ====================== BROADCAST (پشتیبانی کامل از عکس، ویدیو، فایل و متن) ======================
async def broadcast_message(message: types.Message):
    session = Session()
    users = session.query(License.user_id).filter(License.user_id.isnot(None)).distinct().all()
    session.close()

    success = 0
    for (user_id,) in users:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except:
            pass
    return success


# ====================== COMMANDS ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    if is_admin(message.from_user.id):
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔑 ساخت لایسنس جدید")],
                [KeyboardButton(text="📢 اطلاع‌رسانی به کاربران")]
            ],
            resize_keyboard=True
        )
        await message.answer("👋 سلام ادمین عزیز!", reply_markup=keyboard)
    else:
        await message.answer("سلام! کد لایسنس خود را ارسال کنید.\n\nبرای دریافت لایسنس به @Amirmah198 مراجعه کنید.")


@dp.message(F.text == "🔑 ساخت لایسنس جدید")
async def create_license(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    key = generate_license()
    session = Session()
    session.add(License(key=key))
    session.commit()
    session.close()
    await message.answer(f"✅ لایسنس جدید ساخته شد:\n\n`{key}`\n\nکپی کنید.")


@dp.message(F.text == "📢 اطلاع‌رسانی به کاربران")
async def broadcast_mode(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_modes[message.from_user.id] = "broadcast"
    await message.answer("📢 حالت اطلاع‌رسانی فعال شد.\n\nهر چیزی که بخواهید (متن، عکس، ویدیو، فایل، گیف و ...) بفرستید.")


# ====================== LICENSE CHECK ======================
@dp.message(F.text.regexp(LICENSE_REGEX))
async def check_license(message: types.Message):
    if is_admin(message.from_user.id):
        return

    session = Session()
    license_glb = session.query(License).filter_by(key=message.text.strip(), used=False).first()

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
        await message.answer("✅ لایسنس با موفقیت فعال شد!\nبه پنل خوش آمدید 🎉", reply_markup=keyboard)
    else:
        await message.answer("❌ لایسنس نامعتبر یا قبلاً استفاده شده.")

    session.close()


# ====================== MODES ======================
@dp.message(F.text == "📦 دریافت ریسورس پک ریلیز تکسچر")
async def ask_for_pack(message: types.Message):
    user_modes[message.from_user.id] = "resource_pack"
    await message.answer("📤 فایل ریسورس پک (.zip یا .mcpack) را ارسال کنید.")


@dp.message(F.text == "🧊 ساخت آیتم سه‌بعدی ماینکرافت")
async def minecraft_3d_mode(message: types.Message):
    user_modes[message.from_user.id] = "minecraft_3d"
    await message.answer("🧊 فایل PNG آیتم را ارسال کنید.")


@dp.message(F.text == "🔄 تبدیل JSON به OBJ")
async def json_to_obj_mode(message: types.Message):
    user_modes[message.from_user.id] = "json_to_obj"
    user_data.pop(message.from_user.id, None)
    await message.answer("📤 فایل **JSON** مدل ماینکرافت را ارسال کنید.")


# ====================== BROADCAST HANDLER ======================
@dp.message()
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    mode = user_modes.get(user_id)

    if mode == "broadcast" and is_admin(user_id):
        count = await broadcast_message(message)
        await message.answer(f"✅ اطلاع‌رسانی با موفقیت ارسال شد!\n\n📨 به {count} کاربر فرستاده شد.")
        user_modes.pop(user_id, None)
        return


# ====================== DOCUMENT HANDLER ======================
@dp.message(F.document)
async def handle_document(message: types.Message):
    user_id = message.from_user.id
    mode = user_modes.get(user_id)
    doc = message.document

    if not doc or not mode:
        return

    # Resource Pack
    if mode == "resource_pack":
        if not doc.file_name.lower().endswith(('.zip', '.mcpack')):
            await message.answer("❌ فقط فایل zip یا mcpack مجاز است.")
            return
        await message.answer("🔄 در حال پردازش ریسورس پک...")
        # (کد پردازش resource pack را بعداً کامل می‌کنیم اگر نیاز بود)

    # Minecraft 3D Item
    elif mode == "minecraft_3d":
        if not doc.file_name.lower().endswith('.png'):
            await message.answer("❌ فقط فایل PNG مجاز است.")
            return
        await message.answer("🔄 در حال ساخت مدل سه‌بعدی...")
        # (کد پردازش item3d را بعداً کامل می‌کنیم)

    # JSON to OBJ - مرحله اول
    elif mode == "json_to_obj":
        if not doc.file_name.lower().endswith('.json'):
            await message.answer("❌ فقط فایل JSON مجاز است.")
            return

        json_path = os.path.join(INPUT_DIR, doc.file_name)
        file_info = await bot.get_file(doc.file_id)
        await bot.download_file(file_info.file_path, json_path)

        user_data[user_id] = {
            "json_path": json_path,
            "base_name": os.path.splitext(doc.file_name)[0]
        }
        user_modes[user_id] = "json_to_obj_waiting_texture"

        await message.answer("✅ JSON دریافت شد.\n\n📤 حالا فایل **تکسچر PNG** را ارسال کنید.")

    # JSON to OBJ - مرحله دوم (Texture)
    elif mode == "json_to_obj_waiting_texture":
        if not doc.file_name.lower().endswith('.png'):
            await message.answer("❌ فقط فایل PNG مجاز است.")
            return

        data = user_data.get(user_id)
        if not data:
            await message.answer("❌ خطا: اطلاعات مدل پیدا نشد.")
            return

        texture_path = os.path.join(INPUT_DIR, doc.file_name)
        file_info = await bot.get_file(doc.file_id)
        await bot.download_file(file_info.file_path, texture_path)

        json_path = data["json_path"]
        base_name = data["base_name"]
        output_obj = os.path.join(OUTPUT_DIR, f"{base_name}.obj")

        await message.answer("🔄 در حال تبدیل JSON به OBJ + ZIP...")

        try:
            await run_json_to_obj(json_path, output_obj)
            zip_path = create_zip_with_texture(base_name, output_obj, texture_path)

            await message.answer_document(
                FSInputFile(zip_path),
                caption=f"✅ تبدیل با موفقیت انجام شد!\n\n"
                        f"📦 شامل:\n"
                        f"• {base_name}.obj\n"
                        f"• {base_name}.mtl\n"
                        f"• {os.path.basename(texture_path)}"
            )
        except Exception as e:
            await message.answer(f"❌ خطا:\n{str(e)}")
        finally:
            # Cleanup
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
    print("🚀 Bot started successfully with Advanced Broadcast")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
