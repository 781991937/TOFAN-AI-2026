import html
import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot import automation, sections, ai_pages

TERM_MEANINGS = {
    "python": "لغة برمجة تُستخدم لبناء البرامج والأتمتة وتحليل البيانات.",
    "program": "برنامج: مجموعة تعليمات ينفذها الحاسوب لإنجاز مهمة.",
    "programming": "البرمجة: كتابة تعليمات وأوامر للحاسوب لتنفيذ المهام.",
    "variable": "متغير: اسم يخزن قيمة يمكن أن تتغير أثناء تشغيل البرنامج.",
    "function": "دالة: مجموعة أوامر لها اسم ويمكن استدعاؤها لتنفيذ مهمة محددة.",
    "list": "قائمة: بنية بيانات تخزن عدة عناصر بترتيب محدد.",
    "tuple": "صف: مجموعة مرتبة من العناصر لا يمكن تعديلها بعد إنشائها.",
    "dictionary": "قاموس: بنية تربط كل مفتاح بقيمة.",
    "set": "مجموعة: بنية بيانات تخزن عناصر غير مكررة.",
    "array": "مصفوفة: مجموعة قيم منظمة في بنية واحدة.",
    "string": "سلسلة نصية: مجموعة من الأحرف والنصوص.",
    "integer": "عدد صحيح: رقم لا يحتوي على جزء عشري.",
    "float": "عدد عشري: رقم يحتوي على جزء بعد الفاصلة.",
    "boolean": "قيمة منطقية: True أو False.",
    "loop": "حلقة تكرار: تعيد تنفيذ مجموعة أوامر عدة مرات.",
    "if": "شرط برمجي ينفذ الأوامر عندما يتحقق الشرط.",
    "while": "حلقة تكرار تستمر ما دام الشرط صحيحًا.",
    "for": "حلقة تكرار تمر على عناصر مجموعة أو نطاق من القيم.",
    "input": "إدخال: بيانات يستقبلها البرنامج من المستخدم أو مصدر آخر.",
    "output": "إخراج: النتيجة أو البيانات التي يعرضها البرنامج.",
    "excel": "برنامج جداول إلكترونية من Microsoft لتنظيم البيانات والحسابات.",
    "microsoft office": "حزمة برامج مكتبية من Microsoft مثل Word وExcel وPowerPoint.",
    "workbook": "مصنف Excel: ملف يحتوي على ورقة عمل أو أكثر.",
    "worksheet": "ورقة عمل في Excel تتكون من صفوف وأعمدة وخلايا.",
    "cell": "خلية: تقاطع صف وعمود في جدول Excel.",
    "formula": "صيغة حسابية أو منطقية تُستخدم لإنتاج نتيجة.",
    "database": "قاعدة بيانات: نظام منظم لتخزين البيانات وإدارتها واسترجاعها.",
    "file": "ملف: وحدة تخزين تحتوي بيانات أو مستندات أو برامج.",
    "algorithm": "خوارزمية: خطوات مرتبة لحل مشكلة أو تنفيذ مهمة.",
    "byte": "بايت: وحدة لقياس البيانات الرقمية، وتساوي عادة 8 بتات.",
    "operation": "عملية: إجراء حسابي أو منطقي يُنفذ على البيانات.",
}


def _meaning(term, source):
    key = re.sub(r"\s+", " ", term.lower().strip())
    if key in TERM_MEANINGS:
        return TERM_MEANINGS[key]
    m = re.search(rf"{re.escape(term)}\s*(?:[-–—:|]|\bmeans\b|\bis\b)\s*([^\n.؟!?]{{5,180}})", source, re.I)
    return m.group(1).strip() if m else "شرح المصطلح يُستنتج من الجملة التي ورد فيها في الدرس."


def _pretty(source, limit=1800):
    text = str(source or "").replace("\r", "\n")
    text = re.sub(r"\s+(?=\d+(?:\.\d+)+\s)", "\n", text)
    lines, seen = [], set()
    for raw in text.splitlines():
        line = " ".join(raw.split()).strip()
        if not line or re.fullmatch(r"(?:Page|صفحة)\s*\d+", line, re.I):
            continue
        k = line.casefold()
        if k in seen:
            continue
        seen.add(k)
        lines.extend(re.split(r"(?<=[.!؟?])\s+", line) if len(line) > 420 else [line])
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\d+(?:\.\d+)+\s", line):
            out.append(f"🔹 <b>{html.escape(line[:240])}</b>")
        elif re.match(r"^(?:[-•*]|\d+[.)])\s", line):
            out.append(f"• {html.escape(line)}")
        else:
            out.append(html.escape(line))
        if len("\n".join(out)) >= limit:
            break
    return "\n".join(out)[:limit] or "لا يوجد نص واضح في هذه الصفحة."


