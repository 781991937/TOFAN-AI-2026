import hashlib
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _enc(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _rows(buttons, width: int = 2):
    return [buttons[i:i + width] for i in range(0, len(buttons), width)]


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 قسم الذكاء الاصطناعي", callback_data="ai_section"), InlineKeyboardButton(text="🤖 قسم البوت", callback_data="bot_section")],
        [InlineKeyboardButton(text="⚙️ إعدادات البوت", callback_data="settings"), InlineKeyboardButton(text="❓ المساعدة", callback_data="help")],
    ])


def section_menu(section: str):
    library = "ai_library" if section == "ai" else "bot_library"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 المكتبة", callback_data=library), InlineKeyboardButton(text="📥 إدارة الملفات", callback_data="file_management")],
        [InlineKeyboardButton(text="🧭 الصفحات والتنقل", callback_data="navigation_help"), InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])


def ai_categories_menu(c):
    rows = _rows([InlineKeyboardButton(text=f"{r['category']} ({int(r['lesson_count'])})", callback_data=f"ai_category:{_enc(str(r['category']))}") for r in c])
    rows.append([InlineKeyboardButton(text="⬅️ قسم الذكاء", callback_data="ai_section")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bot_categories_menu(c):
    rows = _rows([InlineKeyboardButton(text=f"{r['category']} ({int(r['lesson_count'])})", callback_data=f"bot_category:{_enc(str(r['category']))}") for r in c])
    rows.append([InlineKeyboardButton(text="⬅️ قسم البوت", callback_data="bot_section")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_category_menu(cat):
    t = _enc(cat)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 ملفات القسم", callback_data=f"ai_categoryfiles:{t}"), InlineKeyboardButton(text="🎓 اختبار القسم كامل", callback_data=f"ai_categoryquiz:{t}")],
        [InlineKeyboardButton(text="⬅️ المكتبة", callback_data="ai_library")],
    ])


def ai_files_menu(files, cat):
    rows = _rows([InlineKeyboardButton(text=f"📘 {n} ({c})", callback_data=f"ai_file:{_enc(k)}") for k, n, c in files])
    rows.append([InlineKeyboardButton(text="⬅️ القسم", callback_data=f"ai_category:{_enc(cat)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_lessons_menu(lessons, key):
    b = []
    for n, l in enumerate(lessons, 1):
        t = str(l["file_name"] or f"الدرس {n}")
        t = t.split(" - ", 1)[1] if " - " in t else t
        t = t[:22] + "..." if len(t) > 25 else t
        b.append(InlineKeyboardButton(text=f"📖 {n}: {t}", callback_data=f"ai_lesson:{int(l['id'])}:{_enc(key)}"))
    rows = _rows(b)
    if len(lessons) > 1:
        rows.append([InlineKeyboardButton(text="🎓 اختبار شامل للملف", callback_data=f"ai_filequiz:{_enc(key)}")])
    rows.append([InlineKeyboardButton(text="⬅️ الملفات", callback_data=f"ai_fileback:{_enc(key)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_lesson_menu(lid, key):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 شرح ذكي", callback_data=f"ai_explain:{lid}"), InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"ai_quiz:{lid}")],
        [InlineKeyboardButton(text="📖 صفحات الدرس", callback_data=f"ai_pages:{lid}"), InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lid}")],
        [InlineKeyboardButton(text="⬅️ الملف السابق", callback_data=f"ai_prevfile:{lid}"), InlineKeyboardButton(text="الملف التالي ➡️", callback_data=f"ai_nextfile:{lid}")],
        [InlineKeyboardButton(text="⬅️ دروس الملف", callback_data=f"ai_fileback:{_enc(key)}")],
    ])


def automation_lesson_menu(lid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 صفحات الدرس", callback_data=f"pages:{lid}"), InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lid}")],
        [InlineKeyboardButton(text="⬅️ الملف السابق", callback_data=f"prevfile:{lid}"), InlineKeyboardButton(text="الملف التالي ➡️", callback_data=f"nextfile:{lid}")],
        [InlineKeyboardButton(text="🗑️ حذف الملف", callback_data=f"delete_lesson:{lid}"), InlineKeyboardButton(text="⬅️ المكتبة", callback_data="bot_library")],
    ])


