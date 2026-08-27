from __future__ import annotations

import html
import io
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from aiogram import F, Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards import bot_lesson_list
from app.bot.quiz_engine import QuizState, send_question
from app.database import Database
from app.services.file_extractor import page_parts
from app.services.pdf_page_renderer import download_telegram_file, render_pdf_bytes
from app.services.quiz_generator import QuizGenerator

logger = logging.getLogger(__name__)
router = Router(name="bot_page_images")


def _pages(lesson) -> list[dict]:
    text = str(lesson["extracted_text"] or "")
    suffix = Path(str(lesson["file_name"] or "")).suffix.lower()
    try:
        pages = json.loads(lesson["key_points"] or "[]")
        if isinstance(pages, list) and pages and isinstance(pages[0], dict) and "page" in pages[0]:
            # Old DOCX records were sometimes cached as one virtual page even
            # when the extracted lesson is much longer. Rebuild those pages.
            if suffix == ".docx" and len(pages) == 1 and len(text) > 1800:
                return [
                    {"page": number, "text": body, "summary": "", "key_points": [], "terms": []}
                    for number, body in page_parts(text)
                ]
            return pages
    except Exception:
        pass
    return [
        {"page": number, "text": body, "summary": "", "key_points": [], "terms": []}
        for number, body in page_parts(text)
    ]


def _keyboard(lesson_id: int, pages: list[dict], index: int) -> InlineKeyboardMarkup:
    rows = []
    numbers = [int(item.get("page", i + 1)) for i, item in enumerate(pages)]
    for start in range(0, len(numbers), 6):
        rows.append([
            InlineKeyboardButton(
                text=(f"🔵 {numbers[i]}" if i == index else f"📄 {numbers[i]}"),
                callback_data=f"bot_page:{lesson_id}:{i}",
            )
            for i in range(start, min(start + 6, len(numbers)))
        ])
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابقة", callback_data=f"bot_page:{lesson_id}:{index - 1}"))
    if index < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="التالية ➡️", callback_data=f"bot_page:{lesson_id}:{index + 1}"))
    if nav:
        rows.append(nav)
    if index == len(pages) - 1:
        rows.append([InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"bot_quiz:{lesson_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ دروس الملف", callback_data=f"bot_lessonback:{lesson_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _caption(lesson, index: int, total: int, rendered_original: bool = True) -> str:
    note = "🖼️ الصفحة من الملف الأصلي بدون تلخيص أو إعادة تنسيق." if rendered_original else "🖼️ تم إنشاء نسخة مرئية مرتبة للملف لأن صيغة المستند لا توفر صفحة PDF أصلية."
    return (
        f"🤖 <b>البوت والأتمتة — Python</b>\n"
        f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n"
        f"📄 <b>الصفحة {index + 1} من {total}</b>\n\n{note}"
    )


def _font(size: int):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _render_text_page(text: str) -> bytes:
    from PIL import Image, ImageDraw
    width, height, margin = 1600, 2200, 90
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font, small = _font(42), _font(34)
    max_width = width - margin * 2
    lines = []
    for paragraph in str(text or "").splitlines():
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = current + " " + word
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    y = margin
    for line in lines:
        if y > height - margin - 80:
            break
        rtl = any("\u0600" <= c <= "\u06ff" for c in line)
        draw.text((width - margin, y), line, font=font, fill="black", anchor="ra", direction="rtl" if rtl else None)
        y += 62
    draw.text((width - margin, height - margin + 5), "TOFAN AI • البوت والأتمتة — Python", font=small, fill="black", anchor="ra", direction="rtl")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


def _convert_docx_to_pdf(docx_bytes: bytes, filename: str) -> bytes | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    with tempfile.TemporaryDirectory(prefix="tofan_docx_") as tmp:
        root = Path(tmp)
        source = root / Path(filename or "lesson.docx").name
        if source.suffix.lower() != ".docx":
            source = source.with_suffix(".docx")
        source.write_bytes(docx_bytes)
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(root), str(source)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except Exception:
            logger.exception("DOCX to PDF conversion failed")
            return None
        pdf_path = source.with_suffix(".pdf")
        return pdf_path.read_bytes() if pdf_path.exists() else None


async def _render_page(lesson, pages: list[dict], index: int, bot: Bot) -> tuple[bytes, bool]:
    file_id = str(lesson["file_id"] or "").strip()
    if not file_id:
        raise ValueError("لا توجد نسخة Telegram أصلية لهذا الملف. أعد رفع الملف مرة واحدة.")
    raw, telegram_path = await download_telegram_file(bot, file_id)
    suffix = Path(str(lesson["file_name"] or telegram_path)).suffix.lower()
    if suffix == ".pdf" or raw.startswith(b"%PDF"):
        return render_pdf_bytes(raw, int(pages[index].get("page", index + 1)) - 1), True
    if suffix == ".docx":
        converted = _convert_docx_to_pdf(raw, str(lesson["file_name"]))
        if converted:
            return render_pdf_bytes(converted, index), True
    body = str(pages[index].get("text") or pages[index].get("summary") or "").strip()
    return _render_text_page(body), False


async def _show(callback: CallbackQuery, lesson, index: int, bot: Bot) -> None:
    pages = _pages(lesson)
    if not pages:
        await callback.answer("❌ لا توجد صفحات محفوظة لهذا الدرس.", show_alert=True)
        return
    index = max(0, min(index, len(pages) - 1))
    try:
        image, original = await _render_page(lesson, pages, index, bot)
        photo = BufferedInputFile(image, filename=f"lesson_{lesson['id']}_page_{index + 1}.jpg")
        if callback.message:
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                pass
            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=photo,
                caption=_caption(lesson, index, len(pages), original),
                reply_markup=_keyboard(int(lesson["id"]), pages, index),
            )
        await callback.answer()
    except Exception as exc:
        logger.exception("Could not render bot lesson page")
        await callback.answer(f"⚠️ تعذر عرض الصفحة: {str(exc)[:120]}", show_alert=True)


@router.callback_query(F.data.startswith("pages:"))
async def open_pages(callback: CallbackQuery, db: Database, bot: Bot) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await _show(callback, lesson, 0, bot)


@router.callback_query(F.data.startswith("bot_page:"))
async def bot_page(callback: CallbackQuery, db: Database, bot: Bot) -> None:
    try:
        _, lesson_text, index_text = callback.data.split(":", 2)
        lesson_id, index = int(lesson_text), int(index_text)
    except (ValueError, AttributeError):
        await callback.answer("❌ زر صفحة غير صالح.", show_alert=True)
        return
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await _show(callback, lesson, index, bot)


@router.callback_query(F.data.startswith("bot_lessonback:"))
async def bot_lessonback(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    from app.bot.bot_library_isolation import _bot_lessons
    from app.bot.library import file_lessons
    lessons = _bot_lessons(db, callback.from_user.id)
    key = str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])
    selected = file_lessons(lessons, key)
    if not selected:
        await callback.answer("❌ تعذر العثور على دروس الملف.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        f"🤖 <b>قسم البوت والأتمتة</b>\n📘 <b>{html.escape(str(lesson['file_name']))}</b>\n\nاختر الدرس:",
        reply_markup=bot_lesson_list(selected, key),
    )


