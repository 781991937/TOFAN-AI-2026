import html
from aiogram import F, Router
from aiogram.types import CallbackQuery
from app.database import Database
from app.bot.keyboards import lesson_menu

router=Router(name="automation_lesson")

@router.callback_query(F.data.startswith("lesson:"))
async def open_lesson(callback: CallbackQuery, db: Database):
    lesson=db.get_lesson(int(callback.data.split(":",1)[1]),callback.from_user.id); await callback.answer()
    if not lesson: await callback.message.edit_text("❌ الدرس غير موجود."); return
    await callback.message.edit_text(f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n📚 <b>{html.escape(str(lesson['category'] or '📂 مواد أخرى'))}</b>\n\n⚙️ <b>طريقة العمل: البوت والأتمتة — Python</b>\n\nاختر الوظيفة:",reply_markup=lesson_menu(int(lesson["id"])))
