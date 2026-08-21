from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 دروسي", callback_data="lessons"), InlineKeyboardButton(text="👤 ملفي", callback_data="profile")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="settings"), InlineKeyboardButton(text="❓ المساعدة", callback_data="help")],
    ])


def lesson_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 اختبار جديد", callback_data=f"quiz:{lesson_id}"), InlineKeyboardButton(text="🔁 إعادة الاختبار", callback_data=f"repeat:{lesson_id}")],
        [InlineKeyboardButton(text="👥 اختبار جماعي", callback_data=f"groupquiz:{lesson_id}")],
        [InlineKeyboardButton(text="📖 شرح الدرس", callback_data=f"explain:{lesson_id}")],
    ])


def lessons_list_menu(lessons: list) -> InlineKeyboardMarkup:
    rows = []
    for lesson in lessons:
        lesson_id = int(lesson["id"])
        name = str(lesson["file_name"])
        if len(name) > 28:
            name = name[:25] + "..."
        rows.append([InlineKeyboardButton(text=f"📘 {name}", callback_data=f"lesson:{lesson_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")])
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
        [InlineKeyboardButton(text="🔁 إعادة الاختبار", callback_data=f"repeat:{lesson_id}")],
        [InlineKeyboardButton(text="📝 اختبار جديد", callback_data=f"quiz:{lesson_id}")],
    ]
    if group:
        rows.append([InlineKeyboardButton(text="👥 اختبار جماعي جديد", callback_data=f"groupquiz:{lesson_id}")])
    rows.append([InlineKeyboardButton(text="📖 شرح الدرس", callback_data=f"explain:{lesson_id}")])
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
