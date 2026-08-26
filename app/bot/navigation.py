import hashlib
import html

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.keyboards import lesson_list_menu, automation_lesson_menu
from app.database import Database

router = Router(name="navigation")


def _file_key(lesson) -> str:
    return str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])


def _token(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _file_lessons(all_lessons: list, key: str) -> list:
    return [lesson for lesson in all_lessons if _file_key(lesson) == key]


def _find_file(all_lessons: list, token: str):
    for lesson in all_lessons:
        key = _file_key(lesson)
        if _token(key) == token:
            return key
    return None


def _lesson_number(all_lessons: list, lesson) -> tuple[int, int]:
    same_file = _file_lessons(all_lessons, _file_key(lesson))
    ids = [int(x["id"]) for x in same_file]
    try:
        return ids.index(int(lesson["id"])) + 1, len(ids)
    except ValueError:
        return 1, max(1, len(same_file))


def _lesson_text(lesson, all_lessons: list) -> str:
    number, total = _lesson_number(all_lessons, lesson)
    title = str(lesson["file_name"] or "الدرس")
    if " - " in title:
        title = title.split(" - ", 1)[1]
    category = str(lesson["category"] or "📂 مواد أخرى")
    summary = str(lesson["summary"] or "لم يتم حفظ شرح محلي لهذا الدرس بعد.").strip()

    return (
        f"📖 <b>{html.escape(title)}</b>\n"
        f"🔢 <b>الدرس {number} من {total}</b>\n"
        f"📚 <b>القسم:</b> {html.escape(category)}\n\n"
        "⚙️ <b>طريقة العرض: نظام البوت</b>\n\n"
        "📘 <b>شرح مختصر لاستيعاب الدرس</b>\n"
        f"{html.escape(summary[:2800])}"
    )[:3900]


async def _show_file_lessons(callback: CallbackQuery, db: Database, key: str) -> None:
    lessons = db.get_lessons(callback.from_user.id, 1000)
    selected = _file_lessons(lessons, key)
    if not selected:
        await callback.answer("❌ الملف غير موجود.", show_alert=True)
        return
    name = str(selected[0]["file_name"] or "الملف")
    if " - " in name:
        name = name.split(" - ", 1)[0]
    await callback.message.edit_text(
        f"📘 <b>{html.escape(name)}</b>\n\n"
        f"📚 <b>{len(selected)} درس</b>\nاختر الدرس الذي تريد دراسته:",
        reply_markup=lesson_list_menu(selected, key),
    )


@router.callback_query(F.data.startswith("file:"))
async def open_file(callback: CallbackQuery, db: Database) -> None:
    token = callback.data.split(":", 1)[1]
    lessons = db.get_lessons(callback.from_user.id, 1000)
    key = _find_file(lessons, token)
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود أو تم حذفه.")
        return
    await _show_file_lessons(callback, db, key)


@router.callback_query(F.data.startswith("fileback:"))
async def file_back(callback: CallbackQuery, db: Database) -> None:
    value = callback.data.split(":", 1)[1]
    lessons = db.get_lessons(callback.from_user.id, 1000)
    if value.isdigit():
        lesson = db.get_lesson(int(value), callback.from_user.id)
        key = _file_key(lesson) if lesson else None
    else:
        key = _find_file(lessons, value)
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ لم أجد الملف.")
        return
    await _show_file_lessons(callback, db, key)


@router.callback_query(F.data.startswith("lesson:"))
async def open_lesson(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text("❌ الدرس غير موجود.")
        return
    lessons = db.get_lessons(callback.from_user.id, 1000)
    await callback.message.edit_text(
        _lesson_text(lesson, lessons),
        reply_markup=automation_lesson_menu(lesson_id),
    )
