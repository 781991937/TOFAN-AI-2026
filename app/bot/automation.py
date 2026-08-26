import html
import json
import logging
import re
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import delete_lesson_confirm, lesson_menu, lessons_list_menu
from app.bot.quiz_engine import QuizState, send_question
from app.database import Database
from app.services.file_extractor import FileExtractor, clean_text, page_parts, split_lessons
from app.services.local_engine import local_analysis
from app.services.quiz_generator import QuizGenerator

logger = logging.getLogger(__name__)
router = Router(name="automation")


def _title(name: str) -> str:
    return html.escape(Path(name).stem.replace("_", " ").strip() or "الملف")


def _format_local(analysis: dict) -> str:
    summary = html.escape(str(analysis.get("summary") or "لا يوجد ملخص كافٍ."))
    terms = analysis.get("english_terms") or []
    term_lines = []
    for term in terms[:8]:
        raw = str(term)
        if " — " in raw:
            en, ar = raw.split(" — ", 1)
        elif " - " in raw:
            en, ar = raw.split(" - ", 1)
        else:
            en, ar = raw, "المصطلح كما ورد في الملف"
        term_lines.append(f"<b>{html.escape(en.strip())}</b>\n{html.escape(ar.strip())}")
    terms_text = "\n\n".join(term_lines) or "لا توجد مصطلحات واضحة."
    return f"⚙️ <b>طريقة العمل: البوت والأتمتة — Python</b>\n\n📖 <b>تنظيم سريع</b>\n{summary}\n\n🇬🇧 <b>المصطلحات</b>\n{terms_text}"


def _page_cache(text: str) -> list[dict]:
    result = []
    for number, body in page_parts(text):
        analysis = local_analysis(body)
        result.append({
            "page": int(number),
            "text": body,
            "summary": str(analysis.get("summary") or "")[:2200],
            "key_points": (analysis.get("key_points") or [])[:6],
            "terms": (analysis.get("english_terms") or [])[:8],
        })
    return result


def _load_pages(lesson) -> list[dict]:
    try:
        cached = json.loads(lesson["key_points"] or "[]")
        if isinstance(cached, list) and cached and isinstance(cached[0], dict) and "page" in cached[0]:
            for item in cached:
                if not item.get("text"):
                    item["text"] = ""
            return cached
    except Exception:
        pass
    return _page_cache(str(lesson["extracted_text"] or ""))


def _page_text(lesson, index: int) -> str:
    pages = _load_pages(lesson)
    if not pages:
        return "❌ لا توجد صفحات محفوظة لهذا الملف."
    index = max(0, min(index, len(pages) - 1))
    item = pages[index]
    number = int(item.get("page", index + 1))
    summary = html.escape(str(item.get("summary") or "").strip())
    points = item.get("key_points") or []
    points_text = "\n".join(f"• {html.escape(str(x))}" for x in points[:6]) or "• لا توجد نقاط إضافية."
    terms = item.get("terms") or []
    term_blocks = []
    for raw in terms[:8]:
        value = str(raw)
        if " — " in value:
            en, ar = value.split(" — ", 1)
        else:
            en, ar = value, "المعنى العربي موجود في محتوى الصفحة"
        term_blocks.append(f"<b>{html.escape(en.strip())}</b>\n{html.escape(ar.strip())}")
    terms_text = "\n\n".join(term_blocks) or "لا توجد مصطلحات واضحة."
    return (
        f"📖 <b>الدرس: {_title(str(lesson['file_name']))}</b>\n"
        f"📄 <b>صفحة {number} من {len(pages)}</b>\n\n"
        "⚙️ <b>طريقة الشرح: البوت والأتمتة — بدون ذكاء اصطناعي</b>\n\n"
        "📚 <b>محتوى الصفحة</b>\n"
        f"{summary or 'لا يوجد نص واضح في هذه الصفحة.'}\n\n"
        f"📌 <b>أهم النقاط</b>\n{points_text}\n\n"
        f"🇬🇧 <b>English Terms</b>\n{terms_text}"
    )[:3900]


