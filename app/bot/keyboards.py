import hashlib
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _enc(value: str) -> str:
    """Create a short Telegram-safe token for callback_data."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _pair_rows(buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 قسم الذكاء", callback_data="ai_section"), InlineKeyboardButton(text="🤖 قسم البوت", callback_data="automation_section")],
        [InlineKeyboardButton(text="⚙️ إعدادات البوت", callback_data="settings"), InlineKeyboardButton(text="❓ المساعدة", callback_data="help")],
    ])


def section_menu(section: str) -> InlineKeyboardMarkup:
    prefix = "ai" if section == "ai" else "bot"
    library_callback = "ai_library" if section == "ai" else "library"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 المكتبة", callback_data=library_callback), InlineKeyboardButton(text="📥 إدارة الملفات", callback_data="file_management")],
        [InlineKeyboardButton(text="🧭 الصفحات والتنقل", callback_data="navigation_help"), InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])


def ai_categories_menu(categories: list) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=f"{str(row['category'])} ({int(row['lesson_count'])})",
            callback_data=f"ai_category:{_enc(str(row['category']))}",
        )
        for row in categories
    ]
    rows = _pair_rows(buttons)
    rows.append([InlineKeyboardButton(text="⬅️ قسم الذكاء", callback_data="ai_section")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_category_menu(category: str) -> InlineKeyboardMarkup:
    token = _enc(category)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 ملفات القسم", callback_data=f"ai_categoryfiles:{token}"), InlineKeyboardButton(text="🎓 اختبار القسم كامل", callback_data=f"ai_categoryquiz:{token}")],
        [InlineKeyboardButton(text="⬅️ المكتبة", callback_data="ai_library")],
    ])


def ai_files_menu(files: list, category: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"📘 {name} ({count})", callback_data=f"ai_file:{_enc(key)}")
        for key, name, count in files
    ]
    rows = _pair_rows(buttons)
    rows.append([InlineKeyboardButton(text="⬅️ القسم", callback_data=f"ai_category:{_enc(category)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_lessons_menu(lessons: list, file_key: str) -> InlineKeyboardMarkup:
    buttons = []
    for number, lesson in enumerate(lessons, start=1):
        title = str(lesson["file_name"] or f"الدرس {number}")
        if " - " in title:
            title = title.split(" - ", 1)[1]
        if len(title) > 28:
            title = title[:25] + "..."
        buttons.append(InlineKeyboardButton(text=f"📖 {number}: {title}", callback_data=f"ai_lesson:{int(lesson['id'])}:{_enc(file_key)}"))
    rows = _pair_rows(buttons)
    rows.append([InlineKeyboardButton(text="⬅️ الملفات", callback_data=f"ai_fileback:{_enc(file_key)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def automation_lesson_menu(lesson_id: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text="📖 صفحات الدرس", callback_data=f"pages:{lesson_id}"),
        InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lesson_id}"),
        InlineKeyboardButton(text="🗑️ حذف الملف", callback_data=f"delete_lesson:{lesson_id}"),
    ]
    rows = _pair_rows(buttons)
    rows.append([
        InlineKeyboardButton(text="⬅️ الدرس السابق", callback_data=f"prevlesson:{lesson_id}"),
        InlineKeyboardButton(text="الدرس التالي ➡️", callback_data=f"nextlesson:{lesson_id}"),
    ])
    rows.append([InlineKeyboardButton(text="⬅️ دروس الملف", callback_data=f"fileback:{lesson_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_lesson_menu(lesson_id: int, file_key: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text="🧠 شرح ذكي", callback_data=f"ai_explain:{lesson_id}"),
        InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"ai_quiz:{lesson_id}"),
        InlineKeyboardButton(text="📖 صفحات الدرس", callback_data=f"pages:{lesson_id}"),
        InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lesson_id}"),
        InlineKeyboardButton(text="🗑️ حذف الملف", callback_data=f"delete_lesson:{lesson_id}"),
    ]
    rows = _pair_rows(buttons)
    rows.append([
        InlineKeyboardButton(text="⬅️ الدرس السابق", callback_data=f"prevlesson:{lesson_id}"),
        InlineKeyboardButton(text="الدرس التالي ➡️", callback_data=f"nextlesson:{lesson_id}"),
    ])
    rows.append([InlineKeyboardButton(text="⬅️ دروس الملف", callback_data=f"ai_fileback:{_enc(file_key)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lesson_menu(lesson_id: int) -> InlineKeyboardMarkup:
    """Compatibility alias: automation menu only, never exposes AI actions."""
    return automation_lesson_menu(lesson_id)


def delete_lesson_confirm(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ نعم، احذف الملف", callback_data=f"confirm_delete:{lesson_id}"), InlineKeyboardButton(text="❌ إلغاء", callback_data=f"lesson:{lesson_id}")],
    ])


def lessons_list_menu(lessons: list) -> InlineKeyboardMarkup:
    grouped = {}
    for lesson in lessons:
        category = str(lesson["category"] or "📂 مواد أخرى")
        grouped[category] = grouped.get(category, 0) + 1
    buttons = [InlineKeyboardButton(text=f"{category} ({count})", callback_data=f"category:{_enc(category)}") for category, count in grouped.items()]
    rows = _pair_rows(buttons)
    rows.append([InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def library_menu(categories: list) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{str(row['category'])} ({int(row['lesson_count'])})", callback_data=f"category:{_enc(str(row['category']))}")
        for row in categories
    ]
    rows = _pair_rows(buttons)
    rows.append([InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_menu(category: str, lessons: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 ملفات القسم", callback_data=f"categoryfiles:{_enc(category)}")],
        [InlineKeyboardButton(text="⬅️ المكتبة", callback_data="library")],
    ])


def file_list_menu(lessons: list, category: str) -> InlineKeyboardMarkup:
    grouped = {}
    for lesson in lessons:
        key = str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])
        if key not in grouped:
            grouped[key] = {"name": str(lesson["file_name"]), "count": 0}
        grouped[key]["count"] += 1
    buttons = []
    for key, item in grouped.items():
        name = item["name"]
        if " - " in name:
            name = name.split(" - ", 1)[0]
        if len(name) > 30:
            name = name[:27] + "..."
        buttons.append(InlineKeyboardButton(text=f"📘 {name} ({item['count']})", callback_data=f"file:{_enc(key)}"))
    rows = _pair_rows(buttons)
    rows.append([InlineKeyboardButton(text="⬅️ القسم", callback_data=f"category:{_enc(category)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lesson_list_menu(lessons: list, file_key: str) -> InlineKeyboardMarkup:
    buttons = []
    for number, lesson in enumerate(lessons, start=1):
        title = str(lesson["file_name"] or f"الدرس {number}")
        if " - " in title:
            title = title.split(" - ", 1)[1]
        if len(title) > 30:
            title = title[:27] + "..."
        buttons.append(InlineKeyboardButton(text=f"📖 {number}: {title}", callback_data=f"lesson:{int(lesson['id'])}"))
    rows = _pair_rows(buttons)
    rows.append([InlineKeyboardButton(text="⬅️ الملفات", callback_data=f"fileback:{_enc(file_key)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lesson_actions_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return automation_lesson_menu(lesson_id)


def group_quiz_menu(quiz_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 انضم للاختبار الجماعي", callback_data=f"join:{quiz_id}"), InlineKeyboardButton(text="🏆 المتصدرين", callback_data=f"leaderboard:{quiz_id}")],
    ])


def result_menu(lesson_id: int, group: bool = False) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text="🔁 اختبار جديد", callback_data=f"filequiz:{lesson_id}"), InlineKeyboardButton(text="⬅️ رجوع للدرس", callback_data=f"lesson:{lesson_id}")]
    if group:
        buttons.append(InlineKeyboardButton(text="👥 اختبار جماعي جديد", callback_data=f"groupquiz:{lesson_id}"))
    return InlineKeyboardMarkup(inline_keyboard=_pair_rows(buttons))


def settings_menu(count: int, difficulty: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"عدد الأسئلة: {count}", callback_data="set_count"), InlineKeyboardButton(text=f"الصعوبة: {difficulty}", callback_data="set_difficulty")],
        [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])


def count_menu() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=str(n), callback_data=f"count:{n}") for n in (5, 10, 15, 20, 30)]
    return InlineKeyboardMarkup(inline_keyboard=_pair_rows(buttons))


def difficulty_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 سهل", callback_data="difficulty:easy"), InlineKeyboardButton(text="🟡 متوسط", callback_data="difficulty:medium")],
        [InlineKeyboardButton(text="🔴 صعب", callback_data="difficulty:hard")],
    ])
