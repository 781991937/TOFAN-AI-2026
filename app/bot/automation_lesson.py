"""Bot/Automation lesson controls.

These handlers are deliberately separate from AI navigation.
"""

import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from app.bot.bot_library_isolation import _bot_lessons
from app.bot.keyboards import delete_lesson_confirm, file_list_menu, lesson_menu
from app.bot.library import file_lessons
from app.database import Database

logger = logging.getLogger(__name__)
router = Router(name="automation_lesson")


def _is_ai(category: str) -> bool:
    value = str(category or "").casefold()
    return "الذكاء الاصطناعي" in value or "artificial intelligence" in value or "intelligent agent" in value


def _key(lesson) -> str:
    return str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])


@router.callback_query(F.data.startswith("lesson:"))
async def open_lesson(callback: CallbackQuery, db: Database):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    await callback.answer()
    if not lesson or _is_ai(str(lesson["category"] or "")):
        await callback.message.edit_text("❌ هذا الدرس تابع لقسم الذكاء الاصطناعي.")
        return
    selected = file_lessons(_bot_lessons(db, callback.from_user.id), _key(lesson))
    number = next((i + 1 for i, row in enumerate(selected) if int(row["id"]) == int(lesson["id"])), 1)
    await callback.message.edit_text(
        f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n"
        f"🔢 <b>الدرس {number} من {len(selected)}</b>\n"
        f"📚 <b>{html.escape(str(lesson['category'] or '📂 مواد أخرى'))}</b>\n\n"
        "🐍 <b>البوت والأتمتة — Python</b>\n\nاختر الوظيفة:",
        reply_markup=lesson_menu(int(lesson["id"])),
    )


async def _move(callback: CallbackQuery, db: Database, lesson_id: int, direction: int) -> None:
    lessons = _bot_lessons(db, callback.from_user.id)
    current = db.get_lesson(lesson_id, callback.from_user.id)
    if not current or _is_ai(str(current["category"] or "")):
        await callback.answer("❌ الدرس غير موجود في قسم البوت.", show_alert=True)
        return

    # Move between files, not between individual lessons.
    groups = []
    seen = set()
    for item in lessons:
        key = _key(item)
        if key not in seen:
            seen.add(key)
            groups.append((key, item))
    keys = [key for key, _ in groups]
    current_key = _key(current)
    if current_key not in keys:
        await callback.answer("❌ الملف غير موجود.", show_alert=True)
        return
    position = keys.index(current_key) + direction
    if position < 0 or position >= len(groups):
        await callback.answer("📚 لا يوجد ملف آخر في هذا الاتجاه.")
        return

    key, target = groups[position]
    selected = file_lessons(lessons, key)
    await callback.answer()
    await callback.message.edit_text(
        f"🤖 <b>قسم البوت والأتمتة — Python</b>\n"
        f"📘 <b>{html.escape(str(target['file_name']))}</b>\n\nاختر الدرس:",
        reply_markup=__import__("app.bot.keyboards", fromlist=["bot_lesson_list"]).bot_lesson_list(selected, key),
    )


@router.callback_query(F.data.startswith("prevfile:"))
async def previous_file(callback: CallbackQuery, db: Database):
    await _move(callback, db, int(callback.data.split(":", 1)[1]), -1)


@router.callback_query(F.data.startswith("nextfile:"))
async def next_file(callback: CallbackQuery, db: Database):
    await _move(callback, db, int(callback.data.split(":", 1)[1]), 1)


@router.callback_query(F.data.startswith("download:"))
async def download_file(callback: CallbackQuery, db: Database, bot):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    if not lesson or _is_ai(str(lesson["category"] or "")):
        await callback.answer("❌ الملف غير موجود.", show_alert=True)
        return
    file_id = str(lesson["file_id"] or "").strip()
    if not file_id:
        await callback.answer("⚠️ هذه نسخة قديمة بلا Telegram file_id. أعد رفع الملف مرة واحدة.", show_alert=True)
        return
    try:
        await callback.answer("📥 جاري إرسال الملف…")
        await bot.send_document(callback.from_user.id, file_id, caption=f"📘 {html.escape(str(lesson['file_name']))}")
    except Exception:
        logger.exception("Telegram file download failed")
        await callback.answer("❌ تعذر تنزيل الملف.", show_alert=True)


@router.callback_query(F.data.startswith("delete_lesson:"))
async def delete_prompt(callback: CallbackQuery, db: Database):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text("❌ الدرس غير موجود.")
        return
    await callback.message.edit_text(
        f"🗑️ <b>حذف الدرس</b>\n\nهل تريد حذف:\n📖 <b>{html.escape(str(lesson['file_name']))}</b>؟",
        reply_markup=delete_lesson_confirm(int(lesson["id"])),
    )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def confirm_delete(callback: CallbackQuery, db: Database):
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("الدرس محذوف بالفعل.")
        return
    deleted = db.delete_lesson(lesson_id, callback.from_user.id)
    await callback.answer("🗑️ تم حذف الدرس." if deleted else "❌ تعذر الحذف.")
    if not deleted:
        return
    remaining = _bot_lessons(db, callback.from_user.id)
    if not remaining:
        await callback.message.edit_text("📚 مكتبة البوت والأتمتة فارغة.")
        return
    category = str(lesson["category"] or "📂 مواد أخرى")
    category_lessons = [x for x in remaining if str(x["category"] or "") == category]
    if not category_lessons:
        await callback.message.edit_text("✅ تم الحذف. ارجع إلى المكتبة لاختيار قسم آخر.", reply_markup=__import__("app.bot.keyboards", fromlist=["section_menu"]).section_menu("bot"))
        return
    await callback.message.edit_text(
        f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:",
        reply_markup=file_list_menu(category_lessons, category),
    )
