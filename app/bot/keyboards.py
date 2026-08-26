import hashlib
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _enc(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _rows(buttons, width: int = 2):
    return [buttons[i:i + width] for i in range(0, len(buttons), width)]


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 قسم الذكاء الاصطناعي", callback_data="ai_section"), InlineKeyboardButton(text="🤖 قسم البوت", callback_data="bot_section")],
        [InlineKeyboardButton(text="⚙️ إعدادات البوت", callback_data="settings"), InlineKeyboardButton(text="❓ المساعدة", callback_data="help")],
    ])


def section_menu(section: str) -> InlineKeyboardMarkup:
    library_cb = "ai_library" if section == "ai" else "bot_library"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 المكتبة", callback_data=library_cb), InlineKeyboardButton(text="📥 إدارة الملفات", callback_data="file_management")],
        [InlineKeyboardButton(text="🧭 الصفحات والتنقل", callback_data="navigation_help"), InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])


def ai_categories_menu(categories: list) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=f"{str(row['category'])} ({int(row['lesson_count'])})", callback_data=f"ai_category:{_enc(str(row['category']))}") for row in categories]
    rows = _rows(buttons); rows.append([InlineKeyboardButton(text="⬅️ قسم الذكاء", callback_data="ai_section")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bot_categories_menu(categories: list) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=f"{str(row['category'])} ({int(row['lesson_count'])})", callback_data=f"bot_category:{_enc(str(row['category']))}") for row in categories]
    rows = _rows(buttons); rows.append([InlineKeyboardButton(text="⬅️ قسم البوت", callback_data="bot_section")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_category_menu(category: str) -> InlineKeyboardMarkup:
    token = _enc(category)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 ملفات القسم", callback_data=f"ai_categoryfiles:{token}"), InlineKeyboardButton(text="🎓 اختبار القسم كامل", callback_data=f"ai_categoryquiz:{token}")],
        [InlineKeyboardButton(text="⬅️ المكتبة", callback_data="ai_library")],
    ])


def ai_files_menu(files: list, category: str) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=f"📘 {name} ({count})", callback_data=f"ai_file:{_enc(key)}") for key, name, count in files]
    rows = _rows(buttons); rows.append([InlineKeyboardButton(text="⬅️ القسم", callback_data=f"ai_category:{_enc(category)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_lessons_menu(lessons: list, file_key: str) -> InlineKeyboardMarkup:
    buttons = []
    for number, lesson in enumerate(lessons, 1):
        title = str(lesson["file_name"] or f"الدرس {number}")
        if " - " in title: title = title.split(" - ", 1)[1]
        if len(title) > 25: title = title[:22] + "..."
        buttons.append(InlineKeyboardButton(text=f"📖 {number}: {title}", callback_data=f"ai_lesson:{int(lesson['id'])}:{_enc(file_key)}"))
    rows = _rows(buttons); rows.append([InlineKeyboardButton(text="⬅️ الملفات", callback_data=f"ai_fileback:{_enc(file_key)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_lesson_menu(lesson_id: int, file_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 شرح ذكي", callback_data=f"ai_explain:{lesson_id}"), InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"ai_quiz:{lesson_id}")],
        [InlineKeyboardButton(text="📖 صفحات الدرس", callback_data=f"ai_pages:{lesson_id}"), InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ الملف السابق", callback_data=f"prevfile:{lesson_id}"), InlineKeyboardButton(text="الملف التالي ➡️", callback_data=f"nextfile:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ دروس الملف", callback_data=f"ai_fileback:{_enc(file_key)}")],
    ])


def automation_lesson_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 صفحات الدرس", callback_data=f"pages:{lesson_id}"), InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ الملف السابق", callback_data=f"prevfile:{lesson_id}"), InlineKeyboardButton(text="الملف التالي ➡️", callback_data=f"nextfile:{lesson_id}")],
        [InlineKeyboardButton(text="🗑️ حذف الملف", callback_data=f"delete_lesson:{lesson_id}"), InlineKeyboardButton(text="⬅️ المكتبة", callback_data="bot_library")],
    ])


def lesson_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return automation_lesson_menu(lesson_id)


def delete_lesson_confirm(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑️ نعم، احذف الملف", callback_data=f"confirm_delete:{lesson_id}"), InlineKeyboardButton(text="❌ إلغاء", callback_data=f"lesson:{lesson_id}")]])


def file_list_menu(lessons: list, category: str) -> InlineKeyboardMarkup:
    grouped = {}
    for lesson in lessons:
        key = str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])
        grouped.setdefault(key, {"name": str(lesson["file_name"]), "count": 0})["count"] += 1
    buttons = []
    for key, item in grouped.items():
        name = item["name"][:25] + "..." if len(item["name"]) > 28 else item["name"]
        buttons.append(InlineKeyboardButton(text=f"📘 {name} ({item['count']})", callback_data=f"bot_file:{_enc(key)}"))
    rows = _rows(buttons); rows.append([InlineKeyboardButton(text="⬅️ الأقسام", callback_data="bot_library")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bot_lesson_list(lessons: list, file_key: str) -> InlineKeyboardMarkup:
    buttons = []
    for number, lesson in enumerate(lessons, 1):
        title = str(lesson["file_name"] or f"الدرس {number}")
        if " - " in title: title = title.split(" - ", 1)[1]
        if len(title) > 25: title = title[:22] + "..."
        buttons.append(InlineKeyboardButton(text=f"📖 {number}: {title}", callback_data=f"bot_lesson:{int(lesson['id'])}:{_enc(file_key)}"))
    rows = _rows(buttons); rows.append([InlineKeyboardButton(text="⬅️ الملفات", callback_data=f"bot_fileback:{_enc(file_key)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def result_menu(lesson_id: int, group: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔁 اختبار جديد", callback_data=f"ai_quiz:{lesson_id}"), InlineKeyboardButton(text="⬅️ رجوع للدرس", callback_data=f"ai_lessonback:{lesson_id}")]])


def settings_menu(count: int, difficulty: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"عدد الأسئلة: {count}", callback_data="set_count"), InlineKeyboardButton(text=f"الصعوبة: {difficulty}", callback_data="set_difficulty")], [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")]])


def count_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=_rows([InlineKeyboardButton(text=str(n), callback_data=f"count:{n}") for n in (5, 10, 15, 20, 30)]))


def difficulty_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🟢 سهل", callback_data="difficulty:easy"), InlineKeyboardButton(text="🟡 متوسط", callback_data="difficulty:medium")], [InlineKeyboardButton(text="🔴 صعب", callback_data="difficulty:hard")]])
