import html
import re
from pathlib import Path


COMMON_MEANINGS = {
    "variable": "متغير: اسم يخزن قيمة يمكن استخدامها وتغييرها أثناء تنفيذ البرنامج.",
    "list": "قائمة: مجموعة مرتبة من العناصر يمكن تعديلها وتسمح بتكرار العناصر.",
    "tuple": "صف: مجموعة مرتبة وثابتة لا يمكن تعديل عناصرها بعد إنشائها.",
    "dictionary": "قاموس: مجموعة بيانات على شكل مفتاح وقيمة للوصول إلى البيانات بسرعة.",
    "dict": "قاموس: مجموعة من أزواج المفتاح والقيمة.",
    "set": "مجموعة: عناصر غير مرتبة لا تسمح بتكرار العنصر نفسه.",
    "string": "سلسلة نصية: قيمة تتكون من مجموعة من الأحرف والنصوص.",
    "integer": "عدد صحيح: رقم بدون جزء عشري مثل 5 أو -3.",
    "float": "عدد عشري: رقم يمكن أن يحتوي على جزء عشري مثل 3.14.",
    "boolean": "منطقي: قيمة نتيجتها إما True (صحيح) أو False (خطأ).",
    "operation": "عملية: إجراء يُنفذ على قيمة أو أكثر للحصول على نتيجة.",
    "operations": "العمليات: مجموعة الإجراءات الحسابية أو المنطقية التي يمكن تنفيذها على البيانات.",
    "comparison": "مقارنة: عملية لفحص العلاقة بين قيمتين مثل أكبر من أو يساوي.",
    "numeric": "عددي: متعلق بالأرقام والعمليات التي تُجرى عليها.",
    "bitwise": "على مستوى البِتّات: عمليات تتعامل مع البتات الثنائية للأعداد.",
    "sequence": "تسلسل: بيانات مرتبة يمكن الوصول إلى عناصرها بالتتابع أو بالفهرس.",
    "byte": "بايت: وحدة تخزين تتكون عادةً من 8 بِتّات.",
    "bytes": "بايتات: مجموعة من وحدات البايت تمثل بيانات ثنائية.",
    "function": "دالة: جزء من البرنامج ينفذ مهمة محددة ويمكن استدعاؤه عند الحاجة.",
    "parameter": "مُعامل/وسيط: قيمة تُمرر إلى الدالة لتستخدمها أثناء التنفيذ.",
    "argument": "وسيط مستدعى: القيمة الفعلية التي نمررها إلى الدالة عند استدعائها.",
    "return": "إرجاع: إعادة نتيجة من الدالة إلى المكان الذي استدعاها.",
    "loop": "حلقة تكرار: طريقة لتكرار تنفيذ مجموعة من التعليمات عدة مرات.",
    "condition": "شرط: تعبير يحدد هل سيتم تنفيذ جزء معين من البرنامج أم لا.",
    "if": "شرط if: تعليمة تنفذ كودًا عندما يكون الشرط صحيحًا.",
    "while": "حلقة while: تكرر التعليمات ما دام الشرط صحيحًا.",
    "for": "حلقة for: تكرر التعليمات على عناصر تسلسل أو نطاق محدد.",
    "class": "صنف: قالب يحدد الخصائص والدوال التي تنتمي إلى كائنات معينة.",
    "object": "كائن: نسخة من صنف تحتوي على بيانات وسلوكيات محددة.",
    "input": "إدخال: بيانات يستقبلها البرنامج من المستخدم أو من مصدر آخر.",
    "output": "إخراج: البيانات أو النتيجة التي يعرضها البرنامج أو يرسلها.",
    "array": "مصفوفة: بنية تخزن مجموعة من القيم بطريقة مرتبة.",
    "index": "فهرس: رقم يحدد موقع عنصر داخل تسلسل مثل القائمة.",
    "module": "وحدة برمجية: ملف يحتوي كودًا يمكن استيراده وإعادة استخدامه.",
    "library": "مكتبة برمجية: مجموعة أدوات ودوال جاهزة للاستخدام في البرامج.",
    "syntax": "صياغة: القواعد التي تحدد الطريقة الصحيحة لكتابة أوامر اللغة البرمجية.",
    "method": "دالة مرتبطة بكائن أو صنف وتنفذ عملية عليه.",
    "class": "صنف: قالب لإنشاء كائنات تشترك في خصائص وسلوكيات.",
}


