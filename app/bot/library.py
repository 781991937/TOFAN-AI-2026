import hashlib
import html

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.keyboards import bot_categories_menu, file_list_menu, bot_lesson_list, lesson_menu
from app.database import Database

router = Router(name="library")


def token(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def classify_lesson(lesson) -> str:
    name = str(lesson.get("file_name", "")).casefold()
    text = str(lesson.get("extracted_text", ""))[:16000].casefold()
    source = f"{name}\n{text}"
    rules = [
        ("🤖 مقدمة الذكاء الاصطناعي", ["artificial intelligence", "الذكاء الاصطناعي", "intelligent agent", "intelligent agents", "الوكلاء الأذكياء", "peas", "turing test", "اختبار تورينغ", "state space", "problem solving", "knowledge representation"]),
        ("🗣 مهارات الاتصال", ["communication skills", "مهارات الاتصال", "communication", "التواصل", "listening", "الاستماع", "presentation", "verbal", "nonverbal", "الاتصال اللفظي", "الاتصال غير اللفظي"]),
        ("💻 البرمجة", ["python", "programming", "البرمجة", "algorithm", "الخوارزمية", "variable", "variables", "loop", "function", "functions", "code"]),
        ("🇬🇧 اللغة الإنجليزية", ["english", "grammar", "vocabulary", "present simple", "tense", "adjective", "verb", "noun"]),
        ("📐 الرياضيات", ["discrete mathematics", "discrete math", "رياضيات منفصلة", "logic", "truth table", "set theory", "probability"]),
        ("🖥 مهارات الحاسوب", ["computer skills", "مهارات الحاسوب", "microsoft word", "excel", "powerpoint", "windows", "الحاسوب"]),
    ]
    score, category = max((sum(source.count(k) for k in keys), category) for category, keys in rules)
    return category if score else "📂 مواد أخرى"


def prepare_categories(db: Database, user_id: int):
    lessons = db.get_lessons(user_id, 1000)
    for lesson in lessons:
        category = classify_lesson(lesson)
        if str(lesson["category"] or "") != category:
            db.update_lesson_category(int(lesson["id"]), category)
    return db.get_categories(user_id)


def files_in_category(lessons: list):
    grouped = {}
    for lesson in lessons:
        key = str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])
        grouped.setdefault(key, [str(lesson["file_name"] or "الملف"), 0])[1] += 1
    return [(key, name, count) for key, (name, count) in grouped.items()]


def find_file(lessons: list, file_token: str):
    for lesson in lessons:
        key = str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])
        if token(key) == file_token:
            return key
    return None


def file_lessons(lessons: list, key: str):
    return [x for x in lessons if str(x["file_id"] or x["file_path"] or x["file_name"]) == key]


def decode_category(db: Database, user_id: int, value: str):
    for row in db.get_categories(user_id):
        category = str(row["category"])
        if token(category) == value:
            return category
    return None


@router.callback_query(F.data == "bot_library")
async def bot_library(callback: CallbackQuery, db: Database):
    categories = prepare_categories(db, callback.from_user.id)
    await callback.answer()
    if not categories:
        await callback.message.edit_text("📚 <b>المكتبة فارغة</b>\n\nأرسل أي ملف وسأكتشف مادته وأرتبه تلقائيًا.")
        return
    await callback.message.edit_text("🤖 <b>مكتبة قسم البوت</b>\n\nاختر القسم:", reply_markup=bot_categories_menu(categories))


@router.callback_query(F.data.startswith("bot_category:"))
async def bot_category(callback: CallbackQuery, db: Database):
    category = decode_category(db, callback.from_user.id, callback.data.split(":", 1)[1])
    await callback.answer()
    if not category:
        await callback.message.edit_text("❌ القسم غير موجود."); return
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    await callback.message.edit_text(f"🤖 <b>{html.escape(category)}</b>\n\nاختر الملف:", reply_markup=file_list_menu(lessons, category))


@router.callback_query(F.data.startswith("bot_file:"))
async def bot_file(callback: CallbackQuery, db: Database):
    all_lessons = db.get_lessons(callback.from_user.id, 1000)
    key = find_file(all_lessons, callback.data.split(":", 1)[1])
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود."); return
    selected = file_lessons(all_lessons, key)
    await callback.message.edit_text(
        f"🤖 <b>قسم البوت والأتمتة</b>\n📚 <b>{html.escape(str(selected[0]['category'] or '📂 مواد أخرى'))}</b>\n📘 <b>{html.escape(str(selected[0]['file_name']))}</b>\n\nاختر الدرس:",
        reply_markup=bot_lesson_list(selected, key),
    )


@router.callback_query(F.data.startswith("bot_fileback:"))
async def bot_fileback(callback: CallbackQuery, db: Database):
    all_lessons = db.get_lessons(callback.from_user.id, 1000)
    key = find_file(all_lessons, callback.data.split(":", 1)[1])
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود."); return
    selected = file_lessons(all_lessons, key)
    category = str(selected[0]["category"] or "📂 مواد أخرى")
    await callback.message.edit_text(f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:", reply_markup=file_list_menu(db.get_lessons_by_category(callback.from_user.id, category), category))


@router.callback_query(F.data.startswith("bot_lesson:"))
async def bot_lesson(callback: CallbackQuery, db: Database):
    _, lesson_id, file_token = callback.data.split(":", 2)
    lesson = db.get_lesson(int(lesson_id), callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text("❌ الدرس غير موجود."); return
    all_lessons = db.get_lessons(callback.from_user.id, 1000)
    key = str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])
    selected = file_lessons(all_lessons, key)
    number = next((i + 1 for i, x in enumerate(selected) if int(x["id"]) == int(lesson_id)), 1)
    await callback.message.edit_text(
        f"📖 <b>{html.escape(str(lesson['file_name']))}</b>\n"
        f"🔢 <b>الدرس {number} من {len(selected)}</b>\n"
        f"📚 <b>القسم:</b> {html.escape(str(lesson['category'] or '📂 مواد أخرى'))}\n\n"
        "⚙️ <b>طريقة العمل: البوت والأتمتة — Python</b>\n\nاختر الوظيفة:",
        reply_markup=lesson_menu(int(lesson_id)),
    )
