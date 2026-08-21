import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    count_menu,
    difficulty_menu,
    group_quiz_menu,
    lesson_menu,
    lessons_list_menu,
    main_menu,
    result_menu,
    settings_menu,
)
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator
from app.services.file_extractor import clean_text

logger = logging.getLogger(__name__)
router = Router()


class QuizState(StatesGroup):
    active = State()


def register_user(db: Database, user_id: int, first_name: str = "") -> None:
    db.ensure_user(user_id, first_name)


def answer_matches(question: dict, answer: str) -> bool:
    expected = str(question.get("answer", "")).strip().lower()
    actual = answer.strip().lower()
    if question.get("type") == "short":
        return expected == actual or (expected and expected in actual)
    return actual == expected


def question_keyboard(options: list[str], index: int):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(option), callback_data=f"ans:{index}:{i}")]
            for i, option in enumerate(options)
        ]
    )


@router.message(CommandStart())
async def start(message: Message, db: Database) -> None:
    register_user(db, message.from_user.id, message.from_user.first_name or "")
    await message.answer(
        "🌟 أهلاً بك في TOFAN AI 2026!\n\n"
        "مساعدك التعليمي الذكي: أرسل PDF أو DOCX أو TXT وسأشرح الدرس وأجهز لك اختبارات فردية أو جماعية.\n\n"
        "📚 لكل درس ستجد: شرح الدرس، اختبار جديد، إعادة الاختبار، واختبار جماعي.\n\n"
        "اختر من القائمة أو استخدم /help.",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "📘 أوامر TOFAN AI 2026:\n"
        "/start — تشغيل البوت\n/help — المساعدة\n/lessons — مكتبة الدروس\n"
        "/quiz — اختبار آخر درس\n/summary — شرح آخر درس\n/profile — تقدم الطالب\n\n"
        "👥 يمكن تشغيل الاختبارات الجماعية داخل المجموعات والقنوات باستخدام الأزرار.\n"
        "📎 أرسل PDF أو DOCX أو TXT لمعالجة الدرس."
    )


async def show_lessons(message: Message, db: Database) -> None:
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("📚 افتح البوت في الخاص أولًا لعرض مكتبة دروسك.")
        return
    rows = db.get_lessons(user_id)
    if not rows:
        await message.answer("📚 لا توجد دروس بعد. أرسل أول ملف درس.")
        return
    await message.answer(
        "📚 **مكتبة دروسك**\n\nاختر درسًا للوصول إلى الشرح والاختبارات:",
        reply_markup=lessons_list_menu(rows),
    )


@router.message(Command("lessons"))
async def lessons(message: Message, db: Database) -> None:
    register_user(db, message.from_user.id, message.from_user.first_name or "")
    await show_lessons(message, db)


@router.message(Command("profile"))
async def profile(message: Message, db: Database) -> None:
    register_user(db, message.from_user.id, message.from_user.first_name or "")
    user = db.get_user(message.from_user.id)
    stats = db.get_stats(message.from_user.id)
    await message.answer(
        f"👤 ملفك في TOFAN AI 2026\n\n📚 الدروس: {stats['lessons']}\n"
        f"📝 الاختبارات المكتملة: {stats['quizzes']}\n📊 متوسط النتائج: {stats['average']}%\n"
        f"🎯 الإعدادات: {user['question_count']} أسئلة / {user['difficulty']}"
    )


@router.message(Command("summary"))
async def summary_command(message: Message, db: Database) -> None:
    rows = db.get_lessons(message.from_user.id, 1)
    if not rows:
        await message.answer("📖 لا يوجد درس بعد. أرسل درسًا أولًا.")
        return
    await send_lesson_explanation(message, rows[0])