def _page_keyboard(lesson_id: int, pages: list[dict], index: int):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    numbers = [int(x.get("page", i + 1)) for i, x in enumerate(pages)]
    for start in range(0, len(numbers), 6):
        rows.append([
            InlineKeyboardButton(
                text=(f"🔵 {numbers[i]}" if i == index else f"📄 {numbers[i]}"),
                callback_data=f"page:{lesson_id}:{i}",
            ) for i in range(start, min(start + 6, len(numbers)))
        ])
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="⬅️ الصفحة السابقة", callback_data=f"page:{lesson_id}:{index - 1}"))
    if index < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="الصفحة التالية ➡️", callback_data=f"page:{lesson_id}:{index + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"bot_quiz:{lesson_id}")])
    rows.append([
        InlineKeyboardButton(text="⬅️ الملف السابق", callback_data=f"prevfile:{lesson_id}"),
        InlineKeyboardButton(text="الملف التالي ➡️", callback_data=f"nextfile:{lesson_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lesson_id}"),
        InlineKeyboardButton(text="⬅️ قائمة الدرس", callback_data=f"lesson:{lesson_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_page(callback: CallbackQuery, lesson, index: int) -> None:
    pages = _load_pages(lesson)
    if not pages:
        await callback.answer("لا توجد صفحات محفوظة.", show_alert=True)
        return
    index = max(0, min(index, len(pages) - 1))
    try:
        await callback.message.edit_text(_page_text(lesson, index), reply_markup=_page_keyboard(int(lesson["id"]), pages, index))
        await callback.answer()
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            await callback.answer("أنت في نفس الصفحة.")
        else:
            raise


async def save_file(message: Message, db: Database, bot, extractor: FileExtractor, owner_id: int) -> None:
    document = message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in extractor.SUPPORTED:
        await message.answer("❌ هذا النوع غير مدعوم للاستخراج حاليًا. أرسل ملفًا تعليميًا نصيًا أو مكتبيًا من الأنواع المدعومة.")
        return
    if document.file_size and document.file_size > 20 * 1024 * 1024:
        await message.answer("❌ حجم الملف أكبر من 20 MB.")
        return

    safe_name = Path(document.file_name or "lesson").name
    path = Path("data/uploads") / f"{owner_id}_{message.message_id}_{safe_name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    await message.answer("📥 <b>تم استلام الملف</b>\n⚙️ البوت الآن يستكشف النوع، يقسم المحتوى، ويرتبه في المكتبة.\n💾 وستبقى نسخة Telegram قابلة للتنزيل لاحقًا.")
    try:
        await bot.download(document, destination=path)
        text = clean_text(extractor.extract(path))
        if len(text.strip()) < 20:
            raise ValueError("لم أجد نصًا كافيًا في الملف.")
        lessons = split_lessons(text)
        if not lessons:
            lessons = [("الدرس الكامل", text)]
        db.ensure_user(owner_id, getattr(message.from_user, "first_name", "") or "")

        saved = []
        for number, (lesson_title, lesson_text) in enumerate(lessons, 1):
            lesson_text = clean_text(lesson_text)
            if len(lesson_text) < 20:
                continue
            lesson_name = safe_name if len(lessons) == 1 else f"{Path(safe_name).stem} - {lesson_title or f'الدرس {number}'}{suffix}"
            pages = _page_cache(lesson_text)
            analysis = local_analysis("\n\n".join(x.get("text", "") for x in pages))
            category = "📂 مواد أخرى"
            from app.bot.library import classify_lesson
            category = classify_lesson({"file_name": lesson_name, "extracted_text": lesson_text, "category": category})
            lesson_id = db.create_lesson(owner_id, lesson_name, suffix[1:], str(path), lesson_text, category=category, file_id=document.file_id)
            db.update_lesson_analysis(lesson_id, analysis.get("summary", ""), json.dumps(analysis.get("concepts", []), ensure_ascii=False), json.dumps(pages, ensure_ascii=False))
            saved.append((lesson_id, lesson_name, category, len(pages)))

        if not saved:
            raise ValueError("لم أجد محتوى صالحًا لإنشاء الدروس.")
        lines = [f"✅ <b>تم حفظ {len(saved)} درسًا</b>", f"📁 <b>الملف:</b> {html.escape(safe_name)}", ""]
        for i, (lesson_id, name, category, pages) in enumerate(saved, 1):
            lines.append(f"{i}. 📖 <b>{html.escape(name)}</b>")
            lines.append(f"   📚 {html.escape(category)}  •  📄 {pages} صفحة")
        lines.append("\n💾 <b>الملف الأصلي محفوظ عبر Telegram ويمكن تنزيله لاحقًا حتى لو حذفته من هاتفك.</b>")
        if len(saved) == 1:
            await message.answer("\n".join(lines) + "\n\nاختر من أزرار الملف:", reply_markup=lesson_menu(saved[0][0]))
        else:
            await message.answer("\n".join(lines))
    except Exception as exc:
        logger.exception("Automation file processing failed")
        await message.answer(f"⚠️ <b>تعذر معالجة الملف</b>\n{html.escape(str(exc))}")


@router.message(F.document)
async def document_handler(message: Message, db: Database, bot, extractor: FileExtractor) -> None:
    await save_file(message, db, bot, extractor, message.from_user.id)


@router.channel_post(F.document)
async def channel_document_handler(message: Message, db: Database, bot, extractor: FileExtractor) -> None:
    await save_file(message, db, bot, extractor, 0)


@router.callback_query(F.data.startswith("bot_quiz:"))
async def bot_lesson_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
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
        await callback.answer("📝 جاري إعداد اختبار الدرس…")
        questions = await quiz_generator.create_local(text, 20, "medium")
        if not questions:
            await callback.message.edit_text("⚠️ لم أجد معلومات كافية لإنشاء اختبار لهذا الدرس.")
            return
        quiz_id = db.create_quiz(lesson_id, quiz_generator.serialize(questions), len(questions), "medium")
        await state.set_state(QuizState.active)
        await state.update_data(
            quiz_id=quiz_id,
            lesson_id=lesson_id,
            questions=questions,
            answers=[],
            group_mode=False,
            engine="local",
        )
        await callback.message.edit_text(
            f"📝 <b>اختبار الدرس</b>\n\n"
            f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n"
            f"⚙️ <b>طريقة العمل: البوت والأتمتة — Python</b>\n"
            f"🎯 <b>{len(questions)} سؤالًا</b>\n\n"
            "العدد يتحدد حسب كمية المعلومات في الدرس، ولن يتم تكرار الأسئلة.",
        )
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception as exc:
        logger.exception("Local bot lesson quiz failed")
        await callback.message.edit_text(f"⚠️ <b>تعذر إنشاء اختبار الدرس</b>\n{html.escape(str(exc))}")


@router.callback_query(F.data.startswith("pages:"))
async def pages(callback: CallbackQuery, db: Database) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]), callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True); return
    await _show_page(callback, lesson, 0)


