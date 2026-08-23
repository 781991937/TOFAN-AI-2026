import html
import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.handlers import QuizState, send_question
from app.bot.keyboards import lesson_menu
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator
from app.services.file_extractor import clean_text, page_parts, split_lessons
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


def _page_cache(lesson_text: str) -> list[dict]:
    pages = page_parts(lesson_text)
    result = []
    for number, text in pages:
        analysis = local_analysis(text)
        result.append({
            "page": number,
            "summary": analysis.get("summary", "")[:2600],
            "key_points": analysis.get("key_points", [])[:6],
            "terms": analysis.get("english_terms", [])[:10],
        })
    return result


def _page_keyboard(lesson_id: int, pages: list[dict], current: int) -> InlineKeyboardMarkup:
    rows = []
    numbers = [int(item.get("page", i + 1)) for i, item in enumerate(pages)]
    row = []
    for index, number in enumerate(numbers):
        label = f"📄 {number}" if number != current else f"🔵 {number}"
        row.append(InlineKeyboardButton(text=label, callback_data=f"page:{lesson_id}:{index}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    current_index = next((i for i, n in enumerate(numbers) if n == current), 0)
    nav = []
    if current_index > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابقة", callback_data=f"page:{lesson_id}:{current_index - 1}"))
    if current_index < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="➡️ التالية", callback_data=f"page:{lesson_id}:{current_index + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ قائمة الدرس", callback_data=f"lesson:{lesson_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _page_message(lesson, pages: list[dict], index: int) -> str:
    item = pages[index]
    page_number = item.get("page", index + 1)
    summary = html.escape(item.get("summary") or "لم أجد شرحًا كافيًا لهذه الصفحة.")
    points = item.get("key_points") or []
    points_text = "\n".join(f"• {html.escape(str(point))}" for point in points[:6]) or "• لا توجد نقاط إضافية واضحة."
    terms = item.get("terms") or []
    terms_text = "، ".join(html.escape(str(term)) for term in terms[:10]) or "لا توجد مصطلحات واضحة"
    return (
        f"📖 <b>شرح الدرس — صفحة {page_number}</b>\n"
        f"📄 <b>صفحة {index + 1} من {len(pages)}</b>\n\n"
        f"🧠 <b>افهم الصفحة ببساطة</b>\n{summary}\n\n"
        f"📌 <b>أهم النقاط</b>\n{points_text}\n\n"
        f"💡 <b>مصطلحات مهمة:</b> {terms_text}"
    )[:3900]


async def _show_page(callback: CallbackQuery, lesson, index: int) -> None:
    try:
        pages = json.loads(lesson["key_points"] or "[]")
    except (TypeError, json.JSONDecodeError):
        pages = []
    if not isinstance(pages, list) or not pages:
        pages = _page_cache(lesson["extracted_text"])
    if not pages:
        await callback.answer("❌ لا توجد صفحات محفوظة لهذا الدرس.", show_alert=True)
        return
    index = max(0, min(index, len(pages) - 1))
    await callback.message.edit_text(
        _page_message(lesson, pages, index),
        reply_markup=_page_keyboard(int(lesson["id"]), pages, index),
    )


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
    await message.answer("📥 استلمت الملف. استخراج النص وتقسيمه إلى دروس مستقلة وصفحات ذكية ⚡ …")

    try:
        await bot.download(document, destination=path)
        text = clean_text(extractor.extract(path))
        if len(text) < 20:
            raise ValueError("لم أستطع استخراج نص كافٍ من الملف.")

        lessons = split_lessons(text)
        if not lessons:
            raise ValueError("لم أجد محتوى صالحًا لإنشاء الدروس.")

        if owner_id != 0:
            db.ensure_user(owner_id, getattr(message.from_user, "first_name", "") or "")

        saved = []
        for number, (lesson_title, lesson_text) in enumerate(lessons, start=1):
            lesson_text = clean_text(lesson_text)
            if len(lesson_text) < 20:
                continue
            if len(lessons) == 1:
                lesson_name = safe_name
            else:
                clean_title = lesson_title.replace("/", "-").replace("\\", "-").strip()
                lesson_name = f"{Path(safe_name).stem} - {clean_title or f'الدرس {number}'}{suffix}"

            pages = _page_cache(lesson_text)
            page_text = "\n".join(text for _, text in page_parts(lesson_text))
            analysis = local_analysis(page_text)
            cache = json.dumps(pages, ensure_ascii=False)
            lesson_id = db.create_lesson(owner_id, lesson_name, suffix[1:], str(path), lesson_text)
            db.update_lesson_analysis(
                lesson_id,
                analysis["summary"],
                json.dumps(analysis["concepts"], ensure_ascii=False),
                cache,
            )
            saved.append((lesson_id, lesson_name, analysis, len(pages)))

        if not saved:
            raise ValueError("لم أجد دروسًا تحتوي على نص كافٍ.")

        if len(saved) == 1:
            lesson_id, lesson_name, analysis, page_count = saved[0]
            await message.answer(
                f"✅ <b>تم حفظ الدرس #{lesson_id}</b>\n📚 <b>{html.escape(lesson_name)}</b>\n"
                f"📄 <b>{page_count} صفحة</b> محفوظة للشرح صفحة بصفحة\n\n"
                f"{_format_local_analysis(analysis)}\n\n"
                "⚡ الشرح الأساسي يعمل محليًا بدون Gemini.",
                reply_markup=lesson_menu(lesson_id),
            )
            return

        lines = [
            f"✅ <b>تم تقسيم الملف إلى {len(saved)} دروس مستقلة</b>",
            f"📚 <b>الملف:</b> {html.escape(safe_name)}",
            "",
        ]
        for number, (lesson_id, lesson_name, analysis, page_count) in enumerate(saved, start=1):
            summary = html.escape((analysis.get("summary") or "").replace("\n", " ")[:180])
            lines.append(f"{number}. 📖 <b>الدرس #{lesson_id}</b> — {html.escape(lesson_name)}")
            lines.append(f"   ↳ 📄 {page_count} صفحة")
            if summary:
                lines.append(f"   ↳ {summary}")
        lines.append("\n💡 كل درس محفوظ مستقلًا، والشرح الآن صفحة بصفحة مع أزرار انتقال مباشرة.")
        await message.answer("\n".join(lines))

    except Exception as exc:
        logger.exception("Local lesson processing failed")
        await message.answer(f"⚠️ حدث خطأ أثناء معالجة الملف: {html.escape(str(exc))}")


@router.message(F.document)
async def document_local_first(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    await save_local_lesson(message, db, bot, extractor, message.from_user.id)


@router.channel_post(F.document)
async def channel_document_local_first(message: Message, db: Database, bot, extractor: FileExtractor, ai_service: AIService) -> None:
    await save_local_lesson(message, db, bot, extractor, 0)


@router.callback_query(F.data.startswith("pages:"))
async def pages_button(callback: CallbackQuery, db: Database) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await callback.answer()
    await _show_page(callback, lesson, 0)


@router.callback_query(F.data.startswith("page:"))
async def page_button(callback: CallbackQuery, db: Database) -> None:
    _, lesson_id, index = callback.data.split(":")
    lesson = db.get_lesson(int(lesson_id))
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await callback.answer()
    await _show_page(callback, lesson, int(index))


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
        try:
            cached_pages = json.loads(lesson["key_points"] or "[]")
        except (TypeError, json.JSONDecodeError):
            cached_pages = _page_cache(lesson["extracted_text"])
        db.update_lesson_analysis(
            lesson["id"],
            summary,
            json.dumps(analysis.get("concepts", []), ensure_ascii=False),
            json.dumps(cached_pages, ensure_ascii=False),
        )
        concepts = analysis.get("concepts", [])[:12]
        concepts_text = "\n".join(f"• {html.escape(str(item))}" for item in concepts) or "• لا توجد مفاهيم إضافية."
        await callback.message.edit_text(
            f"🧠 <b>شرح الدرس: {_lesson_title(lesson['file_name'])}</b>\n\n"
            f"{html.escape(summary[:5000])}\n\n"
            f"📌 <b>أهم المفاهيم</b>\n{concepts_text}\n\n"
            "📄 ولشرح الدرس صفحة بصفحة اضغط زر «شرح صفحة بصفحة».",
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
