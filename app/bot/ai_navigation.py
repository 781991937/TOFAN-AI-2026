"""AI-only file navigation."""

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.keyboards import ai_lesson_menu
from app.bot.library import file_lessons
from app.database import Database

router = Router(name="ai_navigation")


def _is_ai(lesson) -> bool:
    value = str(lesson["category"] or "").casefold()
    return "الذكاء الاصطناعي" in value or "artificial intelligence" in value or "intelligent agent" in value


def _key(lesson) -> str:
    return str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])


async def _move(callback: CallbackQuery, db: Database, lesson_id: int, direction: int):
    all_lessons = [x for x in db.get_lessons(callback.from_user.id, 1000) if _is_ai(x)]
    current = db.get_lesson(lesson_id, callback.from_user.id)
    if not current or not _is_ai(current):
        await callback.answer("❌ الدرس غير موجود في قسم الذكاء الاصطناعي.", show_alert=True)
        return

    groups = []
    seen = set()
    for item in all_lessons:
        key = _key(item)
        if key not in seen:
            seen.add(key)
            groups.append((key, item))

    keys = [key for key, _ in groups]
    current_key = _key(current)
    if current_key not in keys:
        await callback.answer("❌ الملف غير موجود.", show_alert=True)
        return
    target_pos = keys.index(current_key) + direction
    if target_pos < 0 or target_pos >= len(groups):
        await callback.answer("📚 لا يوجد ملف آخر في هذا الاتجاه.")
        return

    key, target = groups[target_pos]
    selected = file_lessons(all_lessons, key)
    await callback.answer()
    await callback.message.edit_text(
        "🧠 <b>قسم الذكاء الاصطناعي</b>\n"
        f"📘 <b>{html.escape(str(target['file_name']))}</b>\n\nاختر الدرس:",
        reply_markup=ai_lesson_menu(int(selected[0]["id"]), key),
    )


@router.callback_query(F.data.startswith("ai_prevfile:"))
async def prevfile(callback: CallbackQuery, db: Database):
    await _move(callback, db, int(callback.data.split(":", 1)[1]), -1)


@router.callback_query(F.data.startswith("ai_nextfile:"))
async def nextfile(callback: CallbackQuery, db: Database):
    await _move(callback, db, int(callback.data.split(":", 1)[1]), 1)