def bot_page_text(lesson, index):
    pages = automation._load_pages(lesson)
    index = max(0, min(index, len(pages) - 1))
    item = pages[index]
    source = str(item.get("text") or "")
    terms = []
    for raw in (item.get("terms") or [])[:8]:
        value = str(raw)
        if " — " in value:
            en, ar = value.split(" — ", 1); meaning = ar.strip()
        elif " - " in value:
            en, ar = value.split(" - ", 1); meaning = ar.strip()
        else:
            en, meaning = value, _meaning(value, source)
        terms.append(f"🔤 <b>{html.escape(en.strip())}</b>\n📌 <b>المعنى:</b> {html.escape(meaning)}")
    points = item.get("key_points") or []
    return (f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n"
            f"📄 <b>صفحة {int(item.get('page', index + 1))} من {len(pages)}</b>\n\n"
            "⚙️ <b>البوت والأتمتة — Python</b>\n\n"
            "📚 <b>محتوى الصفحة</b>\n" + _pretty(source) + "\n\n"
            "📌 <b>أهم النقاط</b>\n" + ("\n".join(f"• {html.escape(str(x))}" for x in points[:5]) or "• لا توجد نقاط إضافية.") + "\n\n"
            "🇬🇧 <b>المصطلحات الإنجليزية ومعانيها</b>\n" + ("\n\n".join(terms) or "لا توجد مصطلحات إنجليزية واضحة."))[:3900]


def bot_page_keyboard(lid, pages, index):
    rows = []
    for start in range(0, len(pages), 6):
        rows.append([InlineKeyboardButton(text=("🔵 " if i == index else "📄 ") + str(pages[i].get("page", i + 1)), callback_data=f"page:{lid}:{i}") for i in range(start, min(start + 6, len(pages)))])
    nav = []
    if index > 0:
        nav += [InlineKeyboardButton(text="⏮️ الصفحة الأولى", callback_data=f"page:{lid}:0"), InlineKeyboardButton(text="⬅️ السابقة", callback_data=f"page:{lid}:{index-1}")]
    if index < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="التالية ➡️", callback_data=f"page:{lid}:{index+1}"))
    if nav: rows.append(nav)
    if index == len(pages) - 1:
        rows.append([InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"bot_quiz:{lid}")])
    rows.append([InlineKeyboardButton(text="⬅️ قائمة الدرس", callback_data=f"lesson:{lid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_page_keyboard(lid, pages, index):
    rows = []
    for start in range(0, len(pages), 6):
        rows.append([InlineKeyboardButton(text=("🔵 " if i == index else "📄 ") + str(pages[i][0]), callback_data=f"ai_page:{lid}:{i}") for i in range(start, min(start + 6, len(pages)))])
    nav = []
    if index > 0:
        nav += [InlineKeyboardButton(text="⏮️ الصفحة الأولى", callback_data=f"ai_page:{lid}:0"), InlineKeyboardButton(text="⬅️ السابقة", callback_data=f"ai_page:{lid}:{index-1}")]
    if index < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="التالية ➡️", callback_data=f"ai_page:{lid}:{index+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text="🧠 شرح هذه الصفحة", callback_data=f"ai_page_explain:{lid}:{index}")])
    if index == len(pages) - 1:
        rows.append([InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"ai_quiz:{lid}")])
    rows.append([InlineKeyboardButton(text="⬅️ قائمة الدرس", callback_data=f"ai_lessonback:{lid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def fixed_show_page(callback, lesson, index):
    pages = automation._load_pages(lesson)
    if not pages:
        await callback.answer("لا توجد صفحات محفوظة.", show_alert=True); return
    index = max(0, min(index, len(pages) - 1))
    try:
        await callback.message.edit_text(bot_page_text(lesson, index), reply_markup=bot_page_keyboard(int(lesson['id']), pages, index))
        await callback.answer()
    except TelegramBadRequest as exc:
        await callback.answer("أنت بالفعل في هذه الصفحة." if "not modified" in str(exc).lower() else "⚠️ تعذر تحديث الصفحة.")


automation._page_text = bot_page_text
automation._page_keyboard = bot_page_keyboard
automation._show_page = fixed_show_page
try:
    automation.router.callback_query.handlers = [h for h in automation.router.callback_query.handlers if getattr(getattr(h, "callback", None), "__name__", "") != "lesson"]
except Exception:
    pass
sections.page_kb = ai_page_keyboard
sections.page_keyboard = ai_page_keyboard
ai_pages.page_kb = ai_page_keyboard
