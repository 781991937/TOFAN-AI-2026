from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database import Database
from app.services.file_extractor import page_parts
from app.bot import sections as sections_module
from app.bot import automation as automation_module
from app.bot.keyboards import page_keyboard
from app.bot.page_helpers import ai_page_text, bot_page_text

router = Router(name="ai_pages")

# The legacy sections/automation modules are already imported by main.py before
# this router. Normalize their page helpers here so every page callback uses one
# stable implementation.
sections_module.page_keyboard = page_keyboard
sections_module.page_kb = page_keyboard
sections_module.page_view = ai_page_text


def _patched_bot_page_text(lesson, index: int) -> str:
    pages = automation_module._load_pages(lesson)
    if not pages:
        return "❌ لا توجد صفحات محفوظة لهذا الملف."
    index = max(0, min(index, len(pages) - 1))
    return bot_page_text(lesson, pages, index)


automation_module._page_text = _patched_bot_page_text


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
        ai_page_text(lesson, pages, 0),
        reply_markup=page_keyboard(lesson_id, pages, 0),
    )