@router.callback_query(F.data.startswith("page:"))
async def page(callback: CallbackQuery, db: Database) -> None:
    _, lesson_id, index = callback.data.split(":")
    lesson = db.get_lesson(int(lesson_id), callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True); return
    await _show_page(callback, lesson, int(index))


def _file_group(lessons: list, lesson) -> list:
    key = str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])
    groups = []
    seen = set()
    for item in lessons:
        item_key = str(item["file_id"] or item["file_path"] or item["file_name"])
        if item_key not in seen:
            seen.add(item_key); groups.append((item_key, item))
    return groups


async def _move_file(callback: CallbackQuery, db: Database, lesson_id: int, direction: int) -> None:
    lessons = db.get_lessons(callback.from_user.id, 1000)
    current = db.get_lesson(lesson_id, callback.from_user.id)
    if not current:
        await callback.answer("❌ الملف غير موجود.", show_alert=True); return
    groups = _file_group(lessons, current)
    current_key = str(current["file_id"] or current["file_path"] or current["file_name"])
    ids = [key for key, _ in groups]
    pos = ids.index(current_key) + direction
    if pos < 0 or pos >= len(groups):
        await callback.answer("📚 لا يوجد ملف آخر في هذا الاتجاه.", show_alert=True); return
    target = groups[pos][1]
    await callback.answer()
    await callback.message.edit_text(
        f"📘 <b>{html.escape(str(target['file_name']))}</b>\n📚 <b>{html.escape(str(target['category'] or '📂 مواد أخرى'))}</b>\n\n⚙️ <b>قسم البوت والأتمتة</b>\nاختر ما تريد:",
        reply_markup=lesson_menu(int(target["id"])),
    )


