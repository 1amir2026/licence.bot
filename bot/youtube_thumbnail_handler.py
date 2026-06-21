# -*- coding: utf-8 -*-
"""
ماژول دانلود تامنیل ویدیوهای یوتیوب
------------------------------------
کاربر لینک ویدیوی یوتیوب یا اسم دقیق ویدیو را می‌فرستد، بات کیفیت‌های موجود
تامنیل (تا بالاترین کیفیتی که یوتیوب برای آن ویدیو دارد - معمولاً تا حد
Full HD / گاهی بالاتر، و در صورت نبود "تا جایی که موجود است") را پیدا کرده
و به صورت دکمه نمایش می‌دهد. با انتخاب کاربر، فایل تامنیل با همان کیفیت
به صورت سند (برای حفظ کیفیت اصلی) ارسال می‌شود.

نکته مهم: یوتیوب به صورت رسمی "تامنیل 4K" ندارد؛ بالاترین کیفیت موجود
معمولاً maxresdefault است که بسته به ویدیو می‌تواند از 120x90 تا حدود
1920x1080 (و به ندرت بالاتر) باشد. این ماژول هر چقدر که واقعاً موجود
باشد را پیدا و به ترتیب از بهترین به ضعیف‌ترین نمایش می‌دهد.
"""

import io
import json
import os
import re
import asyncio
from urllib.parse import quote

import aiohttp
from aiogram import F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ====================== CONSTANTS ======================
YT_BUTTON_TEXT = "🖼 دانلود تامنیل یوتیوب"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# کیفیت‌های استاندارد تامنیل یوتیوب، از بالاترین به پایین‌ترین
THUMBNAIL_VARIANTS = ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"]

# اندازه‌ی تصویر جای‌گزین (placeholder) که یوتیوب برای کیفیت‌های ناموجود برمی‌گرداند
PLACEHOLDER_SIZE = (120, 90)

CALLBACK_PREFIX = "ytq:"
CANCEL_CALLBACK = "ytthumb_cancel"

VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
URL_ID_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtube\.com/shorts/|youtu\.be/|"
    r"youtube\.com/embed/|youtube\.com/v/)([A-Za-z0-9_-]{11})"
)

# حافظه موقت در RAM: video_id -> {"title": str, "candidates": {quality: data}}
_yt_cache = {}


# ====================== FSM ======================
class YoutubeThumbState(StatesGroup):
    waiting_input = State()


# ====================== HELPERS ======================
def _extract_video_id(text: str):
    text = text.strip()

    m = URL_ID_RE.search(text)
    if m:
        return m.group(1)

    # اگر کاربر مستقیم آیدی ۱۱ کاراکتری ویدیو را فرستاده باشد
    if VIDEO_ID_RE.fullmatch(text):
        return text

    return None


async def _search_youtube(session: aiohttp.ClientSession, query: str):
    """جستجوی نام ویدیو در یوتیوب؛ خروجی (video_id, title) اولین نتیجه یا (None, None)"""
    url = f"https://www.youtube.com/results?search_query={quote(query)}"
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None, None
            html = await resp.text(errors="ignore")
    except Exception:
        return None, None

    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html)
    if not m:
        m = re.search(r"ytInitialData\"\]\s*=\s*(\{.*?\});", html)
    if not m:
        return None, None

    try:
        data = json.loads(m.group(1))
    except Exception:
        return None, None

    def find_video(obj):
        if isinstance(obj, dict):
            if "videoRenderer" in obj:
                vr = obj["videoRenderer"]
                vid = vr.get("videoId")
                title = ""
                try:
                    title = vr["title"]["runs"][0]["text"]
                except Exception:
                    title = vr.get("title", {}).get("simpleText", "") or ""
                if vid:
                    return vid, title
            for v in obj.values():
                res = find_video(v)
                if res:
                    return res
        elif isinstance(obj, list):
            for item in obj:
                res = find_video(item)
                if res:
                    return res
        return None

    result = find_video(data)
    if result:
        return result
    return None, None


