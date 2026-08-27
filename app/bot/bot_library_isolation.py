from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.keyboards import bot_categories_menu, file_list_menu, bot_lesson_list, lesson_menu
from app.bot.library import find_file, file_lessons, token, sync_categories
from app.database import Database

router = Router(name="bot_library_isolation")


def _is_ai_category(category: str) -> bool:
    value = str(category or "").casefold()
    return "الذكاء الاصطناعي" in value or "artificial intelligence" in value or "intelligent agent" in value


def _bot_lessons(db: Database, user_id: int) -> list:
    lessons = sync_categories(db, user_id)
    return [lesson for lesson in lessons if not _is_ai_category(str(lesson["category"] or ""))]


def _categories(lessons: list) -> list[dict]:
    counts: dict[str, int] = {}
    for lesson in lessons:
        category = str(lesson["category"] or "📂 مواد أخرى")
        counts[category] = counts.get(category, 0) + 1
    return [{"category": category, "lesson_count": count} for category, count in counts.items()]


@router.callback_query(F.data == "bot_library")
async def bot_library(callback: CallbackQuery, db: Database):
    lessons = _bot_lessons(db, callback.from_user.id)
    categories = _categories(lessons)
    await callback.answer()
    if not categories:
        await callback.message.edit_text("📚 <b>مكتبة البوت والأتمتة فارغة</b>\n\nأرسل ملفًا للأتمتة.\n\n🧠 مواد الذكاء الاصطناعي تظهر في مكتبتها فقط.")
        return
    await callback.message.edit_text("🤖 <b>مكتبة البوت والأتمتة</b>\n\nاختر القسم:\n\n🐍 هذا القسم مستقل عن الذكاء الاصطناعي.", reply_markup=bot_categories_menu(categories))


@router.callback_query(F.data.startswith("bot_category:"))
async def bot_category(callback: CallbackQuery, db: Database):
    lessons = _bot_lessons(db, callback.from_user.id)
    value = callback.data.split(":", 1)[1]
    category = next((str(row["category"]) for row in _categories(lessons) if token(row["category"]) == value), None)
    await callback.answer()
    if not category:
        await callback.message.edit_text("❌ قسم البوت والأتمتة غير موجود.")
        return
    selected = [lesson for lesson in lessons if str(lesson["category"] or "") == category]
    await callback.message.edit_text(f"🤖 <b>{html.escape(category)}</b>\n\nاختر الملف:", reply_markup=file_list_menu(selected, category))


@router.callback_query(F.data.startswith("bot_file:"))
async def bot_file(callback: CallbackQuery, db: Database):
    lessons = _bot_lessons(db, callback.from_user.id)
    key = find_file(lessons, callback.data.split(":", 1)[1])
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود في قسم البوت والأتمتة.")
        return
    selected = file_lessons(lessons, key)
    await callback.message.edit_text(f"🤖 <b>قسم البوت والأتمتة</b>\n📚 <b>{html.escape(str(selected[0]['category'] or '📂 مواد أخرى'))}</b>\n📘 <b>{html.escape(str(selected[0]['file_name']))}</b>\n\nاختر الدرس:", reply_markup=bot_lesson_list(selected, key))


@router.callback_query(F.data.startswith("bot_fileback:"))
async def bot_fileback(callback: CallbackQuery, db: Database):
    lessons = _bot_lessons(db, callback.from_user.id)
    key = find_file(lessons, callback.data.split(":", 1)[1])
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود.")
        return
    selected = file_lessons(lessons, key)
    category = str(selected[0]["category"] or "📂 مواد أخرى")
    category_lessons = [x for x in lessons if str(x["category"] or "") == category]
    await callback.message.edit_text(f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:", reply_markup=file_list_menu(category_lessons, category))


@router.callback_query(F.data.startswith("bot_lesson:"))
async def bot_lesson(callback: CallbackQuery, db: Database):
    _, lesson_id_text, _file_token = callback.data.split(":", 2)
    lesson_id = int(lesson_id_text)
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer()
    if not lesson or _is_ai_category(str(lesson["category"] or "")):
        await callback.message.edit_text("❌ هذا الدرس تابع لقسم الذكاء الاصطناعي وليس قسم البوت والأتمتة.")
        return
    lessons = _bot_lessons(db, callback.from_user.id)
    selected = file_lessons(lessons, str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"]))
    number = next((i + 1 for i, row in enumerate(selected) if int(row["id"]) == lesson_id), 1)
    await callback.message.edit_text(
        f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n🔢 <b>الدرس {number} من {len(selected)}</b>\n"
        "🤖 <b>قسم البوت والأتمتة — Python</b>\n\n"
        "🐍 الاستخراج والتنظيم والتنقل تعمل بمحرك Python.\n"
        "🧠 الشرح الذكي والاختبارات الذكية موجودة في قسم الذكاء الاصطناعي.\n\nاختر الوظيفة:",
        reply_markup=lesson_menu(lesson_id),
    )
