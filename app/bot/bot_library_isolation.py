from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.keyboards import bot_categories_menu, file_list_menu, bot_lesson_list, lesson_menu
from app.bot.library import files_in_category, find_file, file_lessons, token
from app.database import Database

router = Router(name="bot_library_isolation")


def _is_ai_category(category: str) -> bool:
    value = str(category or "").casefold()
    return "الذكاء الاصطناعي" in value or "artificial intelligence" in value or "intelligent agent" in value


def _bot_lessons(db: Database, user_id: int) -> list:
    return [lesson for lesson in db.get_lessons(user_id, 1000) if not _is_ai_category(str(lesson["category"] or ""))]


def _categories(lessons: list) -> list:
    seen = set()
    result = []
    for lesson in lessons:
        category = str(lesson["category"] or "📂 مواد أخرى")
        if category not in seen:
            seen.add(category)
            result.append({"category": category})
    return result


@router.callback_query(F.data == "bot_library")
async def bot_library(callback: CallbackQuery, db: Database):
    lessons = _bot_lessons(db, callback.from_user.id)
    categories = _categories(lessons)
    await callback.answer()
    if not categories:
        await callback.message.edit_text(
            "📚 <b>مكتبة البوت والأتمتة فارغة</b>\n\nأرسل ملفًا برمجيًا أو تعليميًا للأتمتة.\n\n🧠 مواد الذكاء الاصطناعي تظهر في مكتبة الذكاء الاصطناعي فقط."
        )
        return
    await callback.message.edit_text(
        "🤖 <b>مكتبة البوت والأتمتة</b>\n\nاختر القسم:\n\n🐍 هذا القسم مستقل عن الذكاء الاصطناعي.",
        reply_markup=bot_categories_menu([row["category"] for row in categories]),
    )


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
    await callback.message.edit_text(
        f"🤖 <b>{html.escape(category)}</b>\n\nاختر الملف:",
        reply_markup=file_list_menu(selected, category),
    )


@router.callback_query(F.data.startswith("bot_file:"))
async def bot_file(callback: CallbackQuery, db: Database):
    lessons = _bot_lessons(db, callback.from_user.id)
    key = find_file(lessons, callback.data.split(":", 1)[1])
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود في قسم البوت والأتمتة.")
        return
    selected = file_lessons(lessons, key)
    await callback.message.edit_text(
        f"🤖 <b>قسم البوت والأتمتة</b>\n📚 <b>{html.escape(str(selected[0]['category'] or '📂 مواد أخرى'))}</b>\n📘 <b>{html.escape(str(selected[0]['file_name']))}</b>\n\nاختر الدرس:",
        reply_markup=bot_lesson_list(selected, key),
    )


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
    await callback.message.edit_text(
        f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:",
        reply_markup=file_list_menu(category_lessons, category),
    )


@router.callback_query(F.data.startswith("bot_lesson:"))
async def bot_lesson(callback: CallbackQuery, db: Database):
    _, lesson_id_text, file_token = callback.data.split(":", 2)
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
        f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n"
        f"🔢 <b>الدرس {number} من {len(selected)}</b>\n"
        "🤖 <b>قسم البوت والأتمتة — Python</b>\n\n"
        "🐍 الاستخراج والتنظيم والتنقل تعمل بمحرك Python.\n"
        "🧠 الشرح الذكي الخاص بالذكاء الاصطناعي موجود في قسمه المستقل.\n\n"
        "اختر الوظيفة:",
        reply_markup=lesson_menu(lesson_id),
    )
