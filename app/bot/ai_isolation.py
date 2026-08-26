from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database import Database
from app.services.file_extractor import page_parts

router = Router(name="ai_isolation")


def _title(lesson) -> str:
    name = str(lesson["file_name"] or "الدرس")
    return name.split(" - ", 1)[1] if " - " in name else name


def _keyboard(lesson_id: int, pages: list[tuple[int, str]], index: int) -> InlineKeyboardMarkup:
    rows = []
    for start in range(0, len(pages), 6):
        rows.append([
            InlineKeyboardButton(
                text=(f"🔵 {pages[i][0]}" if i == index else f"📄 {pages[i][0]}"),
                callback_data=f"ai_page:{lesson_id}:{i}",
            )
            for i in range(start, min(start + 6, len(pages)))
        ])
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابقة", callback_data=f"ai_page:{lesson_id}:{index - 1}"))
    if index < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="التالية ➡️", callback_data=f"ai_page:{lesson_id}:{index + 1}"))
    if nav:
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(text="🧠 شرح هذه الصفحة", callback_data=f"ai_page_explain:{lesson_id}:{index}"),
        InlineKeyboardButton(text="📝 اختبار هذه الصفحة", callback_data=f"ai_page_quiz:{lesson_id}:{index}"),
    ])
    rows.append([InlineKeyboardButton(text="⬅️ قائمة الدرس", callback_data=f"ai_lessonback:{lesson_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("ai_page:"))
async def ai_page(callback: CallbackQuery, db: Database) -> None:
    try:
        _, lesson_id_text, index_text = callback.data.split(":", 2)
        lesson_id, index = int(lesson_id_text), int(index_text)
    except (ValueError, AttributeError):
        await callback.answer("❌ زر الصفحة غير صالح.", show_alert=True)
        return

    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return

    pages = page_parts(str(lesson["extracted_text"] or ""))
    if not pages or index < 0 or index >= len(pages):
        await callback.answer("❌ الصفحة غير موجودة.", show_alert=True)
        return

    number, body = pages[index]
    text = (
        f"🧠 <b>{html.escape(_title(lesson))}</b>\n"
        f"🔢 <b>صفحة {number} من {len(pages)}</b>\n"
        f"📚 <b>القسم:</b> {html.escape(str(lesson['category'] or '📂 مواد أخرى'))}\n\n"
        "🐍 <b>التنظيم والتنقل: Python</b>\n"
        "🧠 <b>الشرح والاختبار: الذكاء الاصطناعي</b>\n\n"
        "📄 <b>محتوى الصفحة</b>\n"
        f"{html.escape(body[:3000])}"
    )[:3900]

    await callback.answer()
    await callback.message.edit_text(text, reply_markup=_keyboard(lesson_id, pages, index))
