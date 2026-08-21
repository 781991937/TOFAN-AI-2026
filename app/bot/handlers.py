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
from app.services.file_extractor import chunk_text, clean_text

logger = logging.getLogger(__name__)
router = Router()


class QuizState(StatesGroup):
    active = State()


def register_user(db: Database, message: Message) -> None:
    user = message.from_user
    db.ensure_user(user.id, user.first_name or "")


def answer_matches(question: dict, answer: str) -> bool:
    expected = str(question.get("answer", "")).strip().lower()
    actual = answer.strip().lower()
    return actual == expected or (question.get("type") == "short" and expected in actual)


def question_keyboard(options: list[str], index: int):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=option, callback_data=f"ans:{index}:{i}") for i, option in enumerate(options)]
    ])


@router.message(CommandStart())
async def start(message: Message, db: Database) -> None:
    register_user(db, message)
    await message.answer(
        "🌟 أهلاً بك في TOFAN AI 2026!\n\n"
        "مساعدك التعليمي الذكي: أرسل ملف درس PDF أو DOCX أو TXT وسأستخرج محتواه وأحلله وأجهز لك اختبارًا تفاعليًا.\n\n"
        "اختر من القائمة أو استخدم /help.", reply_markup=main_menu()
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "📘 الأوامر المتاحة:\n"
        "/start — تشغيل البوت\n/help — المساعدة\n/lessons — دروسك\n/quiz — إنشاء اختبار من آخر درس\n"
        "/summary — ملخص آخر درس\n/profile — تقدمك وإحصاءاتك\n\n"
        "📎 أرسل PDF أو DOCX أو TXT مباشرةً لمعالجة الدرس."
    )


@router.message(Command("lessons"))
async def lessons(message: Message, db: Database) -> None:
    register_user(db, message)
    rows = db.get_lessons(message.from_user.id)
    if not rows:
        await message.answer("📚 لا توجد دروس بعد. أرسل أول ملف درس ليبدأ TOFAN AI العمل.")
        return
    text = "📚 دروسك السابقة:\n\n"
    for row in rows:
        text += f"• #{row['id']} — {row['file_name']}\n"
    await message.answer(text + "\nاستخدم /summary أو اختر درسًا من القائمة لاحقًا.")


@router.message(Command("profile"))
async def profile(message: Message, db: Database) -> None:
    register_user(db, message)
    user = db.get_user(message.from_user.id)
    stats = db.get_stats(message.from_user.id)
    await message.answer(
        f"👤 ملفك في TOFAN AI 2026\n\n"
        f"📚 الدروس: {stats['lessons']}\n"
        f"📝 الاختبارات المكتملة: {stats['quizzes']}\n"
        f"📊 متوسط النتائج: {stats['average']}%\n"
        f"🎯 إعداداتك: {user['question_count']} أسئلة / {user['difficulty']}"
    )


@router.message(Command("summary"))
async def summary_command(message: Message, db: Database) -> None:
    rows = db.get_lessons(message.from_user.id, 1)
    if not rows or not rows[0]["summary"]:
        await message.answer("📖 لا يوجد ملخص جاهز بعد. أرسل درسًا أولًا.")
        return
    await message.answer("📖 ملخص آخر درس:\n\n" + rows[0]["summary"][:3900])


@router.message(Command("quiz"))
async def quiz_command(message: Message, db: Database, quiz_generator: QuizGenerator) -> None:
    rows = db.get_lessons(message.from_user.id, 1)
    if not rows:
        await message.answer("📝 أرسل درسًا أولًا ثم اطلب الاختبار.")
        return
    await create_quiz_for_lesson(message, rows[0], db, quiz_generator)


async def create_quiz_for_lesson(message: Message, lesson, db: Database, quiz_generator: QuizGenerator) -> None:
    user = db.get_user(message.from_user.id)
    await message.answer("🧠 جاري إنشاء الاختبار من محتوى الدرس...")
    questions = await quiz_generator.create(lesson["extracted_text"], user["question_count"], user["difficulty"])
    quiz_id = db.create_quiz(lesson["id"], quiz_generator.serialize(questions))
    await message.answer(f"🎯 تم إنشاء الاختبار #{quiz_id}. نبدأ الآن!")
    await send_question(message, quiz_id, questions, 0, [], db)


async def send_question(message: Message, quiz_id: int, questions: list[dict], index: int, answers: list[str], db: Database) -> None:
    if index >= len(questions):
        score = sum(answer_matches(q, a) for q, a in zip(questions, answers))
        total = len(questions)
        percentage = round(score / total * 100, 1) if total else 0
        db.save_result(message.from_user.id, quiz_id, score, total, percentage, json.dumps(answers, ensure_ascii=False))
        await message.answer(f"🏁 انتهى الاختبار!\n\n✅ النتيجة: {score}/{total}\n📊 النسبة: {percentage}%")
        return
    q = questions[index]
    options = q.get("options") or []
    await message.answer(f"❓ السؤال {index + 1}/{len(questions)}\n\n{q.get('question', '')}", reply_markup=question_keyboard(options, index))


@router.callback_query(F.data.startswith("ans:"))
async def quiz_answer(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    index = int(callback.data.split(":")[1])
    option_index = int(callback.data.split(":")[2])
    if not quiz_id or index != len(answers) or index >= len(questions):
        await callback.answer("هذا السؤال لم يعد نشطًا.")
        return
    options = questions[index].get("options", [])
    answer = options[option_index] if option_index < len(options) else ""
    answers.append(answer)
    await state.update_data(answers=answers)
    await callback.answer("تم تسجيل إجابتك ✅")
    await callback.message.edit_reply_markup(reply_markup=None)
    await send_question(callback.message, quiz_id, questions, index + 1, answers, db)
    if index + 1 >= len(questions):
        await state.clear()


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
    lesson_id = int(callback.data.split(":")[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.answer("الدرس غير موجود.")
        return
    await callback.message.answer("📖 " + (lesson["summary"] or "لا يوجد ملخص.")[:3900])


@router.callback_query(F.data.startswith("quiz:"))
async def lesson_quiz(callback: CallbackQuery, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson_id = int(callback.data.split(":")[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.answer("الدرس غير موجود.")
        return
    await create_quiz_for_lesson(callback.message, lesson, db, quiz_generator)


@router.message(F.document)
async def document_handler(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    register_user(db, message)
    document = message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in extractor.SUPPORTED:
        await message.answer("❌ الصيغة غير مدعومة. أرسل PDF أو DOCX أو TXT.")
        return
    max_bytes = db.get_user(message.from_user.id)  # keeps user registered
    del max_bytes
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
        analysis = await ai_service.analyze_lesson(text[:30000])
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
