from __future__ import annotations

import html
import logging

from aiogram import F, Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database import Database
from app.services.pdf_page_renderer import render_telegram_pdf_page

logger = logging.getLogger(__name__)
router = Router(name="bot_page_images")


def _pages(lesson) -> list[dict]:
    import json
    try:
        pages = json.loads(lesson["key_points"] or "[]")
        if isinstance(pages, list) and pages and isinstance(pages[0], dict) and "page" in pages[0]:
            return pages
    except Exception:
        pass
    return []


def _keyboard(lesson_id: int, pages: list[dict], index: int) -> InlineKeyboardMarkup:
    rows = []
    numbers = [int(item.get("page", i + 1)) for i, item in enumerate(pages)]
    for start in range(0, len(numbers), 6):
        rows.append([
            InlineKeyboardButton(
                text=(f"🔵 {numbers[i]}" if i == index else f"📄 {numbers[i]}"),
                callback_data=f"bot_page:{lesson_id}:{i}",
            )
            for i in range(start, min(start + 6, len(numbers)))
        ])

    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابقة", callback_data=f"bot_page:{lesson_id}:{index - 1}"))
    if index < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="التالية ➡️", callback_data=f"bot_page:{lesson_id}:{index + 1}"))
    if nav:
        rows.append(nav)

    if index == len(pages) - 1:
        rows.append([InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"bot_quiz:{lesson_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ قائمة الدرس", callback_data=f"lesson:{lesson_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _caption(lesson, item: dict, index: int, total: int) -> str:
    summary = str(item.get("summary") or "").strip()
    points = item.get("key_points") or []
    lines = [
        f"📖 <b>{html.escape(str(lesson['file_name']))}</b>",
        f"📄 <b>الصفحة {index + 1} من {total}</b>",
        "⚙️ <b>البوت والأتمتة — Python</b>",
    ]
    if summary:
        lines += ["", "🧠 <b>ملخص الصفحة</b>", html.escape(summary[:500])]
    if points:
        lines += ["", "📌 <b>أهم النقاط</b>"]
        lines += [f"• {html.escape(str(point))}" for point in points[:3]]
    return "\n".join(lines)[:1000]


async def _show(callback: CallbackQuery, lesson, index: int, bot: Bot) -> None:
    pages = _pages(lesson)
    if not pages:
        await callback.answer("❌ لا توجد صفحات محفوظة لهذا الدرس.", show_alert=True)
        return
    index = max(0, min(index, len(pages) - 1))
    item = pages[index]
    pdf_page = int(item.get("page", index + 1)) - 1
    try:
        image = await render_telegram_pdf_page(bot, str(lesson["file_id"] or ""), pdf_page)
        photo = BufferedInputFile(image, filename=f"lesson_{lesson['id']}_page_{index + 1}.jpg")
        caption = _caption(lesson, item, index, len(pages))
        if callback.message:
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                pass
            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=photo,
                caption=caption,
                reply_markup=_keyboard(int(lesson["id"]), pages, index),
            )
        await callback.answer()
    except Exception as exc:
        logger.exception("Could not render bot lesson page")
        # Do not bring back the old 'PDF missing on server' dependency.
        # Explain the actual failure and keep navigation available.
        try:
            await callback.answer("⚠️ تعذر عرض صورة الصفحة الآن.", show_alert=True)
        except Exception:
            pass


@router.callback_query(F.data.startswith("pages:"))
async def open_pages(callback: CallbackQuery, db: Database, bot: Bot) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await _show(callback, lesson, 0, bot)


@router.callback_query(F.data.startswith("bot_page:"))
async def bot_page(callback: CallbackQuery, db: Database, bot: Bot) -> None:
    try:
        _, lesson_text, index_text = callback.data.split(":", 2)
        lesson_id, index = int(lesson_text), int(index_text)
    except (ValueError, AttributeError):
        await callback.answer("❌ زر صفحة غير صالح.", show_alert=True)
        return
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await _show(callback, lesson, index, bot)
