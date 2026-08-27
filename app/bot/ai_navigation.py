"""AI interface file navigation.

Navigation uses the same complete lesson library as Bot/Automation. This
module only controls the AI-side presentation and never filters by subject.
"""

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.keyboards import ai_lesson_menu
from app.bot.library import file_lessons, sync_categories
from app.database import Database

router = Router(name="ai_navigation")


def _key(lesson) -> str:
    return str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])


async def _move(callback: CallbackQuery, db: Database, lesson_id: int, direction: int):
    all_lessons = sync_categories(db, callback.from_user.id)
    current = db.get_lesson(lesson_id, callback.from_user.id)
    if not current:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
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
        f"📚 <b>{html.escape(str(target['category'] or '📂 مواد أخرى'))}</b>\n"
        f"📘 <b>{html.escape(str(target['file_name']))}</b>\n\n"
        "اختر الدرس:\n"
        "🧠 الشرح والاختبار هنا يعملان بمحرك الذكاء الاصطناعي.",
        reply_markup=ai_lesson_menu(int(selected[0]["id"]), key),
    )


@router.callback_query(F.data.startswith("ai_prevfile:"))
async def prevfile(callback: CallbackQuery, db: Database):
    await _move(callback, db, int(callback.data.split(":", 1)[1]), -1)


@router.callback_query(F.data.startswith("ai_nextfile:"))
async def nextfile(callback: CallbackQuery, db: Database):
    await _move(callback, db, int(callback.data.split(":", 1)[1]), 1)
