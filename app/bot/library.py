"""Shared deterministic library helpers.

No Telegram handlers live here. Domain-specific routers are in
bot_library_isolation.py (Bot/Automation) and sections.py (AI).
"""

import hashlib
import json
from pathlib import Path

from aiogram import Router

from app.services.file_extractor import split_lessons

router = Router(name="library_compat")


def token(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _field(lesson, name: str, default=""):
    try:
        return lesson[name]
    except (KeyError, IndexError, TypeError):
        return lesson.get(name, default) if hasattr(lesson, "get") else default


def classify_lesson(lesson) -> str:
    name = str(_field(lesson, "file_name", "")).casefold()
    text = str(_field(lesson, "extracted_text", ""))[:16000].casefold()
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


def _key(lesson) -> str:
    return str(_field(lesson, "file_id", "") or _field(lesson, "file_path", "") or _field(lesson, "file_name", ""))


def _auto_split_file(db, lessons: list) -> bool:
    """Repair a legacy one-row upload when its extracted text contains multiple lessons."""
    changed = False
    groups: dict[str, list] = {}
    for lesson in lessons:
        groups.setdefault(_key(lesson), []).append(lesson)

    for _key_value, rows in groups.items():
        if len(rows) != 1:
            continue
        lesson = rows[0]
        parts = split_lessons(str(_field(lesson, "extracted_text", "") or ""))
        if len(parts) <= 1:
            continue

        source_name = str(_field(lesson, "file_name", "الملف") or "الملف")
        suffix = Path(source_name).suffix
        stem = Path(source_name).stem
        category = str(_field(lesson, "category", "") or classify_lesson(lesson))

        first_title, first_text = parts[0]
        first_name = f"{stem} - {first_title}{suffix}"
        db.update_lesson_text_and_name(int(lesson["id"]), first_name, first_text, category)

        for number, (title, body) in enumerate(parts[1:], 2):
            body = str(body).strip()
            if len(body) < 20:
                continue
            name = f"{stem} - {title or f'الدرس {number}'}{suffix}"
            new_id = db.create_lesson(
                int(lesson["telegram_id"]),
                name,
                str(_field(lesson, "file_type", "") or suffix.lstrip(".") or "txt"),
                str(_field(lesson, "file_path", "") or ""),
                body,
                category=category,
                file_id=str(_field(lesson, "file_id", "") or ""),
            )
            db.update_lesson_analysis(new_id, "", json.dumps([], ensure_ascii=False), "")
        changed = True

    return changed


def sync_categories(db, user_id: int) -> list:
    """Repair old categories and old one-row multi-lesson uploads before opening a domain."""
    lessons = db.get_lessons(user_id, 1000)
    _auto_split_file(db, lessons)
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
        key = _key(lesson)
        grouped.setdefault(key, [str(_field(lesson, "file_name", "الملف") or "الملف"), 0])[1] += 1
    return [(key, name, count) for key, (name, count) in grouped.items()]


def find_file(lessons: list, file_token: str):
    for lesson in lessons:
        key = _key(lesson)
        if token(key) == file_token:
            return key
    return None


def file_lessons(lessons: list, key: str):
    return [x for x in lessons if _key(x) == key]