def lesson_menu(lid):
    return automation_lesson_menu(lid)


def delete_lesson_confirm(lid):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑️ نعم، احذف الدرس", callback_data=f"confirm_delete:{lid}"), InlineKeyboardButton(text="❌ إلغاء", callback_data=f"lesson:{lid}")]])


def file_list_menu(lessons, cat):
    g = {}
    for l in lessons:
        k = str(l["file_id"] or l["file_path"] or l["file_name"])
        g.setdefault(k, [str(l["file_name"]), 0])[1] += 1
    rows = _rows([InlineKeyboardButton(text=f"📘 {n[:25]}{'...' if len(n) > 28 else ''} ({c})", callback_data=f"bot_file:{_enc(k)}") for k, (n, c) in g.items()])
    rows.append([InlineKeyboardButton(text="⬅️ الأقسام", callback_data="bot_library")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bot_lesson_list(lessons, key):
    b = []
    for n, l in enumerate(lessons, 1):
        t = str(l["file_name"] or f"الدرس {n}")
        t = t.split(" - ", 1)[1] if " - " in t else t
        t = t[:22] + "..." if len(t) > 25 else t
        b.append(InlineKeyboardButton(text=f"📖 {n}: {t}", callback_data=f"bot_lesson:{int(l['id'])}:{_enc(key)}"))
    rows = _rows(b)
    rows.append([InlineKeyboardButton(text="⬅️ الملفات", callback_data=f"bot_fileback:{_enc(key)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lessons_list_menu(lessons):
    cats = {}
    for l in lessons:
        cats[str(l["category"] or "📂 مواد أخرى")] = cats.get(str(l["category"] or "📂 مواد أخرى"), 0) + 1
    return bot_categories_menu([{"category": k, "lesson_count": v} for k, v in cats.items()])


def result_menu(lid, group=False, bot=False, comprehensive_key: str | None = None):
    retry = f"bot_quiz:{lid}" if bot else f"ai_quiz:{lid}"
    back = f"lesson:{lid}" if bot else f"ai_lessonback:{lid}"
    rows = [[InlineKeyboardButton(text="🔁 اختبار جديد", callback_data=retry), InlineKeyboardButton(text="⬅️ رجوع للدرس", callback_data=back)]]
    if comprehensive_key and not bot:
        rows.insert(0, [InlineKeyboardButton(text="🎓 الاختبار الشامل للملف", callback_data=f"ai_filequiz:{_enc(comprehensive_key)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_menu(count, difficulty):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"عدد الأسئلة: {count}", callback_data="set_count"), InlineKeyboardButton(text=f"الصعوبة: {difficulty}", callback_data="set_difficulty")], [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")]])


def count_menu():
    return InlineKeyboardMarkup(inline_keyboard=_rows([InlineKeyboardButton(text=str(n), callback_data=f"count:{n}") for n in (5, 10, 15, 20, 30)]))


def difficulty_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🟢 سهل", callback_data="difficulty:easy"), InlineKeyboardButton(text="🟡 متوسط", callback_data="difficulty:medium")], [InlineKeyboardButton(text="🔴 صعب", callback_data="difficulty:hard")]])


def page_keyboard(lid, pages, i):
    rows = []
    for s in range(0, len(pages), 6):
        rows.append([InlineKeyboardButton(text=("🔵" if j == i else "📄") + f" {pages[j][0]}", callback_data=f"ai_page:{lid}:{j}") for j in range(s, min(s + 6, len(pages)))])
    nav = []
    if i > 0:
        nav.append(InlineKeyboardButton(text="⏮️ الأولى", callback_data=f"ai_page:{lid}:0"))
        nav.append(InlineKeyboardButton(text="⬅️ السابقة", callback_data=f"ai_page:{lid}:{i - 1}"))
    if i < len(pages) - 1:
        nav.append(InlineKeyboardButton(text="التالية ➡️", callback_data=f"ai_page:{lid}:{i + 1}"))
    if nav:
        rows.append(nav)
    if i == len(pages) - 1:
        rows.append([InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"ai_quiz:{lid}")])
    rows.append([InlineKeyboardButton(text="⬅️ قائمة الدرس", callback_data=f"ai_lessonback:{lid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
