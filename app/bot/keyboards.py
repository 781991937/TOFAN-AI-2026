import hashlib
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _enc(value: str) -> str:
    """Create a short Telegram-safe token for callback_data."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 قسم الذكاء", callback_data="ai_section")],
        [InlineKeyboardButton(text="🤖 قسم البوت", callback_data="automation_section")],
        [InlineKeyboardButton(text="⚙️ إعدادات البوت", callback_data="settings")],
        [InlineKeyboardButton(text="❓ المساعدة", callback_data="help")],
    ])


def ai_actions_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 شرح ذكي", callback_data="ai_pick:explain")],
        [InlineKeyboardButton(text="🧠 اختبار ذكي", callback_data="ai_pick:quiz")],
        [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])


def ai_categories_menu(categories: list, action: str) -> InlineKeyboardMarkup:
    rows = []
    for row in categories:
        category = str(row["category"])
        count = int(row["lesson_count"])
        rows.append([InlineKeyboardButton(
            text=f"{category}  ({count} درس)",
            callback_data=f"ai_category:{action}:{_enc(category)}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ قسم الذكاء", callback_data="ai_section")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_files_menu(files: list, action: str) -> InlineKeyboardMarkup:
    rows = []
    for key, name, count in files:
        rows.append([InlineKeyboardButton(
            text=f"📘 {name}  ({count} درس)",
            callback_data=f"ai_file:{action}:{_enc(key)}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ المواد", callback_data=f"ai_pick:{action}")])
    rows.append([InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_lessons_menu(lessons: list, action: str) -> InlineKeyboardMarkup:
    rows = []
    for number, lesson in enumerate(lessons, start=1):
        title = str(lesson["file_name"] or f"الدرس {number}")
        if " - " in title:
            title = title.split(" - ", 1)[1]
        if len(title) > 38:
            title = title[:35] + "..."
        rows.append([InlineKeyboardButton(
            text=f"📖 الدرس {number}: {title}",
            callback_data=f"ai_lesson:{action}:{int(lesson['id'])}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ المواد", callback_data=f"ai_pick:{action}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lesson_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 شرح ذكي", callback_data=f"smart_explain:{lesson_id}")],
        [InlineKeyboardButton(text="📝 اختبار الدرس", callback_data=f"filequiz:{lesson_id}")],
        [InlineKeyboardButton(text="📖 صفحات الدرس", callback_data=f"pages:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ الدرس السابق", callback_data=f"prevlesson:{lesson_id}"), InlineKeyboardButton(text="الدرس التالي ➡️", callback_data=f"nextlesson:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ دروس الملف", callback_data=f"fileback:{lesson_id}")],
    ])


def delete_lesson_confirm(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ نعم، احذف الملف", callback_data=f"confirm_delete:{lesson_id}")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"lesson:{lesson_id}")],
    ])


def lessons_list_menu(lessons: list) -> InlineKeyboardMarkup:
    rows = []
    grouped = {}
    for lesson in lessons:
        category = str(lesson["category"] or "📂 مواد أخرى")
        grouped[category] = grouped.get(category, 0) + 1
    for category, count in grouped.items():
        rows.append([InlineKeyboardButton(text=f"{category}  ({count})", callback_data=f"category:{_enc(category)}")])
    rows.append([InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def library_menu(categories: list) -> InlineKeyboardMarkup:
    rows = []
    for row in categories:
        category = str(row["category"])
        count = int(row["lesson_count"])
        rows.append([InlineKeyboardButton(text=f"{category}  ({count} درس)", callback_data=f"category:{_enc(category)}")])
    rows.append([InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_menu(category: str, lessons: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 ملفات القسم", callback_data=f"categoryfiles:{_enc(category)}")],
        [InlineKeyboardButton(text="🎓 اختبار ملفات القسم — 50 سؤال", callback_data=f"categoryquiz:{_enc(category)}")],
        [InlineKeyboardButton(text="⬅️ المكتبة", callback_data="library")],
    ])


def file_list_menu(lessons: list, category: str) -> InlineKeyboardMarkup:
    """Show original files, not every split lesson as if it were a file."""
    grouped = {}
    for lesson in lessons:
        key = str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])
        if key not in grouped:
            grouped[key] = {"name": str(lesson["file_name"]), "count": 0}
        grouped[key]["count"] += 1

    rows = []
    for key, item in grouped.items():
        name = item["name"]
        if " - " in name:
            name = name.split(" - ", 1)[0]
        if len(name) > 40:
            name = name[:37] + "..."
        rows.append([InlineKeyboardButton(
            text=f"📘 {name}  ({item['count']} درس)",
            callback_data=f"file:{_enc(key)}",
        )])
    rows.append([InlineKeyboardButton(text="🎓 اختبار القسم — 50 سؤال", callback_data=f"categoryquiz:{_enc(category)}")])
    rows.append([InlineKeyboardButton(text="⬅️ القسم", callback_data=f"category:{_enc(category)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lesson_list_menu(lessons: list, file_key: str) -> InlineKeyboardMarkup:
    rows = []
    for number, lesson in enumerate(lessons, start=1):
        title = str(lesson["file_name"] or f"الدرس {number}")
        if " - " in title:
            title = title.split(" - ", 1)[1]
        if len(title) > 40:
            title = title[:37] + "..."
        rows.append([InlineKeyboardButton(text=f"📖 الدرس {number}: {title}", callback_data=f"lesson:{int(lesson['id'])}")])
    rows.append([InlineKeyboardButton(text="⬅️ الملفات", callback_data="categoryfiles:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lesson_actions_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return lesson_menu(lesson_id)


def group_quiz_menu(quiz_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 انضم للاختبار الجماعي", callback_data=f"join:{quiz_id}")],
        [InlineKeyboardButton(text="🏆 لوحة المتصدرين", callback_data=f"leaderboard:{quiz_id}")],
    ])


def result_menu(lesson_id: int, group: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🔁 اختبار جديد", callback_data=f"filequiz:{lesson_id}")], [InlineKeyboardButton(text="⬅️ رجوع للدرس", callback_data=f"lesson:{lesson_id}")]]
    if group:
        rows.insert(1, [InlineKeyboardButton(text="👥 اختبار جماعي جديد", callback_data=f"groupquiz:{lesson_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_menu(count: int, difficulty: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"عدد الأسئلة: {count}", callback_data="set_count")],
        [InlineKeyboardButton(text=f"الصعوبة: {difficulty}", callback_data="set_difficulty")],
        [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])


def count_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5", callback_data="count:5"), InlineKeyboardButton(text="10", callback_data="count:10"), InlineKeyboardButton(text="15", callback_data="count:15")],
        [InlineKeyboardButton(text="20", callback_data="count:20"), InlineKeyboardButton(text="30", callback_data="count:30")],
    ])


def difficulty_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 سهل", callback_data="difficulty:easy"), InlineKeyboardButton(text="🟡 متوسط", callback_data="difficulty:medium")],
        [InlineKeyboardButton(text="🔴 صعب", callback_data="difficulty:hard")],
    ])
