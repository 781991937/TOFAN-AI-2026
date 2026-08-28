"""Telegram adapter for the Python automation engine.

This module accepts files and delegates extraction/splitting/page creation to
app.core. It does not call the AI service and it does not own AI callbacks.
"""

import html
import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import Message

from app.bot.keyboards import bot_lesson_list, lesson_menu
from app.bot.library import classify_lesson
from app.database import Database
from app.core.automation_engine import AutomationEngine

logger = logging.getLogger(__name__)
router = Router(name="automation")


async def save_file(message: Message, db: Database, bot, automation_engine: AutomationEngine, owner_id: int) -> None:
    document = message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in automation_engine.extractor.SUPPORTED:
        await message.answer("❌ هذا النوع غير مدعوم حاليًا. أرسل PDF أو DOCX أو TXT أو ملفًا برمجيًا مدعومًا.")
        return
    if document.file_size and document.file_size > 20 * 1024 * 1024:
        await message.answer("❌ حجم الملف أكبر من 20 MB.")
        return

    safe_name = Path(document.file_name or "lesson").name
    path = Path("data/uploads") / f"{owner_id}_{message.message_id}_{safe_name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    await message.answer("📥 <b>تم استلام الملف</b>\n\n🐍 محرك Python يستخرج المحتوى ويقسمه إلى دروس وصفحات.\n🧠 الذكاء الاصطناعي لا يعمل داخل هذا القسم.")

    try:
        await bot.download(document, destination=path)
        text = automation_engine.extract(path)
        if len(text.strip()) < 20:
            raise ValueError("لم أجد نصًا كافيًا في الملف.")

        lessons = automation_engine.split_lessons(text)
        db.ensure_user(owner_id, getattr(message.from_user, "first_name", "") or "")
        saved = []

        for number, (lesson_title, lesson_text) in enumerate(lessons, 1):
            lesson_text = str(lesson_text).strip()
            if len(lesson_text) < 20:
                continue

            lesson_name = safe_name if len(lessons) == 1 else f"{Path(safe_name).stem} - {lesson_title or f'الدرس {number}'}{suffix}"
            category = classify_lesson({
                "file_name": lesson_name,
                "extracted_text": lesson_text,
                "category": "📂 مواد أخرى",
            })
            pages = automation_engine.build_pages(lesson_text)
            lesson_id = db.create_lesson(owner_id, lesson_name, suffix[1:] or "txt", str(path), lesson_text, category=category, file_id=document.file_id)
            db.update_lesson_analysis(lesson_id, "", json.dumps([], ensure_ascii=False), automation_engine.serialize_pages(pages))
            saved.append((lesson_id, lesson_name, category, len(pages)))

        if not saved:
            raise ValueError("لم أجد محتوى صالحًا لإنشاء الدروس.")

        lines = [f"✅ <b>تم حفظ {len(saved)} درسًا منفصلًا</b>", f"📁 <b>الملف:</b> {html.escape(safe_name)}", ""]
        for i, (_lesson_id, name, category, pages) in enumerate(saved, 1):
            lines.append(f"{i}. 📖 <b>{html.escape(name)}</b>")
            lines.append(f"   📚 {html.escape(category)} • 📄 {pages} صفحة")
        lines.append("\n🧠 لكل درس اختبار مستقل من قسم الذكاء الاصطناعي، وبعد إنهاء دروس الملف ستجد الاختبار الشامل.")
        lines.append("🖼️ صفحات كل درس تبقى مرتبطة بالملف الأصلي.")

        if len(saved) == 1:
            await message.answer("\n".join(lines), reply_markup=lesson_menu(saved[0][0]))
        else:
            key = str(document.file_id or path)
            lesson_buttons = [
                {
                    "id": lesson_id,
                    "file_id": document.file_id,
                    "file_name": name,
                }
                for lesson_id, name, _category, _pages in saved
            ]
            await message.answer("\n".join(lines), reply_markup=bot_lesson_list(lesson_buttons, key))
    except Exception as exc:
        logger.exception("Python automation file processing failed")
        await message.answer(f"⚠️ <b>تعذر معالجة الملف</b>\n{html.escape(str(exc))}")


@router.message(F.document)
async def document_handler(message: Message, db: Database, bot, automation_engine: AutomationEngine) -> None:
    await save_file(message, db, bot, automation_engine, message.from_user.id)


@router.channel_post(F.document)
async def channel_document_handler(message: Message, db: Database, bot, automation_engine: AutomationEngine) -> None:
    await save_file(message, db, bot, automation_engine, 0)
