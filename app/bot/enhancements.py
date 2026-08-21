import json
import logging
import sqlite3
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers import QuizState, answer_matches, send_question
from app.bot.keyboards import delete_lesson_confirm, lesson_menu, lessons_list_menu
from app.database import Database

logger = logging.getLogger(__name__)
router = Router(name="enhancements")


@router.callback_query(F.data.startswith("delete_lesson:"))
async def delete_lesson_request(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":")[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود أو لا تملك صلاحية حذفه.")
        return
    await callback.message.edit_text(
        f"⚠️ هل تريد حذف الدرس نهائيًا؟\n\n📘 {lesson['file_name']}\n\nسيتم حذف الدرس والاختبارات والنتائج المرتبطة به.",
        reply_markup=delete_lesson_confirm(lesson_id),
    )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def delete_lesson_confirmed(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    lesson = db.get_lesson(lesson_id, user_id)
    await callback.answer()
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود.")
        return

    file_path = Path(lesson["file_path"] or "")
    try:
        with sqlite3.connect(db.path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM lessons WHERE id=? AND telegram_id=?", (lesson_id, user_id))
        if file_path.exists():
            file_path.unlink()
    except Exception:
        logger.exception("Failed to delete lesson %s", lesson_id)
        await callback.message.answer("⚠️ تعذر حذف الدرس. حاول مرة أخرى.")
        return

    rows = db.get_lessons(user_id)
    if rows:
        await callback.message.edit_text("🗑️ تم حذف الدرس بنجاح.\n\n📚 اختر درسًا آخر:", reply_markup=lessons_list_menu(rows))
    else:
        await callback.message.edit_text("🗑️ تم حذف الدرس بنجاح.\n\n📚 لم تعد لديك دروس محفوظة.")


@router.callback_query(F.data.startswith("ans:"))
async def corrected_quiz_answer(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    if not quiz_id:
        await callback.answer("ابدأ الاختبار أولًا.", show_alert=True)
        return

    try:
        index, option_index = map(int, callback.data.split(":")[1:])
    except (ValueError, AttributeError):
        await callback.answer("إجابة غير صالحة.")
        return
    if index != len(answers) or index >= len(questions):
        await callback.answer("هذا السؤال لم يعد نشطًا.")
        return

    question = questions[index]
    options = question.get("options", [])
    answer = str(options[option_index]) if option_index < len(options) else ""
    correct = answer_matches(question, answer)
    answers.append(answer)
    await state.update_data(answers=answers)
    await callback.answer("✅ صحيحة" if correct else "❌ خطأ")

    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        if correct:
            await callback.message.answer("✅ **إجابة صحيحة!** أحسنت 👏")
        else:
            correct_answer = question.get("answer", "")
            explanation = question.get("explanation", "")
            await callback.message.answer(
                f"❌ **تصحيح الخطأ**\n\n"
                f"إجابتك: {answer or 'بدون إجابة'}\n"
                f"✅ الإجابة الصحيحة: {correct_answer}\n"
                f"💡 الشرح: {explanation or 'راجع شرح الدرس لفهم النقطة.'}"
            )
        await send_question(callback.message, state, quiz_id, questions, index + 1, answers, db)


@router.message(QuizState.active, F.text)
async def corrected_short_answer(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    index = len(answers)
    if not quiz_id or index >= len(questions) or questions[index].get("type") != "short":
        return

    answer = message.text.strip()
    question = questions[index]
    correct = answer_matches(question, answer)
    answers.append(answer)
    await state.update_data(answers=answers)
    if correct:
        await message.answer("✅ **إجابة صحيحة!** أحسنت 👏")
    else:
        await message.answer(
            f"❌ **تصحيح الخطأ**\n\n"
            f"إجابتك: {answer or 'بدون إجابة'}\n"
            f"✅ الإجابة الصحيحة: {question.get('answer', '')}\n"
            f"💡 الشرح: {question.get('explanation', '') or 'راجع شرح الدرس.'}"
        )
    await send_question(message, state, quiz_id, questions, index + 1, answers, db)
