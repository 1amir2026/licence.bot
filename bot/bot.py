import asyncio
import os
import random
import string
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile

from config import TOKEN, ADMIN_ID
from database import Session, License

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_modes = {}

# ====================== PATHS ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSOR_DIR = os.path.join(BASE_DIR, "..", "processor")

NODE_SCRIPT = os.path.join(PROCESSOR_DIR, "processor.mjs")
ITEM3D_SCRIPT = os.path.join(PROCESSOR_DIR, "item3d.mjs")

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
    """اجرای مستقیم item3d.mjs"""
    proc = await asyncio.create_subprocess_exec(
        "node", ITEM3D_SCRIPT, input_path, output_obj,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=PROCESSOR_DIR
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Item3D failed:\n{stderr.decode()}")

    # خروجی اصلی ZIP است
    zip_path = output_obj.replace(".obj", ".zip")
    if os.path.exists(zip_path):
        return zip_path
    elif os.path.exists(output_obj):
        return output_obj
    else:
        raise RuntimeError("No output file was generated")


# ====================== COMMANDS ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    if is_admin(message.from_user.id):
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔑 ساخت لایسنس جدید")]],
            resize_keyboard=True
        )
        await message.answer("👋 سلام شوهر خوبم!\n\nبرای ساخت لایسنس جدید دکمه زیر را بزن:", reply_markup=keyboard)
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
                [KeyboardButton(text="🧊 ساخت آیتم سه‌بعدی ماینکرافت")]
            ],
            resize_keyboard=True
        )

        await message.answer("✅ لایسنس فعال شد!\n\nبه پنل خوش آمدید 🎉", reply_markup=keyboard)
    else:
        await message.answer("❌ لایسنس نامعتبر یا قبلاً استفاده شده.")

    session.close()


# ====================== MODES ======================
@dp.message(F.text == "📦 دریافت ریسورس پک ریلیز تکسچر")
async def ask_for_pack(message: types.Message):
    user_modes[message.from_user.id] = "resource_pack"
    await message.answer("📤 لطفاً فایل ریسورس پک خود را ارسال کنید.\nفقط فرمت‌های .zip یا .mcpack")


@dp.message(F.text == "🧊 ساخت آیتم سه‌بعدی ماینکرافت")
async def minecraft_3d(message: types.Message):
    user_modes[message.from_user.id] = "minecraft_3d"
    await message.answer("🧊 فایل PNG آیتم را ارسال کنید.")


# ====================== FILE HANDLER ======================
@dp.message(F.document)
async def handle_document(message: types.Message):
    mode = user_modes.get(message.from_user.id)
    doc = message.document

    if not doc or not mode:
        return

    # ---------------- RESOURCE PACK ----------------
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
            user_modes.pop(message.from_user.id, None)

            await message.answer_document(
                FSInputFile(output_path),
                caption="✅ ریسورس پک پردازش و UI ساخته شد!"
            )
        except Exception as e:
            await message.answer(f"❌ خطا:\n{e}")

    # ---------------- MINECRAFT 3D ITEM ----------------
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
            user_modes.pop(message.from_user.id, None)

            await message.answer_document(
                FSInputFile(output_file),
                caption="✅ مدل سه‌بعدی با موفقیت ساخته شد!\n(شامل OBJ + MTL + PNG)"
            )

            # پاکسازی فایل ورودی
            if os.path.exists(input_path):
                os.remove(input_path)

        except Exception as e:
            await message.answer(f"❌ خطا در ساخت مدل:\n{str(e)}")


# ====================== MAIN ======================
async def main():
    print("🚀 Bot started successfully")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
