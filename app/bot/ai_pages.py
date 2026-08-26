import json

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import Database
from app.services.file_extractor import page_parts
from app.bot.sections import page_text, page_keyboard

router = Router(name="ai_pages")


def _lesson_pages(lesson) -> list[tuple[int, str]]:
    """Build lesson pages only from data already stored in the database.

    The pages view must never depend on the original PDF existing on the
    Render/container filesystem. Uploaded files are stored locally only while
    processing; the durable source for this screen is extracted_text and the
    cached page data in key_points.
    """
    # Prefer the cached page objects created when the lesson was saved.
    try:
        cached = json.loads(str(lesson["key_points"] or "[]"))
        if isinstance(cached, list) and cached and isinstance(cached[0], dict):
            pages = []
            for index, item in enumerate(cached, 1):
                if "page" not in item:
                    continue
                body = str(item.get("text") or "").strip()
                if body:
                    pages.append((int(item.get("page", index)), body))
            if pages:
                return pages
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    # Fallback for older lessons that do not have cached page objects.
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
        page_text(lesson, pages, 0),
        reply_markup=page_keyboard(int(lesson["id"]), pages, 0),
    )
