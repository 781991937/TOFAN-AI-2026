from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import Database
from app.services.file_extractor import page_parts
from app.bot.keyboards import page_keyboard
from app.bot.page_helpers import ai_page_text

router = Router(name="ai_pages")


def _lesson_pages(lesson) -> list[tuple[int, str]]:
    """AI page adapter: pages come from durable lesson text only."""
    return page_parts(str(lesson["extracted_text"] or ""))


@router.callback_query(F.data.startswith("ai_pages:"))
async def open_ai_pages(callback: CallbackQuery, db: Database):
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)

    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return

    pages = _lesson_pages(lesson)
    if not pages:
        await callback.answer("❌ لا توجد صفحات محفوظة لهذا الدرس.", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        ai_page_text(lesson, pages, 0),
        reply_markup=page_keyboard(lesson_id, pages, 0),
    )
