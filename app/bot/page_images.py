import html
import io
import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.handlers import QuizState, send_question
from app.database import Database
from app.services.file_extractor import page_parts

logger = logging.getLogger(__name__)
router = Router(name="page_images")


def _pages(lesson) -> list[tuple[int, str]]:
    return page_parts(lesson["extracted_text"] or "")


def _keyboard(lesson_id: int, pages: list[tuple[int, str]], index: int) -> InlineKeyboardMarkup:
    rows = []
    for start in range(0, len(pages), 5):
        row = []
        for i in range(start, min(start + 5, len(pages))):
            number = pages[i][0]
            label = f"🔵 {number}" if i == index else f"📄 {number}"
            row.append(InlineKeyboardButton(text=label, callback_data=f"page:{lesson_id}:{i}"))
        rows.append(row)

    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابقة", callback_data=f"page:{lesson_id}:{index - 1}"))
    if index < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="➡️ التالية", callback_data=f"page:{lesson_id}:{index + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="📝 اختبار هذه الصفحة", callback_data=f"pagequiz:{lesson_id}:{index}")])
    rows.append([InlineKeyboardButton(text="⬅️ قائمة الدرس", callback_data=f"lesson:{lesson_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _caption(lesson, pages, index: int) -> str:
    number, text = pages[index]
    preview = " ".join(text.split())
    if len(preview) > 700:
        preview = preview[:697] + "..."
    return (
        f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n"
        f"📄 <b>صفحة {number} من {len(pages)}</b>\n\n"
        "🧠 <b>افهم الصفحة ببساطة</b>\n"
        f"{html.escape(preview or 'لا يوجد نص واضح في هذه الصفحة.')}\n\n"
        "💡 <i>الصورة المعروضة هي الصفحة الأصلية من ملف PDF، بدون إعادة تشكيل النص.</i>"
    )


def _render_pdf_page(path: Path, page_number: int) -> bytes:
    import fitz

    document = fitz.open(str(path))
    try:
        if page_number < 1 or page_number > len(document):
            raise ValueError(f"رقم الصفحة {page_number} غير موجود في الملف.")
        page = document.load_page(page_number - 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
        return pix.tobytes("jpeg", jpg_quality=88)
    finally:
        document.close()


async def _show_page(callback: CallbackQuery, lesson, index: int) -> None:
    pages = _pages(lesson)
    if not pages:
        await callback.answer("❌ لا توجد صفحات محفوظة لهذا الدرس.", show_alert=True)
        return
    index = max(0, min(index, len(pages) - 1))
    page_number = pages[index][0]
    path = Path(str(lesson["file_path"] or ""))

    if path.suffix.lower() != ".pdf":
        await callback.answer("هذا العرض بالصور متاح لملفات PDF.", show_alert=True)
        return
    if not path.exists():
        await callback.answer("⚠️ ملف PDF الأصلي غير موجود على الخادم.", show_alert=True)
        return

    try:
        image = _render_pdf_page(path, page_number)
        photo = BufferedInputFile(image, filename=f"lesson_{lesson['id']}_page_{page_number}.jpg")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=photo,
            caption=_caption(lesson, pages, index),
            reply_markup=_keyboard(int(lesson["id"]), pages, index),
        )
        await callback.answer()
    except Exception:
        logger.exception("PDF page rendering failed")
        await callback.answer("❌ تعذر تحويل الصفحة إلى صورة.", show_alert=True)


@router.callback_query(F.data.startswith("pages:"))
async def pages_button(callback: CallbackQuery, db: Database) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]))
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await _show_page(callback, lesson, 0)


@router.callback_query(F.data.startswith("page:"))
async def page_button(callback: CallbackQuery, db: Database) -> None:
    _, lesson_id, index = callback.data.split(":")
    lesson = db.get_lesson(int(lesson_id))
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await _show_page(callback, lesson, int(index))


@router.callback_query(F.data.startswith("pagequiz:"))
async def page_quiz_button(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator) -> None:
    _, lesson_id, index = callback.data.split(":")
    lesson = db.get_lesson(int(lesson_id))
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return

    pages = _pages(lesson)
    index = int(index)
    if index < 0 or index >= len(pages):
        await callback.answer("❌ الصفحة غير موجودة.", show_alert=True)
        return

    page_number, page_text = pages[index]
    user = db.get_user(callback.from_user.id)
    count = int(user["question_count"] if user else 5)
    difficulty = str(user["difficulty"] if user else "medium")
    count = max(3, min(count, 10))

    await callback.answer("🧠 جاري إعداد اختبار الصفحة…")
    try:
        questions = await quiz_generator.create_smart(page_text, count, difficulty)
        if not questions:
            raise ValueError("لم يتم إنشاء أسئلة من هذه الصفحة.")
        quiz_id = db.create_quiz(lesson["id"], quiz_generator.serialize(questions), len(questions), difficulty)
        await state.set_state(QuizState.active)
        await state.update_data(
            quiz_id=quiz_id,
            lesson_id=int(lesson["id"]),
            questions=questions,
            answers=[],
            group_mode=False,
            source_page=page_number,
        )
        await callback.message.edit_text(
            f"📝 <b>اختبار الصفحة {page_number}</b>\n\n"
            f"تم إنشاء {len(questions)} أسئلة من محتوى هذه الصفحة فقط.\n\n"
            "🎯 ابدأ الاختبار الآن!"
        )
        await send_question(callback.message, state)
    except Exception:
        logger.exception("Page quiz generation failed")
        await callback.message.answer("❌ تعذر إنشاء اختبار لهذه الصفحة حاليًا.")


@router.callback_query(F.data.startswith("smart_page_explain:"))
async def smart_page_explain(callback: CallbackQuery, db: Database, ai_service) -> None:
    _, lesson_id, index = callback.data.split(":")
    lesson = db.get_lesson(int(lesson_id))
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    pages = _pages(lesson)
    index = int(index)
    if index < 0 or index >= len(pages):
        await callback.answer("❌ الصفحة غير موجودة.", show_alert=True)
        return
    page_number, page_text = pages[index]
    await callback.answer("🧠 جاري فهم الصفحة…")
    try:
        analysis = await ai_service.analyze_lesson(page_text)
        summary = html.escape(str(analysis.get("summary") or "لا يوجد شرح كافٍ."))
        concepts = analysis.get("concepts") or []
        concepts_text = "\n".join(f"• {html.escape(str(x))}" for x in concepts[:8]) or "• لا توجد نقاط إضافية."
        await callback.message.answer(
            f"🧠 <b>شرح ذكي — صفحة {page_number}</b>\n\n{summary}\n\n"
            f"📌 <b>أهم النقاط</b>\n{concepts_text}"
        )
    except Exception:
        logger.exception("Smart page explanation failed")
        await callback.answer("❌ تعذر إنشاء الشرح الذكي لهذه الصفحة.", show_alert=True)
