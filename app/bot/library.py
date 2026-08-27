"""Shared deterministic library helpers.

No Telegram handlers live here. Domain-specific routers are in
bot_library_isolation.py (Bot/Automation) and sections.py (AI).
"""

import hashlib

from aiogram import Router

router = Router(name="library_compat")


def token(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def classify_lesson(lesson) -> str:
    name = str(lesson.get("file_name", "")).casefold()
    text = str(lesson.get("extracted_text", ""))[:16000].casefold()
    source = f"{name}\n{text}"
    rules = [
        ("🤖 مقدمة الذكاء الاصطناعي", ["artificial intelligence", "الذكاء الاصطناعي", "intelligent agent", "intelligent agents", "الوكلاء الأذكياء", "peas", "turing test", "اختبار تورينغ", "state space", "problem solving", "knowledge representation"]),
        ("🗣 مهارات الاتصال", ["communication skills", "مهارات الاتصال", "communication", "التواصل", "listening", "الاستماع", "presentation", "verbal", "nonverbal"]),
        ("💻 البرمجة", ["python", "programming", "البرمجة", "algorithm", "الخوارزمية", "variable", "variables", "loop", "function", "functions", "code"]),
        ("🇬🇧 اللغة الإنجليزية", ["english", "grammar", "vocabulary", "present simple", "tense", "adjective", "verb", "noun"]),
        ("📐 الرياضيات", ["discrete mathematics", "discrete math", "رياضيات منفصلة", "logic", "truth table", "set theory", "probability"]),
        ("🖥 مهارات الحاسوب", ["computer skills", "مهارات الحاسوب", "microsoft word", "excel", "powerpoint", "windows", "الحاسوب"]),
    ]
    score, category = max((sum(source.count(k) for k in keys), category) for category, keys in rules)
    return category if score else "📂 مواد أخرى"


def sync_categories(db, user_id: int) -> list:
    """Repair categories of old uploads deterministically before a domain opens."""
    lessons = db.get_lessons(user_id, 1000)
    for lesson in lessons:
        category = classify_lesson(lesson)
        if str(lesson["category"] or "") != category:
            db.update_lesson_category(int(lesson["id"]), category)
    return db.get_lessons(user_id, 1000)


def prepare_categories(db, user_id: int):
    """Compatibility helper used by the AI quiz adapter; never renders UI."""
    sync_categories(db, user_id)
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
