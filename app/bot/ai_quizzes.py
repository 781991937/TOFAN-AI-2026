import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.quiz_engine import QuizState, send_question
from app.bot.library import file_lessons, find_file, prepare_categories, sync_categories, token
from app.database import Database
from app.services import QuizGenerator

logger = logging.getLogger(__name__)
router = Router(name="ai_quizzes")


async def _start_quiz(callback, state, db, quiz_generator, lesson_id, questions, title, file_key=None, file_last=False):
    quiz_id = db.create_quiz(int(lesson_id), quiz_generator.serialize(questions), len(questions), "medium")
    await state.set_state(QuizState.active)
    await state.update_data(
        quiz_id=quiz_id,
        lesson_id=int(lesson_id),
        questions=questions,
        answers=[],
        group_mode=False,
        engine="ai",
        user_id=callback.from_user.id,
        file_key=file_key or "",
        file_last=bool(file_last),
    )
    await callback.message.edit_text(
        f"📝 <b>{html.escape(title)}</b>\n"
        f"🧠 <b>الأسئلة: الذكاء الاصطناعي</b>\n"
        f"🎯 <b>{len(questions)} سؤالًا</b>\n"
        "⏱️ <b>15 ثانية لكل سؤال</b>\n\n"
        "نبدأ الآن!"
    )
    await send_question(callback.message, state, quiz_id, questions, 0, [], db)


@router.callback_query(F.data.startswith("ai_filequiz:"))
async def file_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator):
    lessons = sync_categories(db, callback.from_user.id)
    key = find_file(lessons, callback.data.split(":", 1)[1])
    await callback.answer("🧠 جاري إعداد الاختبار الشامل…")
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود.")
        return

    selected = file_lessons(lessons, key)
    if not selected:
        await callback.message.edit_text("❌ لا توجد دروس داخل هذا الملف.")
        return

    combined_parts = []
    for number, lesson in enumerate(selected, 1):
        title = str(lesson["file_name"] or f"الدرس {number}")
        if " - " in title:
            title = title.split(" - ", 1)[1]
        combined_parts.append(f"===== الدرس {number}: {title} =====\n{str(lesson['extracted_text'] or '')}")
    combined = "\n\n".join(combined_parts).strip()
    if not combined:
        await callback.message.edit_text("⚠️ لا يوجد محتوى كافٍ لإنشاء الاختبار الشامل.")
        return

    try:
        count = min(30, max(10, quiz_generator.smart_count(combined, 30)))
        questions = await quiz_generator.create_smart(combined, count, "medium")
        if not questions:
            raise RuntimeError("لم ينتج الذكاء الاصطناعي أسئلة")
        await _start_quiz(
            callback,
            state,
            db,
            quiz_generator,
            int(selected[0]["id"]),
            questions,
            f"الاختبار الشامل للملف — {len(selected)} دروس",
            file_key=key,
            file_last=False,
        )
    except Exception:
        logger.exception("AI comprehensive file quiz failed")
        await callback.message.edit_text("⚠️ تعذر إنشاء الاختبار الشامل للملف. لم أستخدم المحرك المحلي.")


@router.callback_query(F.data.startswith("ai_categoryquiz:"))
async def category_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator):
    categories = prepare_categories(db, callback.from_user.id)
    value = callback.data.split(":", 1)[1]
    category = next((str(r["category"]) for r in categories if token(str(r["category"])) == value), None)
    await callback.answer("🧠 جاري إنشاء اختبار القسم…")
    if not category:
        await callback.message.edit_text("❌ القسم غير موجود.")
        return
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    if not lessons:
        await callback.message.edit_text("❌ لا توجد دروس في هذا القسم.")
        return
    combined = "\n\n===== درس =====\n\n".join(str(x["extracted_text"] or "") for x in lessons)
    try:
        questions = (await quiz_generator.create_smart(combined, 30, "medium"))[:30]
        if not questions:
            raise RuntimeError("لم ينتج الذكاء الاصطناعي أسئلة")
        await _start_quiz(
            callback,
            state,
            db,
            quiz_generator,
            int(lessons[0]["id"]),
            questions,
            f"اختبار القسم كامل — {html.escape(category)}",
        )
    except Exception:
        logger.exception("AI category quiz failed")
        await callback.message.edit_text("⚠️ تعذر إنشاء اختبار القسم بالذكاء الاصطناعي. لم أستخدم المحرك المحلي.")


@router.callback_query(F.data.startswith("repeat_ai:"))
async def repeat_ai(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    await callback.answer("🧠 جاري إنشاء نموذج جديد…")
    if not lesson:
        await callback.message.edit_text("❌ الدرس غير موجود.")
        return
    try:
        count = quiz_generator.smart_count(str(lesson["extracted_text"] or ""), 20)
        questions = await quiz_generator.create_smart(str(lesson["extracted_text"] or ""), count, "medium")
        await _start_quiz(callback, state, db, quiz_generator, int(lesson["id"]), questions, "نموذج اختبار جديد")
    except Exception:
        logger.exception("AI repeat quiz failed")
        await callback.message.edit_text("⚠️ تعذر إنشاء نموذج جديد.")