@router.callback_query(F.data.startswith("bot_quiz:"))
async def bot_lesson_quiz_from_page(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    text = str(lesson["extracted_text"] or "").strip()
    if not text:
        await callback.answer("⚠️ لا يوجد محتوى كافٍ لهذا الدرس.", show_alert=True)
        return
    try:
        await callback.answer("📝 جاري إعداد الاختبار…")
        questions = await quiz_generator.create_local(text, 20, "medium")
        if not questions:
            await callback.answer("⚠️ لم أجد معلومات كافية لإنشاء الاختبار.", show_alert=True)
            return
        quiz_id = db.create_quiz(lesson_id, quiz_generator.serialize(questions), len(questions), "medium")
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=lesson_id, questions=questions, answers=[], group_mode=False, engine="local", user_id=callback.from_user.id)
        if callback.message:
            await callback.message.answer(
                f"📝 <b>اختبار الدرس</b>\n\n📖 <b>{html.escape(str(lesson['file_name']))}</b>\n"
                "🤖 <b>البوت والأتمتة — Python</b>\n"
                f"🎯 <b>{len(questions)} سؤالًا</b>\n⏱️ <b>15 ثانية لكل سؤال</b>\n\n"
                "إذا لم تختر إجابة خلال 15 ثانية سينتقل الاختبار تلقائيًا للسؤال التالي."
            )
            await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception as exc:
        logger.exception("Local bot lesson quiz from page failed")
        if callback.message:
            await callback.message.answer(f"⚠️ <b>تعذر إنشاء اختبار الدرس</b>\n{html.escape(str(exc))}")