def _context_meaning(term: str, text: str) -> str:
    key = term.strip().lower()
    if key in COMMON_MEANINGS:
        return COMMON_MEANINGS[key]
    lines = [" ".join(x.split()).strip() for x in text.splitlines() if x.strip()]
    pattern = re.compile(re.escape(term.strip()), re.I)
    for line in lines:
        if not pattern.search(line):
            continue
        m = re.search(r"(?:-|–|—|:|=|\bis\b|\bmeans\b)\s*(.+)$", line, re.I)
        if m and len(m.group(1).strip()) >= 8:
            meaning = m.group(1).strip()
            if len(meaning) > 260:
                meaning = meaning[:257] + "..."
            return f"المعنى من تعريف الصفحة: {meaning}"
        arabic = re.findall(r"[\u0600-\u06FF][\u0600-\u06FF\s،؛:()\-–—]{5,}", line)
        if arabic:
            meaning = " ".join(arabic[0].split()).strip(" -–—:؛")
            if len(meaning) >= 8:
                return f"المعنى من سياق الصفحة: {meaning[:260]}"
    return "مصطلح مهم في الصفحة؛ راجع الجملة التي ورد فيها لفهم استخدامه."


def format_terms(terms, source_text: str, limit: int = 8) -> str:
    blocks = []
    seen = set()
    for raw in terms or []:
        value = str(raw).strip()
        if not value:
            continue
        if " — " in value:
            en, meaning = value.split(" — ", 1)
        elif " - " in value and not value.strip().startswith("-"):
            en, meaning = value.split(" - ", 1)
        else:
            en, meaning = value, _context_meaning(value, source_text)
        key = en.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        blocks.append(f"🇬🇧 <b>{html.escape(en.strip())}</b>\n↳ {html.escape(meaning.strip())}")
        if len(blocks) >= limit:
            break
    return "\n\n".join(blocks) or "لا توجد مصطلحات إنجليزية واضحة في هذه الصفحة."


def bot_page_text(lesson, pages: list[dict], index: int) -> str:
    item = pages[index]
    number = int(item.get("page", index + 1))
    title = html.escape(Path(str(lesson["file_name"] or "الدرس")).stem.replace("_", " ").strip() or "الدرس")
    raw = str(item.get("text") or "").strip()
    summary = str(item.get("summary") or "").strip()
    points = item.get("key_points") or []
    content = raw[:1450] if raw else (summary[:1450] or "لا يوجد نص واضح في هذه الصفحة.")
    points_text = "\n".join(f"• {html.escape(str(x))}" for x in points[:5]) or "• لا توجد نقاط إضافية."
    terms_text = format_terms(item.get("terms") or [], raw, 6)
    return (
        f"📖 <b>{title}</b>\n"
        f"📄 <b>الصفحة {number} من {len(pages)}</b>\n\n"
        "⚙️ <b>قسم البوت والأتمتة</b>\n"
        "🐍 تنظيم الصفحات والتنقل بواسطة Python\n\n"
        "━━━━━━━━━━━━━━\n"
        "📚 <b>محتوى الصفحة</b>\n"
        f"{html.escape(content)}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"🧠 <b>أهم النقاط</b>\n{points_text}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"📘 <b>المصطلحات ومعانيها</b>\n{terms_text}"
    )[:3900]


def ai_page_text(lesson, pages, index: int) -> str:
    number, body = pages[index]
    title = html.escape(str(lesson["file_name"] or "الدرس").split(" - ", 1)[-1])
    body = str(body or "").strip()
    return (
        f"🧠 <b>{title}</b>\n"
        f"📄 <b>الصفحة {number} من {len(pages)}</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📚 <b>محتوى الصفحة</b>\n"
        f"{html.escape(body[:3000])}\n\n"
        "━━━━━━━━━━━━━━\n"
        "🤖 <b>الشرح والاختبار: الذكاء الاصطناعي</b>"
    )[:3900]