@router.callback_query(F.data.startswith("prevfile:"))
async def previous_file(callback: CallbackQuery, db: Database) -> None:
    await _move_file(callback, db, int(callback.data.split(":")[1]), -1)


@router.callback_query(F.data.startswith("nextfile:"))
async def next_file(callback: CallbackQuery, db: Database) -> None:
    await _move_file(callback, db, int(callback.data.split(":")[1]), 1)


@router.callback_query(F.data.startswith("download:"))
async def download(callback: CallbackQuery, db: Database, bot) -> None:
    lesson = db.get_lesson(int(callback.data.split(":")[1]), callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الملف غير موجود.", show_alert=True); return
    file_id = str(lesson["file_id"] or "")
    if not file_id:
        await callback.answer("⚠️ هذه نسخة قديمة لا تحتوي معرف Telegram. أعد إرسال الملف مرة واحدة.", show_alert=True); return
    await callback.answer("📥 جاري إرسال الملف…")
    try:
        await bot.send_document(callback.from_user.id, file_id, caption=f"📚 {html.escape(str(lesson['file_name']))}")
    except Exception:
        logger.exception("File resend failed")
        await callback.answer("⚠️ تعذر إرسال الملف.", show_alert=True)


@router.callback_query(F.data.startswith("delete_lesson:"))
async def delete_request(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الملف غير موجود.", show_alert=True); return
    await callback.answer()
    await callback.message.edit_text(
        f"⚠️ <b>حذف الملف</b>\n\n📘 {html.escape(str(lesson['file_name']))}\n\nسيُحذف من المكتبة، أما نسخة Telegram فلا تُحذف من رسالتك السابقة.",
        reply_markup=delete_lesson_confirm(lesson_id),
    )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def delete_confirmed(callback: CallbackQuery, db: Database) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الملف غير موجود.", show_alert=True); return
    path = Path(str(lesson["file_path"] or ""))
    db.delete_lesson(lesson_id, callback.from_user.id)
    if path.exists():
        try: path.unlink()
        except OSError: logger.warning("Could not delete local file %s", path)
    await callback.answer("تم الحذف ✅")
    rows = db.get_lessons(callback.from_user.id, 1000)
    await callback.message.edit_text(
        "🗑️ <b>تم حذف الملف من مكتبتك.</b>\n\nيمكنك إعادة إرسال ملف جديد في أي وقت." if not rows else "🗑️ <b>تم حذف الملف.</b>\n\n📚 اختر من المكتبة لمتابعة الدراسة.",
    )


@router.callback_query(F.data == "file_management")
async def file_management(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "📥 <b>إدارة الملفات — الأتمتة</b>\n\n"
        "• استقبال الملفات التعليمية\n• اكتشاف النوع وتنظيمها في الأقسام\n• تقسيمها إلى دروس وصفحات\n• حفظ نسخة Telegram للتنزيل لاحقًا\n\n"
        "⚙️ التنفيذ هنا بواسطة Python والبوت فقط، بدون ذكاء اصطناعي.",
    )


@router.callback_query(F.data == "navigation_help")
async def navigation_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "🧭 <b>التنقل — الأتمتة</b>\n\n"
        "بعد اختيار القسم ← الملف ← الدرس ستجد أزرار الصفحات، الصفحة السابقة/التالية، الملف السابق/التالي، والتنزيل، واختبار الدرس.\n\n"
        "⚙️ كل هذا يعمل بواسطة Python والبوت، واختبار الدرس يستخدم محرك الأسئلة المحلي بدون ذكاء اصطناعي.",
    )
