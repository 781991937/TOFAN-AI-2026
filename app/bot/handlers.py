import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import count_menu, difficulty_menu, lesson_menu, main_menu, settings_menu
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator
from app.services.file_extractor import clean_text

logger = logging.getLogger(__name__)
router = Router()


class QuizState(StatesGroup):
    active = State()


def register_user(db: Database, message: Message) -> None:
    db.ensure_user(message.from_user.id, message.from_user.first_name or "")


def answer_matches(question: dict, answer: str) -> bool:
    expected = str(question.get("answer", "")).strip().lower()
    actual = answer.strip().lower()
    if question.get("type") == "short":
        return expected == actual or (expected and expected in actual)
    return actual == expected


def question_keyboard(options: list[str], index: int):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for i, option in enumerate(options):
        rows.append([InlineKeyboardButton(text=str(option), callback_data=f"ans:{index}:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def start(message: Message, db: Database) -> None:
    register_user(db, message)
    await message.answer(
        "🌟 أهلاً بك في TOFAN AI 2026!\n\n"
        "مساعدك التعليمي الذكي: أرسل PDF أو DOCX أو TXT وسأستخرج النص وأحلله وأجهز لك اختبارًا تفاعليًا.\n\n"
        "اختر من القائمة أو استخدم /help.", reply_markup=main_menu()
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "📘 الأوامر المتاحة:\n"
        "/start — تشغيل البوت\n/help — المساعدة\n/lessons — دروسك\n/quiz — اختبار آخر درس\n"
        "/summary — ملخص آخر درس\n/profile — تقدمك وإحصاءاتك\n\n"
        "📎 أرسل PDF أو DOCX أو TXT مباشرةً لمعالجة الدرس."
    )


@router.message(Command("lessons"))
async def lessons(message: Message, db: Database) -> None:
    register_user(db, message)
    rows = db.get_lessons(message.from_user.id)
    if not rows:
        await message.answer("📚 لا توجد دروس بعد. أرسل أول ملف درس.")
        return
    lines = ["📚 دروسك السابقة:", ""]
    for row in rows:
        lines.append(f"• #{row['id']} — {row['file_name']}")
    await message.answer("\n".join(lines), reply_markup=main_menu())


@router.message(Command("profile"))
async def profile(message: Message, db: Database) -> None:
    register_user(db, message)
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
    if not rows or not rows[0]["summary"]:
        await message.answer("📖 لا يوجد ملخص جاهز بعد. أرسل درسًا أولًا.")
        return
    await message.answer("📖 ملخص آخر درس:\n\n" + rows[0]["summary"][:3900])


@router.message(Command("quiz"))
async def quiz_command(message: Message, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    rows = db.get_lessons(message.from_user.id, 1)
    if not rows:
        await message.answer("📝 أرسل درسًا أولًا ثم اطلب الاختبار.")
        return
    await create_quiz_for_lesson(message, rows[0], state, db, quiz_generator)


async def create_quiz_for_lesson(message: Message, lesson, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    user = db.get_user(message.from_user.id)
    await message.answer("🧠 جاري إنشاء الاختبار من محتوى الدرس...")
    questions = await quiz_generator.create(lesson["extracted_text"], user["question_count"], user["difficulty"])
    quiz_id = db.create_quiz(lesson["id"], quiz_generator.serialize(questions))
    await state.set_state(QuizState.active)
    await state.update_data(quiz_id=quiz_id, questions=questions, answers=[])
    await message.answer(f"🎯 تم إنشاء الاختبار #{quiz_id}. نبدأ الآن!")
    await send_question(message, state, quiz_id, questions, 0, [], db)


async def finish_quiz(message: Message, state: FSMContext, quiz_id: int, questions: list[dict], answers: list[str], db: Database) -> None:
    score = sum(answer_matches(q, a) for q, a in zip(questions, answers))
    total = len(questions)
    percentage = round(score / total * 100, 1) if total else 0
    db.save_result(message.from_user.id, quiz_id, score, total, percentage, json.dumps(answers, ensure_ascii=False))
    lines = [f"🏁 انتهى الاختبار!", "", f"✅ النتيجة: {score}/{total}", f"📊 النسبة: {percentage}%", "", "📋 المراجعة:"]
    for i, (question, answer) in enumerate(zip(questions, answers), 1):
        mark = "✅" if answer_matches(question, answer) else "❌"
        lines.append(f"{mark} {i}. إجابتك: {answer or 'بدون إجابة'}")
        if mark == "❌":
            lines.append(f"   الصحيحة: {question.get('answer', '')}")
            lines.append(f"   الشرح: {question.get('explanation', '')}")
    await message.answer("\n".join(lines)[:3900])
    await state.clear()


async def send_question(message: Message, state: FSMContext, quiz_id: int, questions: list[dict], index: int, answers: list[str], db: Database) -> None:
    if index >= len(questions):
        await finish_quiz(message, state, quiz_id, questions, answers, db)
        return
    q = questions[index]
    text = f"❓ السؤال {index + 1}/{len(questions)}\n\n{q.get('question', '')}"
    if q.get("type") == "short":
        await message.answer(text + "\n\n✍️ اكتب إجابتك وأرسلها.")
    else:
        await message.answer(text, reply_markup=question_keyboard(q.get("options") or [], index))


@router.callback_query(F.data.startswith("ans:"))
async def quiz_answer(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id, questions, answers = data.get("quiz_id"), data.get("questions", []), data.get("answers", [])
    index, option_index = map(int, callback.data.split(":")[1:])
    if not quiz_id or index != len(answers) or index >= len(questions):
        await callback.answer("هذا السؤال لم يعد نشطًا.")
        return
    options = questions[index].get("options", [])
    answer = str(options[option_index]) if option_index < len(options) else ""
    answers.append(answer)
    await state.update_data(answers=answers)
    await callback.answer("تم تسجيل إجابتك ✅")
    await callback.message.edit_reply_markup(reply_markup=None)
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
    await lessons(callback.message, db)


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
    user = db.get_user(callback.from_user.id)
    if not user:
        db.ensure_user(callback.from_user.id, callback.from_user.first_name or "")
        user = db.get_user(callback.from_user.id)
    await callback.answer()
    await callback.message.edit_text("⚙️ إعدادات الاختبارات", reply_markup=settings_menu(user["question_count"], user["difficulty"]))


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


@router.callback_query(F.data.startswith("summary:"))
async def lesson_summary(callback: CallbackQuery, db: Database) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]), callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.answer("الدرس غير موجود.")
        return
    await callback.message.answer("📖 " + (lesson["summary"] or "لا يوجد ملخص.")[:3900])


@router.callback_query(F.data.startswith("quiz:"))
async def lesson_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]), callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.answer("الدرس غير موجود.")
        return
    await create_quiz_for_lesson(callback.message, lesson, state, db, quiz_generator)


@router.message(F.document)
async def document_handler(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    register_user(db, message)
    document = message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in extractor.SUPPORTED:
        await message.answer("❌ الصيغة غير مدعومة. أرسل PDF أو DOCX أو TXT.")
        return
    if document.file_size and document.file_size > 20 * 1024 * 1024:
        await message.answer("❌ الملف أكبر من الحد المسموح (20 MB).")
        return
    safe_name = Path(document.file_name or "lesson").name
    path = Path("data/uploads") / f"{message.from_user.id}_{message.message_id}_{safe_name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    await message.answer("📥 استلمت الملف. جاري استخراج النص وتحليله...")
    try:
        await bot.download(document, destination=path)
        text = clean_text(extractor.extract(path))
        if len(text) < 20:
            raise ValueError("لم أستطع استخراج نص كافٍ من الملف.")
        lesson_id = db.create_lesson(message.from_user.id, safe_name, suffix[1:], str(path), text)
        analysis = await ai_service.analyze_lesson(text)
        summary = analysis.get("summary", "لم يتم إنشاء ملخص.")
        concepts = json.dumps(analysis.get("concepts", []), ensure_ascii=False)
        db.update_lesson_analysis(lesson_id, summary, concepts)
        await message.answer(
            f"✅ تم حفظ الدرس #{lesson_id}: {safe_name}\n\n📖 الملخص:\n{summary[:2500]}",
            reply_markup=lesson_menu(lesson_id),
        )
    except Exception as exc:
        logger.exception("Document processing failed")
        await message.answer(f"⚠️ حدث خطأ أثناء معالجة الملف: {exc}")
