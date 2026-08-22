import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers import QuizState, answer_matches, send_question
from app.bot.keyboards import (
    delete_lesson_confirm,
    lesson_menu,
    lessons_list_menu,
    main_menu,
)
from app.database import Database

logger = logging.getLogger(__name__)
router = Router(name="enhancements")


async def render_lessons(callback: CallbackQuery, db: Database) -> None:
    """Render the user's real lesson list in the current Telegram message."""
    user_id = callback.from_user.id
    rows = db.get_lessons(user_id)
    if rows:
        await callback.message.edit_text(
            "📚 **مكتبة دروسك**\n\nاختر درسًا للوصول إلى الشرح والاختبارات:",
            reply_markup=lessons_list_menu(rows),
        )
    else:
        await callback.message.edit_text(
            "📚 **مكتبة دروسك**\n\nلا توجد دروس بعد. أرسل أول ملف درس.",
            reply_markup=main_menu(),
        )


@router.callback_query(F.data == "lessons")
async def lessons_navigation(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    await render_lessons(callback, db)


@router.callback_query(F.data.startswith("lesson:"))
async def lesson_navigation(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text(
            "❌ الدرس غير موجود أو لا تملك صلاحية الوصول إليه.",
            reply_markup=main_menu(),
        )
        return
    await callback.message.edit_text(
        f"📘 **{lesson['file_name']}**\n\nاختر ما تريد:",
        reply_markup=lesson_menu(lesson_id),
    )


@router.callback_query(F.data == "help")
async def help_navigation(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "📘 **مساعدة TOFAN AI 2026**\n\n"
        "/start — تشغيل البوت\n"
        "/help — المساعدة\n"
        "/lessons — مكتبة الدروس\n"
        "/quiz — اختبار آخر درس\n"
        "/summary — شرح آخر درس\n"
        "/profile — تقدم الطالب\n\n"
        "📎 أرسل PDF أو DOCX أو TXT لمعالجة الدرس.\n"
        "🧠 شرح ذكي واختبار ذكي يستخدمان Gemini عند الطلب فقط.\n"
        "🇬🇧 المصطلحات الإنجليزية تظهر مع شرحها العربي.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "profile")
async def profile_navigation(callback: CallbackQuery, db: Database) -> None:
    user_id = callback.from_user.id
    db.ensure_user(user_id, callback.from_user.first_name or "")
    user = db.get_user(user_id)
    stats = db.get_stats(user_id)
    await callback.answer()
    await callback.message.edit_text(
        f"👤 **ملفك في TOFAN AI 2026**\n\n"
        f"📚 الدروس: {stats['lessons']}\n"
        f"📝 الاختبارات المكتملة: {stats['quizzes']}\n"
        f"📊 متوسط النتائج: {stats['average']}%\n"
        f"🎯 الإعدادات: {user['question_count']} أسئلة / {user['difficulty']}",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data.startswith("delete_lesson:"))
async def delete_lesson_request(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text(
            "❌ الدرس غير موجود أو لا تملك صلاحية حذفه.",
            reply_markup=main_menu(),
        )
        return
    await callback.message.edit_text(
        f"⚠️ **هل تريد حذف الدرس نهائيًا؟**\n\n"
        f"📘 {lesson['file_name']}\n\n"
        "سيتم حذف الدرس والاختبارات والنتائج المرتبطة به.",
        reply_markup=delete_lesson_confirm(lesson_id),
    )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def delete_lesson_confirmed(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    user_id = callback.from_user.id
    lesson = db.get_lesson(lesson_id, user_id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text(
            "❌ الدرس غير موجود.",
            reply_markup=main_menu(),
        )
        return

    file_path = Path(lesson["file_path"] or "")
    try:
        deleted = db.delete_lesson(lesson_id, user_id)
        if not deleted:
            raise RuntimeError("Lesson was not deleted")
        if file_path.exists():
            file_path.unlink()
    except Exception:
        logger.exception("Failed to delete lesson %s", lesson_id)
        await callback.message.edit_text(
            "⚠️ تعذر حذف الدرس. حاول مرة أخرى.",
            reply_markup=lesson_menu(lesson_id),
        )
        return

    rows = db.get_lessons(user_id)
    if rows:
        await callback.message.edit_text(
            "🗑️ **تم حذف الدرس بنجاح.**\n\n📚 اختر درسًا آخر:",
            reply_markup=lessons_list_menu(rows),
        )
    else:
        await callback.message.edit_text(
            "🗑️ **تم حذف الدرس بنجاح.**\n\n📚 لم تعد لديك دروس محفوظة.",
            reply_markup=main_menu(),
        )


@router.callback_query(F.data.startswith("explain:"))
@router.callback_query(F.data.startswith("summary:"))
async def explanation_navigation(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text("❌ الدرس غير موجود.", reply_markup=main_menu())
        return

    summary = lesson["summary"] or "لا يوجد شرح جاهز لهذا الدرس."
    try:
        concepts = json.loads(lesson["concepts"] or "[]")
    except (TypeError, json.JSONDecodeError):
        concepts = []

    if isinstance(concepts, list):
        concepts_text = "\n".join(f"• {item}" for item in concepts[:12])
    elif isinstance(concepts, dict):
        concepts_text = "\n".join(f"• {key}: {value}" for key, value in concepts.items())[:1500]
    else:
        concepts_text = str(concepts)

    text = f"📖 **شرح الدرس: {lesson['file_name']}**\n\n{summary}"
    if concepts_text:
        text += f"\n\n🧠 **أهم المفاهيم:**\n{concepts_text}"
    await callback.message.edit_text(text[:3900], reply_markup=lesson_menu(lesson_id))


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
            await callback.message.answer(
                f"❌ **تصحيح الخطأ**\n\n"
                f"إجابتك: {answer or 'بدون إجابة'}\n"
                f"✅ الإجابة الصحيحة: {question.get('answer', '')}\n"
                f"💡 الشرح: {question.get('explanation', '') or 'راجع شرح الدرس لفهم النقطة.'}"
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