async def _check_thumbnail(session: aiohttp.ClientSession, video_id: str, quality: str):
    """بررسی می‌کند تامنیل با این کیفیت برای ویدیو واقعاً موجود است یا یک تصویر جای‌گزین است"""
    url = f"https://i.ytimg.com/vi/{video_id}/{quality}.jpg"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            content = await resp.read()
    except Exception:
        return None

    if not content:
        return None

    width = height = None
    if PIL_AVAILABLE:
        try:
            img = Image.open(io.BytesIO(content))
            width, height = img.size
        except Exception:
            return None

        if quality != "default" and (width, height) == PLACEHOLDER_SIZE:
            # یوتیوب برای کیفیت‌های ناموجود، تصویر جای‌گزین ۱۲۰x۹۰ برمی‌گرداند
            return None
    else:
        # بدون PIL، با اندازه فایل تخمین می‌زنیم (تصویر جای‌گزین معمولاً خیلی کوچک است)
        if quality != "default" and len(content) < 2000:
            return None

    return {
        "quality": quality,
        "width": width,
        "height": height,
        "content": content,
        "size": len(content),
    }


async def _gather_thumbnails(video_id: str):
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[
            _check_thumbnail(session, video_id, q) for q in THUMBNAIL_VARIANTS
        ])

    candidates = [r for r in results if r]

    # حذف کیفیت‌های تکراری با وضوح یکسان (وقتی PIL نباشد ابعاد نداریم، پس بر اساس quality یکتا می‌مانند)
    seen = set()
    unique = []
    for c in candidates:
        key = (c["width"], c["height"]) if c["width"] else c["quality"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    unique.sort(key=lambda c: (c["width"] or 0) * (c["height"] or 0), reverse=True)
    return unique


def _quality_label(c: dict) -> str:
    w, h = c.get("width"), c.get("height")
    if w and h:
        if h >= 2160:
            tag = " (4K)"
        elif h >= 1440:
            tag = " (2K)"
        elif h >= 1080:
            tag = " (Full HD)"
        elif h >= 720:
            tag = " (HD)"
        else:
            tag = ""
        return f"🖼 {w}x{h}{tag}"
    return f"🖼 {c.get('quality', 'نامشخص')}"


def _safe_filename(title: str, video_id: str, width, height) -> str:
    base = re.sub(r"[^\w\-]+", "_", title or video_id).strip("_")[:50] or video_id
    if width and height:
        return f"{base}_{width}x{height}.jpg"
    return f"{base}.jpg"


# ====================== REGISTER ======================
def register_youtube_thumbnail_handlers(dp, bot, get_access_block_message=None):
    """
    این تابع باید در bot.py صدا زده شود:
        register_youtube_thumbnail_handlers(dp, bot, get_access_block_message)
    پارامتر get_access_block_message اختیاری است؛ تابعی است که با گرفتن user_id
    در صورت نبود دسترسی، پیام خطا برمی‌گرداند (یا None اگر دسترسی آزاد بود).
    """

    def _check_access(user_id: int):
        if get_access_block_message:
            return get_access_block_message(user_id)
        return None

    @dp.message(F.text == YT_BUTTON_TEXT)
    async def yt_thumb_entry(message: types.Message, state: FSMContext):
        block_msg = _check_access(message.from_user.id)
        if block_msg:
            await message.answer(block_msg)
            return

        await state.set_state(YoutubeThumbState.waiting_input)
        await message.answer(
            "🎬 <b>دانلود تامنیل ویدیو یوتیوب</b>\n\n"
            "➡️ لینک ویدیوی یوتیوب رو بفرست، یا اسم دقیق ویدیو رو تایپ کن.\n\n"
            "مثال لینک‌های قابل قبول:\n"
            "<code>https://www.youtube.com/watch?v=xxxxxxxxxxx</code>\n"
            "<code>https://youtu.be/xxxxxxxxxxx</code>\n"
            "<code>https://youtube.com/shorts/xxxxxxxxxxx</code>\n\n"
            "بعد از پیدا شدن ویدیو، می‌تونی از بین کیفیت‌های واقعاً موجود "
            "(تا بالاترین چیزی که یوتیوب برای اون ویدیو داره) انتخاب کنی.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ لغو", callback_data=CANCEL_CALLBACK)
            ]])
        )

    @dp.callback_query(F.data == CANCEL_CALLBACK)
    async def yt_thumb_cancel(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        try:
            await callback.message.edit_text("❌ عملیات لغو شد.")
        except Exception:
            pass
        await callback.answer()

    @dp.message(YoutubeThumbState.waiting_input)
    async def yt_thumb_receive(message: types.Message, state: FSMContext):
        block_msg = _check_access(message.from_user.id)
        if block_msg:
            await state.clear()
            await message.answer(block_msg)
            return

        text = (message.text or "").strip()
        if not text:
            await message.answer("❌ لطفاً یک لینک یا اسم ویدیو بفرست (به‌صورت متن).")
            return

        wait_msg = await message.answer("🔎 در حال جستجو و بررسی کیفیت‌های تامنیل...")

        try:
            video_id = _extract_video_id(text)
            title = None

            if not video_id:
                async with aiohttp.ClientSession() as session:
                    video_id, title = await _search_youtube(session, text)

                if not video_id:
                    await wait_msg.edit_text(
                        "❌ ویدیویی با این مشخصات پیدا نشد.\n"
                        "لطفاً لینک مستقیم ویدیو رو بفرست یا اسم دقیق‌تری وارد کن."
                    )
                    await state.clear()
                    return

            candidates = await _gather_thumbnails(video_id)

            if not candidates:
                await wait_msg.edit_text("❌ هیچ تامنیلی برای این ویدیو پیدا نشد.")
                await state.clear()
                return

            _yt_cache[video_id] = {
                "title": title or text,
                "candidates": {c["quality"]: c for c in candidates},
            }

            rows = []
            for c in candidates:
                rows.append([InlineKeyboardButton(
                    text=_quality_label(c),
                    callback_data=f"{CALLBACK_PREFIX}{video_id}:{c['quality']}"
                )])
            rows.append([InlineKeyboardButton(text="❌ لغو", callback_data=CANCEL_CALLBACK)])

            best_label = _quality_label(candidates[0])

            await wait_msg.edit_text(
                "✅ ویدیو پیدا شد!\n"
                f"📌 بهترین کیفیت موجود: {best_label}\n\n"
                "کیفیت مورد نظر برای دانلود رو انتخاب کن 👇",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
            )
            await state.clear()

        except Exception as e:
            try:
                await wait_msg.edit_text(f"❌ خطا در پردازش:\n<code>{str(e)[:300]}</code>", parse_mode="HTML")
            except Exception:
                await message.answer(f"❌ خطا در پردازش:\n{str(e)[:300]}")
            await state.clear()

    @dp.callback_query(F.data.startswith(CALLBACK_PREFIX))
    async def yt_thumb_quality_chosen(callback: types.CallbackQuery):
        block_msg = _check_access(callback.from_user.id)
        if block_msg:
            await callback.answer(block_msg, show_alert=True)
            return

        try:
            payload = callback.data[len(CALLBACK_PREFIX):]
            video_id, quality = payload.rsplit(":", 1)
        except Exception:
            await callback.answer("❌ درخواست نامعتبر.", show_alert=True)
            return

        cache = _yt_cache.get(video_id)
        if not cache or quality not in cache["candidates"]:
            await callback.answer("❌ این درخواست منقضی شده، لطفاً دوباره لینک رو بفرست.", show_alert=True)
            return

        await callback.answer("⏳ در حال ارسال...")

        c = cache["candidates"][quality]
        filename = _safe_filename(cache["title"], video_id, c.get("width"), c.get("height"))
        tmp_path = f"/tmp/ytthumb_{video_id}_{quality}.jpg"

        try:
            with open(tmp_path, "wb") as f:
                f.write(c["content"])

            res_text = f"{c['width']}x{c['height']}" if c.get("width") else c["quality"]
            await callback.message.answer_document(
                FSInputFile(tmp_path, filename=filename),
                caption=f"🖼 {cache['title']}\n📐 کیفیت: {res_text}"
            )
        except Exception as e:
            await callback.message.answer(f"❌ خطا در ارسال فایل:\n{str(e)[:200]}")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
