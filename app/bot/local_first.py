import html
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


def _lesson_title(name: str) -> str:
    return html.escape(Path(name).stem.replace("_", " ").strip())


def _format_local_analysis(analysis: dict) -> str:
    summary = html.escape(analysis.get("summary") or "لا يوجد ملخص كافٍ.")
    terms = analysis.get("english_terms", [])[:12]
    term_text = "\n".join(f"• 🇬🇧 <b>{html.escape(str(term))}</b>" for term in terms) or "• لا توجد مصطلحات واضحة"
    return f"📖 <b>شرح سريع</b>\n\n{summary}\n\n🇬🇧 <b>المصطلحات المهمة</b>\n{term_text}"


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
    await message.answer("📥 استلمت الملف. استخراج النص وتنظيفه وتحليل محلي سريع ⚡ …")
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
        await message.answer(
            f"✅ <b>تم حفظ الدرس #{lesson_id}</b>\n📚 <b>{html.escape(safe_name)}</b>\n\n"
            f"{_format_local_analysis(analysis)}\n\n"
            "⚡ الشرح الأساسي يعمل محليًا بدون Gemini. استخدم 🧠 الشرح الذكي عند الحاجة فقط.",
            reply_markup=lesson_menu(lesson_id),
        )
    except Exception as exc:
        logger.exception("Local lesson processing failed")
        await message.answer(f"⚠️ حدث خطأ أثناء معالجة الملف: {html.escape(str(exc))}")


@router.message(F.document)
async def document_local_first(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    await save_local_lesson(message, db, bot, extractor, message.from_user.id)


@router.channel_post(F.document)
async def channel_document_local_first(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    await save_local_lesson(message, db, bot, extractor, 0)


@router.callback_query(F.data.startswith("smart_explain:"))
async def smart_explain(callback: CallbackQuery, db: Database, ai_service: AIService) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await callback.answer("🧠 جاري استخدام Gemini…")
    try:
        analysis = await ai_service.analyze_lesson(lesson["extracted_text"])
        summary = analysis.get("summary", "لم يتم إنشاء شرح.")
        db.update_lesson_analysis(lesson["id"], summary, json.dumps(analysis.get("concepts", []), ensure_ascii=False))
        concepts = analysis.get("concepts", [])[:12]
        concepts_text = "\n".join(f"• {html.escape(str(item))}" for item in concepts) or "• لا توجد مفاهيم إضافية."
        await callback.message.edit_text(
            f"🧠 <b>شرح الدرس: {_lesson_title(lesson['file_name'])}</b>\n\n"
            f"{html.escape(summary[:5000])}\n\n"
            f"📌 <b>أهم المفاهيم</b>\n{concepts_text}",
            reply_markup=lesson_menu(lesson["id"]),
        )
    except Exception:
        logger.exception("Smart explanation failed")
        await callback.message.edit_text(
            f"⚠️ <b>تعذر استخدام Gemini مؤقتًا.</b>\n\n"
            "لم يتعطل الدرس: استخدم الشرح المحلي أو حاول مرة أخرى لاحقًا.",
            reply_markup=lesson_menu(lesson["id"]),
        )


@router.callback_query(F.data.startswith("smart_quiz:"))
async def smart_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await callback.answer("🧠 جاري إنشاء اختبار ذكي…")
    user = db.get_user(callback.from_user.id)
    try:
        questions = await quiz_generator.create_smart(lesson["extracted_text"], user["question_count"], user["difficulty"])
        quiz_id = db.create_quiz(lesson["id"], quiz_generator.serialize(questions))
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=lesson["id"], questions=questions, answers=[], group_mode=False)
        await callback.message.edit_text(f"🧠 <b>تم إنشاء الاختبار الذكي #{quiz_id}</b>\n\nنبدأ الآن!", reply_markup=lesson_menu(lesson["id"]))
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        logger.exception("Smart quiz failed")
        await callback.message.edit_text(
            "⚠️ <b>تعذر إنشاء الاختبار الذكي الآن.</b>\n\n"
            "جرّب الاختبار العادي؛ فهو لا يحتاج Gemini.",
            reply_markup=lesson_menu(lesson["id"]),
        )
