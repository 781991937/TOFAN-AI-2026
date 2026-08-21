from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 دروسي", callback_data="lessons"), InlineKeyboardButton(text="👤 ملفي", callback_data="profile")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="settings"), InlineKeyboardButton(text="❓ المساعدة", callback_data="help")],
    ])


def lesson_menu(lesson_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 إنشاء اختبار", callback_data=f"quiz:{lesson_id}")],
        [InlineKeyboardButton(text="📖 الملخص", callback_data=f"summary:{lesson_id}")],
    ])


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
