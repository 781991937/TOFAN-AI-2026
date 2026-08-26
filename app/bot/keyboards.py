import hashlib
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _enc(value: str) -> str:
    """Create a short Telegram-safe category token (always far below 64 bytes)."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 المكتبة", callback_data="library"), InlineKeyboardButton(text="👤 ملفي", callback_data="profile")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="settings"), InlineKeyboardButton(text="❓ المساعدة", callback_data="help")],
    ])


def lesson_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 اختبار الملف", callback_data=f"filequiz:{lesson_id}")],
        [InlineKeyboardButton(text="🔁 اختبار جديد", callback_data=f"filequiz:{lesson_id}")],
        [InlineKeyboardButton(text="👥 اختبار جماعي", callback_data=f"groupquiz:{lesson_id}")],
        [InlineKeyboardButton(text="📖 شرح صفحة بصفحة", callback_data=f"pages:{lesson_id}")],
        [InlineKeyboardButton(text="🧠 شرح ذكي", callback_data=f"smart_explain:{lesson_id}")],
        [InlineKeyboardButton(text="🧠 اختبار ذكي", callback_data=f"smart_quiz:{lesson_id}")],
        [InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ الملف السابق", callback_data=f"prevlesson:{lesson_id}"), InlineKeyboardButton(text="الملف التالي ➡️", callback_data=f"nextlesson:{lesson_id}")],
        [InlineKeyboardButton(text="🗑️ حذف الملف", callback_data=f"delete_lesson:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ رجوع للمكتبة", callback_data="library")],
        [InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")],
    ])


def delete_lesson_confirm(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ نعم، احذف الملف", callback_data=f"confirm_delete:{lesson_id}")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="library")],
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
        rows.append([InlineKeyboardButton(text=f"{category}  ({count} ملف)", callback_data=f"category:{_enc(category)}")])
    rows.append([InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_menu(category: str, lessons: list) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🎓 اختبار شامل للقسم — 50 سؤال", callback_data=f"categoryquiz:{_enc(category)}")]]
    rows.append([InlineKeyboardButton(text="📂 عرض ملفات القسم", callback_data=f"categoryfiles:{_enc(category)}")])
    rows.append([InlineKeyboardButton(text="⬅️ رجوع للمكتبة", callback_data="library")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def file_list_menu(lessons: list, category: str) -> InlineKeyboardMarkup:
    rows = []
    for lesson in lessons:
        lesson_id = int(lesson["id"])
        name = str(lesson["file_name"])
        if len(name) > 35:
            name = name[:32] + "..."
        rows.append([InlineKeyboardButton(text=f"📘 {name}", callback_data=f"lesson:{lesson_id}")])
    rows.append([InlineKeyboardButton(text="🎓 اختبار القسم — 50 سؤال", callback_data=f"categoryquiz:{_enc(category)}")])
    rows.append([InlineKeyboardButton(text="⬅️ رجوع للقسم", callback_data=f"category:{_enc(category)}")])
    rows.append([InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lesson_actions_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return lesson_menu(lesson_id)


def group_quiz_menu(quiz_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 انضم للاختبار الجماعي", callback_data=f"join:{quiz_id}")],
        [InlineKeyboardButton(text="🏆 لوحة المتصدرين", callback_data=f"leaderboard:{quiz_id}")],
    ])


def result_menu(lesson_id: int, group: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔁 اختبار جديد", callback_data=f"filequiz:{lesson_id}")],
        [InlineKeyboardButton(text="🧠 اختبار ذكي", callback_data=f"smart_quiz:{lesson_id}")],
        [InlineKeyboardButton(text="📖 شرح صفحة بصفحة", callback_data=f"pages:{lesson_id}")],
        [InlineKeyboardButton(text="📥 تنزيل الملف", callback_data=f"download:{lesson_id}")],
        [InlineKeyboardButton(text="⬅️ رجوع للدرس", callback_data=f"lesson:{lesson_id}")],
    ]
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
