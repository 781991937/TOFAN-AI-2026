from aiogram import F, Router
from aiogram.types import CallbackQuery
from app.database import Database
from app.services.file_extractor import page_parts
from app.bot.sections import page_text, page_keyboard

router = Router(name="ai_pages")

@router.callback_query(F.data.startswith("ai_pages:"))
async def open_ai_pages(callback: CallbackQuery, db: Database):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text("❌ الدرس غير موجود."); return
    pages = page_parts(str(lesson["extracted_text"] or ""))
    if not pages:
        await callback.message.edit_text("❌ لا توجد صفحات محفوظة لهذا الدرس."); return
    await callback.message.edit_text(page_text(lesson, pages, 0), reply_markup=page_keyboard(int(lesson["id"]), pages, 0))
