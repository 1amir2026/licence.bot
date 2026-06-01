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

# مسیرهای مربوط به پردازشگر Node
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSOR_DIR = os.path.join(BASE_DIR, "..", "processor")
NODE_SCRIPT = os.path.join(PROCESSOR_DIR, "processor.mjs")

INPUT_DIR = os.path.join(PROCESSOR_DIR, "input")
OUTPUT_DIR = os.path.join(PROCESSOR_DIR, "output")
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_license():
    chars = string.ascii_uppercase + string.digits
    return '-'.join(''.join(random.choices(chars, k=4)) for _ in range(4))


def is_admin(user_id: int):
    return user_id == ADMIN_ID


@dp.message(Command("start"))
async def start(message: types.Message):
    if is_admin(message.from_user.id):
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔑 ساخت لایسنس جدید")]],
            resize_keyboard=True
        )
        await message.answer("👋 سلام ادمین!\n\nبرای ساخت لایسنس جدید دکمه زیر را بزن:", reply_markup=keyboard)
    else:
        await message.answer(
            "👋 سلام!\n\n"
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
    await message.answer(f"✅ لایسنس جدید:\n\n`{key}`\n\nکپی کن و بفرست.")


@dp.message()
async def check_license(message: types.Message):
    if is_admin(message.from_user.id):
        return

    session = Session()
    license_obj = session.query(License).filter_by(
        key=message.text.strip(), used=False
    ).first()

    if license_obj:
        license_obj.used = True
        license_obj.user_id = message.from_user.id
        license_obj.used_at = datetime.utcnow()
        session.commit()

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📦 دریافت ریسورس پک ریلیز تکسچر")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            "✅ لایسنس فعال شد!\n\nبه پنل خوش آمدید 🎉",
            reply_markup=keyboard
        )
    else:
        await message.answer("❌ لایسنس نامعتبر یا قبلاً استفاده شده.")

    session.close()


@dp.message(F.text == "📦 دریافت ریسورس پک ریلیز تکسچر")
async def ask_for_pack(message: types.Message):
    await message.answer(
        "📤 لطفاً فایل ریسورس پک خود را ارسال کنید.\n"
        "فقط فرمت‌های .zip یا .mcpack قابل قبول هستند."
    )


async def run_node_processor(input_path: str, output_path: str,
                             xp_percent: float = 0.7, upscale_rate: int = 1):
    proc = await asyncio.create_subprocess_exec(
        "node",
        NODE_SCRIPT,
        input_path,
        output_path,
        str(xp_percent),
        str(upscale_rate),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=PROCESSOR_DIR
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"Node processor failed:\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
        )


@dp.message(F.document)
async def handle_pack_file(message: types.Message):
    doc = message.document

    if not (doc.file_name.endswith(".zip") or doc.file_name.endswith(".mcpack")):
        await message.answer("❌ فقط فایل‌های ZIP یا MCPACK قابل قبول هستند.")
        return

    await message.answer("🔄 فایل دریافت شد. در حال پردازش... (ممکن است کمی طول بکشد)")

    input_path = os.path.join(INPUT_DIR, doc.file_name)
    output_name = os.path.splitext(doc.file_name)[0] + "_ui.png"
    output_path = os.path.join(OUTPUT_DIR, output_name)

    await bot.download(doc, destination=input_path)

    try:
        await run_node_processor(
            input_path=input_path,
            output_path=output_path,
            xp_percent=0.7,   # هر مقداری که دوست داری
            upscale_rate=1    # هر مقداری که دوست داری
        )
    except Exception as e:
        await message.answer(f"❌ خطا در پردازش پک:\n{e}")
        return

    if not os.path.exists(output_path):
        await message.answer("❌ پردازش انجام نشد. خروجی پیدا نشد.")
        return

    await message.answer_document(
        FSInputFile(output_path),
        caption="✅ پردازش انجام شد! این هم UI نهایی:"
    )


async def main():
    print("🚀 بات شروع شد...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
