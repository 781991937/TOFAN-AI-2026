import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers import QuizState, send_question
from app.bot.keyboards import lesson_menu
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator
from app.services.file_extractor import clean_text
from app.services.local_engine import local_analysis

logger = logging.getLogger(__name__)
router = Router(name="local_first")


async def save_local_lesson(message: Message, db: Database, bot, extractor: FileExtractor, owner_id: int) -> None:
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
    await message.answer("📥 استلمت الملف. استخراج النص وتحليل محلي سريع ⚡ (بدون Gemini)...")
    try:
        await bot.download(document, destination=path)
        text = clean_text(extractor.extract(path))
        if len(text) < 20:
            raise ValueError("لم أستطع استخراج نص كافٍ من الملف.")
        if owner_id != 0:
            db.ensure_user(owner_id, getattr(message.from_user, "first_name", "") or "")
        lesson_id = db.create_lesson(owner_id, safe_name, suffix[1:], str(path), text)
        analysis = local_analysis(text)
        db.update_lesson_analysis(lesson_id, analysis["summary"], json.dumps(analysis["concepts"], ensure_ascii=False))
        terms = "، ".join(analysis["english_terms"][:12]) or "لا توجد مصطلحات واضحة"
        await message.answer(
            f"✅ تم حفظ الدرس #{lesson_id}: {safe_name}\n\n"
            f"📖 **شرح سريع:**\n{analysis['summary'][:2200]}\n\n"
            f"🇬🇧 **مصطلحات إنجليزية:** {terms}\n\n"
            "⚡ لم يتم استخدام Gemini. استخدم 🧠 شرح ذكي أو 🧠 اختبار ذكي فقط عند الحاجة.",
            reply_markup=lesson_menu(lesson_id),
        )
    except Exception as exc:
        logger.exception("Local lesson processing failed")
        await message.answer(f"⚠️ حدث خطأ أثناء معالجة الملف: {exc}")


@router.message(F.document)
async def document_local_first(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    await save_local_lesson(message, db, bot, extractor, message.from_user.id)


@router.channel_post(F.document)
async def channel_document_local_first(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    await save_local_lesson(message, db, bot, extractor, 0)


@router.callback_query(F.data.startswith("smart_explain:"))
async def smart_explain(callback: CallbackQuery, db: Database, ai_service: AIService) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    await callback.answer("🧠 جاري استخدام Gemini...")
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود.")
        return
    try:
        analysis = await ai_service.analyze_lesson(lesson["extracted_text"])
        summary = analysis.get("summary", "لم يتم إنشاء شرح.")
        db.update_lesson_analysis(lesson["id"], summary, json.dumps(analysis.get("concepts", []), ensure_ascii=False))
        await callback.message.answer(f"🧠 **شرح ذكي: {lesson['file_name']}**\n\n{summary[:3000]}", reply_markup=lesson_menu(lesson["id"]))
    except Exception:
        logger.exception("Smart explanation failed")
        await callback.message.answer("⚠️ تعذر استخدام Gemini الآن. الشرح المحلي ما زال متاحًا.")


@router.callback_query(F.data.startswith("smart_quiz:"))
async def smart_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    await callback.answer("🧠 جاري إنشاء اختبار ذكي...")
    if not lesson:
        await callback.message.answer("❌ الدرس غير موجود.")
        return
    user = db.get_user(callback.from_user.id)
    try:
        questions = await quiz_generator.create_smart(lesson["extracted_text"], user["question_count"], user["difficulty"])
        quiz_id = db.create_quiz(lesson["id"], quiz_generator.serialize(questions))
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=lesson["id"], questions=questions, answers=[], group_mode=False)
        await callback.message.answer(f"🧠 تم إنشاء الاختبار الذكي #{quiz_id}. نبدأ!")
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        logger.exception("Smart quiz failed")
        await callback.message.answer("⚠️ تعذر إنشاء الاختبار الذكي. جرّب الاختبار العادي؛ فهو يعمل بدون Gemini.")