@router.message(Command("quiz"))
async def quiz_command(message: Message, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    rows = db.get_lessons(message.from_user.id, 1)
    if not rows:
        await message.answer("📝 أرسل درسًا أولًا ثم اطلب الاختبار.")
        return
    await create_quiz_for_lesson(message, rows[0], state, db, quiz_generator, group_mode=False)


async def create_quiz_for_lesson(
    message: Message,
    lesson,
    state: FSMContext,
    db: Database,
    quiz_generator: QuizGenerator,
    group_mode: bool = False,
) -> None:
    user_id = message.from_user.id
    register_user(db, user_id, message.from_user.first_name or "")
    user = db.get_user(user_id)
    await message.answer("🧠 جاري إنشاء اختبار جديد من محتوى الدرس...")
    questions = await quiz_generator.create(
        lesson["extracted_text"], user["question_count"], user["difficulty"]
    )
    if group_mode:
        questions = [q for q in questions if q.get("type") != "short"]
        if not questions:
            await message.answer("⚠️ هذا الاختبار لم ينتج أسئلة مناسبة للأزرار الجماعية.")
            return
    quiz_id = db.create_quiz(lesson["id"], quiz_generator.serialize(questions))
    await state.set_state(QuizState.active)
    await state.update_data(
        quiz_id=quiz_id,
        lesson_id=lesson["id"],
        questions=questions,
        answers=[],
        group_mode=group_mode,
    )
    if group_mode:
        await message.answer(
            f"👥 **اختبار جماعي جديد**\n📖 الدرس: {lesson['file_name']}\n"
            f"📝 عدد الأسئلة: {len(questions)}\n\nاضغط انضم، ثم سيحصل كل طالب على محاولته الخاصة وتدخل النتائج في لوحة المتصدرين.",
            reply_markup=group_quiz_menu(quiz_id),
        )
        await state.clear()
        return
    await message.answer(f"🎯 تم إنشاء الاختبار #{quiz_id}. نبدأ الآن!")
    await send_question(message, state, quiz_id, questions, 0, [], db)


async def finish_quiz(
    message: Message,
    state: FSMContext,
    quiz_id: int,
    lesson_id: int,
    questions: list[dict],
    answers: list[str],
    db: Database,
    group_mode: bool = False,
) -> None:
    score = sum(answer_matches(q, a) for q, a in zip(questions, answers))
    total = len(questions)
    percentage = round(score / total * 100, 1) if total else 0
    db.save_result(
        message.from_user.id,
        quiz_id,
        score,
        total,
        percentage,
        json.dumps(answers, ensure_ascii=False),
    )
    lines = [
        "🏁 انتهى الاختبار!",
        "",
        f"✅ النتيجة: {score}/{total}",
        f"📊 النسبة: {percentage}%",
    ]
    if group_mode:
        lines += ["", "👥 نتيجتك أضيفت إلى لوحة المتصدرين."]
    else:
        lines += ["", "📋 مراجعة الأخطاء:"]
        for i, (question, answer) in enumerate(zip(questions, answers), 1):
            mark = "✅" if answer_matches(question, answer) else "❌"
            lines.append(f"{mark} {i}. إجابتك: {answer or 'بدون إجابة'}")
            if mark == "❌":
                lines.append(f"   الصحيحة: {question.get('answer', '')}")
                lines.append(f"   الشرح: {question.get('explanation', '')}")
    await message.answer(
        "\n".join(lines)[:3900],
        reply_markup=result_menu(lesson_id, group=group_mode),
    )
    await state.clear()


async def send_question(
    message: Message,
    state: FSMContext,
    quiz_id: int,
    questions: list[dict],
    index: int,
    answers: list[str],
    db: Database,
) -> None:
    data = await state.get_data()
    lesson_id = int(data.get("lesson_id", 0))
    group_mode = bool(data.get("group_mode", False))
    if index >= len(questions):
        await finish_quiz(message, state, quiz_id, lesson_id, questions, answers, db, group_mode)
        return
    q = questions[index]
    if group_mode and q.get("type") == "short":
        answers.append("")
        await state.update_data(answers=answers)
        await send_question(message, state, quiz_id, questions, index + 1, answers, db)
        return
    text = f"❓ السؤال {index + 1}/{len(questions)}\n\n{q.get('question', '')}"
    if q.get("type") == "short":
        await message.answer(text + "\n\n✍️ اكتب إجابتك وأرسلها.")
    else:
        await message.answer(text, reply_markup=question_keyboard(q.get("options") or [], index))


@router.callback_query(F.data.startswith("ans:"))
async def quiz_answer(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    if not quiz_id:
        await callback.answer("ابدأ الاختبار من زر الانضمام أولًا.", show_alert=True)
        return
    index, option_index = map(int, callback.data.split(":")[1:])
    if index != len(answers) or index >= len(questions):
        await callback.answer("هذا السؤال لم يعد نشطًا.")
        return
    options = questions[index].get("options", [])
    answer = str(options[option_index]) if option_index < len(options) else ""
    answers.append(answer)
    await state.update_data(answers=answers)
    await callback.answer("تم تسجيل إجابتك ✅")
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_question(callback.message, state, quiz_id, questions, index + 1, answers, db)


@router.message(QuizState.active, F.text)
async def short_answer(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id, questions, answers = data.get("quiz_id"), data.get("questions", []), data.get("answers", [])
    index = len(answers)
    if not quiz_id or index >= len(questions) or questions[index].get("type") != "short":
        await message.answer("استخدم زر الإجابة الظاهر للسؤال الحالي.")
        return
    answers.append(message.text.strip())
    await state.update_data(answers=answers)
    await send_question(message, state, quiz_id, questions, index + 1, answers, db)


@router.callback_query(F.data == "lessons")
async def lessons_button(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    await show_lessons(callback.message, db)


@router.callback_query(F.data.startswith("lesson:"))
async def lesson_button(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":")[1])
    lesson = db.get_lesson(lesson_id)
    await callback.answer()
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود.")
        return
    await callback.message.answer(
        f"📘 **{lesson['file_name']}**\n\nاختر ما تريد:",
        reply_markup=lesson_menu(lesson_id),
    )


@router.callback_query(F.data == "profile")
async def profile_button(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    await profile(callback.message, db)


@router.callback_query(F.data == "help")
async def help_button(callback: CallbackQuery) -> None:
    await callback.answer()
    await help_command(callback.message)


@router.callback_query(F.data == "home")
async def home_button(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("🌟 TOFAN AI 2026\nاختر خدمة:", reply_markup=main_menu())


@router.callback_query(F.data == "settings")
async def settings_button(callback: CallbackQuery, db: Database) -> None:
    register_user(db, callback.from_user.id, callback.from_user.first_name or "")
    user = db.get_user(callback.from_user.id)
    await callback.answer()
    await callback.message.edit_text(
        "⚙️ إعدادات الاختبارات",
        reply_markup=settings_menu(user["question_count"], user["difficulty"]),
    )


@router.callback_query(F.data == "set_count")
async def set_count(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("اختر عدد الأسئلة:", reply_markup=count_menu())


@router.callback_query(F.data.startswith("count:"))
async def set_count_value(callback: CallbackQuery, db: Database) -> None:
    count = int(callback.data.split(":")[1])
    user = db.get_user(callback.from_user.id)
    db.update_settings(callback.from_user.id, count, user["difficulty"])
    await callback.answer("تم حفظ عدد الأسئلة ✅")
    await settings_button(callback, db)


@router.callback_query(F.data == "set_difficulty")
async def set_difficulty(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("اختر مستوى الصعوبة:", reply_markup=difficulty_menu())


@router.callback_query(F.data.startswith("difficulty:"))
async def set_difficulty_value(callback: CallbackQuery, db: Database) -> None:
    difficulty = callback.data.split(":", 1)[1]
    user = db.get_user(callback.from_user.id)
    db.update_settings(callback.from_user.id, user["question_count"], difficulty)
    await callback.answer("تم حفظ مستوى الصعوبة ✅")
    await settings_button(callback, db)


async def send_lesson_explanation(message: Message, lesson) -> None:
    summary = lesson["summary"] or "لا يوجد شرح جاهز لهذا الدرس."
    concepts = []
    try:
        concepts = json.loads(lesson["concepts"] or "[]")
    except (TypeError, json.JSONDecodeError):
        pass
    if isinstance(concepts, list):
        concepts_text = "\n".join(f"• {c}" for c in concepts[:12])
    elif isinstance(concepts, dict):
        concepts_text = "\n".join(f"• {k}: {v}" for k, v in concepts.items())[:1500]
    else:
        concepts_text = str(concepts)
    text = f"📖 **شرح الدرس: {lesson['file_name']}**\n\n{summary}"
    if concepts_text:
        text += f"\n\n🧠 **أهم المفاهيم:**\n{concepts_text}"
    await message.answer(text[:3900], reply_markup=lesson_menu(lesson["id"]))


@router.callback_query(F.data.startswith("summary:"))
@router.callback_query(F.data.startswith("explain:"))
async def lesson_explanation_button(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":")[1])
    lesson = db.get_lesson(lesson_id)
    await callback.answer()
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود.")
        return
    await send_lesson_explanation(callback.message, lesson)


@router.callback_query(F.data.startswith("quiz:"))
async def lesson_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    await callback.answer()
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود.")
        return
    await create_quiz_for_lesson(callback.message, lesson, state, db, quiz_generator, group_mode=False)


@router.callback_query(F.data.startswith("repeat:"))
async def repeat_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    await callback.answer("🔁 يتم تجهيز اختبار جديد...")
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود.")
        return
    await create_quiz_for_lesson(callback.message, lesson, state, db, quiz_generator, group_mode=False)


@router.callback_query(F.data.startswith("groupquiz:"))
async def group_quiz(callback: CallbackQuery, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    await callback.answer()
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود.")
        return
    register_user(db, callback.from_user.id, callback.from_user.first_name or "")
    user = db.get_user(callback.from_user.id)
    await callback.message.answer("👥 جاري تجهيز اختبار جماعي من هذا الدرس...")
    questions = await quiz_generator.create(lesson["extracted_text"], user["question_count"], user["difficulty"])
    questions = [q for q in questions if q.get("type") != "short"]
    if not questions:
        await callback.message.answer("⚠️ لم يتم إنشاء أسئلة اختيارية مناسبة للاختبار الجماعي.")
        return
    quiz_id = db.create_quiz(lesson["id"], quiz_generator.serialize(questions))
    await callback.message.answer(
        f"👥 **اختبار جماعي**\n📖 {lesson['file_name']}\n📝 {len(questions)} سؤال\n\n"
        "كل طالب يضغط انضم ويجيب عن نفس الاختبار، والنتائج تظهر في لوحة المتصدرين.",
        reply_markup=group_quiz_menu(quiz_id),
    )


@router.callback_query(F.data.startswith("join:"))
async def join_group_quiz(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    quiz_id = int(callback.data.split(":")[1])
    quiz = db.get_quiz(quiz_id)
    if not quiz:
        await callback.answer("الاختبار غير موجود.", show_alert=True)
        return
    register_user(db, callback.from_user.id, callback.from_user.first_name or "")
    questions = json.loads(quiz["questions_json"])
    lesson = db.get_lesson(quiz["lesson_id"])
    await state.set_state(QuizState.active)
    await state.update_data(
        quiz_id=quiz_id,
        lesson_id=quiz["lesson_id"],
        questions=questions,
        answers=[],
        group_mode=True,
    )
    await callback.answer("🚀 انضممت للاختبار!")
    await callback.message.answer(
        f"🎯 {callback.from_user.first_name or 'الطالب'} بدأ محاولته.\n"
        f"📖 {lesson['file_name'] if lesson else 'الدرس'}\n\n"
        "أجب عن الأسئلة من الأزرار."
    )
    await send_question(callback.message, state, quiz_id, questions, 0, [], db)


@router.callback_query(F.data.startswith("leaderboard:"))
async def leaderboard(callback: CallbackQuery, db: Database) -> None:
    quiz_id = int(callback.data.split(":")[1])
    rows = db.get_quiz_leaderboard(quiz_id)
    await callback.answer()
    if not rows:
        await callback.message.answer("🏆 لا توجد نتائج حتى الآن. كن أول المشاركين!")
        return
    lines = ["🏆 **لوحة المتصدرين**", ""]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows, 1):
        medal = medals[i - 1] if i <= 3 else f"{i}."
        name = row["first_name"] or str(row["telegram_id"])
        lines.append(f"{medal} {name} — {row['score']}/{row['total']} ({row['percentage']}%)")
    await callback.message.answer("\n".join(lines))


async def process_document(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService, owner_id: int) -> None:
    document = message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in extractor.SUPPORTED:
        await message.answer("❌ الصيغة غير مدعومة. أرسل PDF أو DOCX أو TXT.")
        return
    if document.file_size and document.file_size > 20 * 1024 * 1024:
        await message.answer("❌ الملف أكبر من الحد المسموح (20 MB).")
        return
    safe_name = Path(document.file_name or "lesson").name
    path = Path("data/uploads") / f"{owner_id}_{message.message_id}_{safe_name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    await message.answer("📥 استلمت الملف. جاري استخراج النص وشرح الدرس...")
    try:
        await bot.download(document, destination=path)
        text = clean_text(extractor.extract(path))
        if len(text) < 20:
            raise ValueError("لم أستطع استخراج نص كافٍ من الملف.")
        register_user(db, owner_id, getattr(message.from_user, "first_name", "") or "")
        lesson_id = db.create_lesson(owner_id, safe_name, suffix[1:], str(path), text)
        analysis = await ai_service.analyze_lesson(text)
        summary = analysis.get("summary", "لم يتم إنشاء شرح.")
        concepts = json.dumps(analysis.get("concepts", []), ensure_ascii=False)
        db.update_lesson_analysis(lesson_id, summary, concepts)
        await message.answer(
            f"✅ تم حفظ الدرس #{lesson_id}: {safe_name}\n\n📖 **الشرح:**\n{summary[:2500]}",
            reply_markup=lesson_menu(lesson_id),
        )
    except Exception as exc:
        logger.exception("Document processing failed")
        await message.answer(f"⚠️ حدث خطأ أثناء معالجة الملف: {exc}")


@router.message(F.document)
async def document_handler(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    owner_id = message.from_user.id
    await process_document(message, db, bot, extractor, ai_service, owner_id)


@router.channel_post(F.document)
async def channel_document_handler(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    # Channel posts have no from_user. A synthetic owner keeps the lesson public/shared.
    owner_id = 0
    register_user(db, owner_id, message.chat.title or "Telegram Channel")
    await process_document(message, db, bot, extractor, ai_service, owner_id)
