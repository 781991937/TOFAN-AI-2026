import html
from aiogram import F, Router
from aiogram.types import CallbackQuery
from app.database import Database
from app.bot.sections import lesson_key, position, lesson_title
from app.bot.library import file_lessons
from app.bot.keyboards import ai_lesson_menu

router=Router(name="ai_navigation")

async def _move(callback: CallbackQuery, db: Database, lesson_id: int, direction: int):
    all_lessons=db.get_lessons(callback.from_user.id,1000); current=db.get_lesson(lesson_id,callback.from_user.id)
    if not current: await callback.answer("❌ الدرس غير موجود.",show_alert=True); return
    groups=[]; seen=set()
    for item in all_lessons:
        key=lesson_key(item)
        if key not in seen: seen.add(key); groups.append((key,item))
    keys=[x[0] for x in groups]; pos=keys.index(lesson_key(current))+direction
    if pos<0 or pos>=len(groups): await callback.answer("📚 لا يوجد ملف آخر في هذا الاتجاه.",show_alert=True); return
    target=groups[pos][1]; selected=file_lessons(all_lessons,lesson_key(target)); await callback.answer()
    await callback.message.edit_text(f"🧠 <b>قسم الذكاء الاصطناعي</b>\n📚 <b>{html.escape(str(target['category'] or '📂 مواد أخرى'))}</b>\n📘 <b>{html.escape(str(target['file_name']))}</b>\n\nاختر الدرس:",reply_markup=ai_lesson_menu(int(selected[0]['id']),lesson_key(target)))

@router.callback_query(F.data.startswith("ai_prevfile:"))
async def prevfile(callback: CallbackQuery,db:Database): await _move(callback,db,int(callback.data.split(":")[1]),-1)

@router.callback_query(F.data.startswith("ai_nextfile:"))
async def nextfile(callback: CallbackQuery,db:Database): await _move(callback,db,int(callback.data.split(":")[1]),1)
