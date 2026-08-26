from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import Database
from app.bot.sections import page_view, page_kb
from app.services.file_extractor import page_parts

router = Router(name="ai_pages")


def _lesson_pages(lesson) -> list[tuple[int, str]]:
    """Build pages from durable database text; never depend on the local upload path."""
    return page_parts(str(lesson["extracted_text"] or ""))


@router.callback_query(F.data.startswith("ai_pages:"))
async def open_ai_pages(callback: CallbackQuery, db: Database):
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
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
        reply_markup=page_kb(lesson_id, pages, 0),
    )
