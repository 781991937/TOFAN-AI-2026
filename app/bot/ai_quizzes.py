import html
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from app.bot.quiz_engine import QuizState, send_question
from app.bot.library import prepare_categories, token
from app.database import Database
from app.services import QuizGenerator

logger=logging.getLogger(__name__)
router=Router(name="ai_quizzes")

@router.callback_query(F.data.startswith("ai_categoryquiz:"))
async def category_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator):
    categories=prepare_categories(db,callback.from_user.id); value=callback.data.split(":",1)[1]
    category=next((str(r["category"]) for r in categories if token(str(r["category"]))==value),None)
    await callback.answer("🧠 جاري إنشاء اختبار القسم…")
    if not category: await callback.message.edit_text("❌ القسم غير موجود."); return
    lessons=db.get_lessons_by_category(callback.from_user.id,category)
    combined="\n\n===== ملف =====\n\n".join(str(x["extracted_text"] or "") for x in lessons)
    try:
        questions=(await quiz_generator.create_smart(combined,50,"medium"))[:50]
        if len(questions)<50:
            await callback.message.edit_text(f"⚠️ محتوى القسم أنتج {len(questions)} سؤالًا مختلفًا فقط. لن أكرر الأسئلة للوصول إلى 50."); return
        quiz_id=db.create_quiz(int(lessons[0]["id"]),quiz_generator.serialize(questions),50,"medium")
        await state.set_state(QuizState.active); await state.update_data(quiz_id=quiz_id,lesson_id=int(lessons[0]["id"]),questions=questions,answers=[],group_mode=False)
        await callback.message.edit_text(f"🎓 <b>اختبار القسم كامل</b>\n📚 <b>{html.escape(category)}</b>\n\n🧠 <b>الأسئلة: الذكاء الاصطناعي</b>\n🔥 <b>50 سؤالًا متنوعًا</b>\n\nنبدأ الآن!")
        await send_question(callback.message,state,quiz_id,questions,0,[],db)
    except Exception:
        logger.exception("AI category quiz failed")
        await callback.message.edit_text("⚠️ تعذر إنشاء اختبار القسم بالذكاء الاصطناعي. لم أستخدم المحرك المحلي.")

@router.callback_query(F.data.startswith("repeat_ai:"))
async def repeat_ai(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator):
    lesson=db.get_lesson(int(callback.data.split(":",1)[1]),callback.from_user.id)
    await callback.answer("🧠 جاري إنشاء نموذج جديد…")
    if not lesson: await callback.message.edit_text("❌ الدرس غير موجود."); return
    try:
        count=quiz_generator.smart_count(str(lesson["extracted_text"] or ""),20)
        questions=await quiz_generator.create_smart(str(lesson["extracted_text"] or ""),count,"medium")
        quiz_id=db.create_quiz(int(lesson["id"]),quiz_generator.serialize(questions),len(questions),"medium")
        await state.set_state(QuizState.active); await state.update_data(quiz_id=quiz_id,lesson_id=int(lesson["id"]),questions=questions,answers=[],group_mode=False)
        await callback.message.edit_text(f"🔁 <b>نموذج اختبار جديد</b>\n🧠 <b>الذكاء الاصطناعي</b>\n🎯 {len(questions)} أسئلة مختلفة")
        await send_question(callback.message,state,quiz_id,questions,0,[],db)
    except Exception:
        await callback.message.edit_text("⚠️ تعذر إنشاء نموذج جديد.")
