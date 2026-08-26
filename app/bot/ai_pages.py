import json

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import Database
from app.services.file_extractor import page_parts
from app.bot.sections import page_view, page_kb

router = Router(name="ai_pages")


def _lesson_pages(lesson) -> list[tuple[int, str]]:
    """Build lesson pages from durable database data, never from the local file path."""
    try:
        cached = json.loads(str(lesson["key_points"] or "[]"))
        if isinstance(cached, list) and cached and isinstance(cached[0], dict):
            pages = []
            for index, item in enumerate(cached, 1):
                body = str(item.get("text") or "").strip()
                if body:
                    pages.append((int(item.get("page", index)), body))
            if pages:
                return pages
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return page_parts(str(lesson["extracted_text"] or ""))


@router.callback_query(F.data.startswith("ai_pages:"))
async def open_ai_pages(callback: CallbackQuery, db: Database):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    await callback.answer()

    if not lesson:
        await callback.message.edit_text("❌ الدرس غير موجود.")
        return

    pages = _lesson_pages(lesson)
    if not pages:
        await callback.message.edit_text("❌ لا توجد صفحات محفوظة لهذا الدرس.")
        return

    await callback.message.edit_text(
        page_view(lesson, pages, 0),
        reply_markup=page_kb(int(lesson["id"]), pages, 0),
    )
