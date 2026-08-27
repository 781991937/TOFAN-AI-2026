"""Top-level AI section router.

Only the AI domain lives here. Page navigation is delegated to ai_pages.py;
the Bot/Automation domain has its own isolated routers.
"""

import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.keyboards import ai_categories_menu, ai_category_menu, ai_files_menu, ai_lessons_menu, ai_lesson_menu, section_menu
from app.bot.library import file_lessons, find_file, token
from app.bot.quiz_engine import QuizState, send_question
from app.database import Database
from app.services import AIService, QuizGenerator

logger = logging.getLogger(__name__)
router = Router(name="ai_section")


def _is_ai_category(category: str) -> bool:
    value = str(category or "").casefold()
    return "الذكاء الاصطناعي" in value or "artificial intelligence" in value or "intelligent agent" in value


def _ai_lessons(db: Database, user_id: int) -> list:
    return [x for x in db.get_lessons(user_id, 1000) if _is_ai_category(str(x["category"] or ""))]


def _categories(lessons: list) -> list[dict]:
    counts: dict[str, int] = {}
    for lesson in lessons:
        category = str(lesson["category"] or "📂 مواد أخرى")
        counts[category] = counts.get(category, 0) + 1
    return [{"category": k, "lesson_count": v} for k, v in counts.items()]


def _key(lesson) -> str:
    return str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])


def _title(lesson) -> str:
    name = str(lesson["file_name"] or "الدرس")
    return name.split(" - ", 1)[1] if " - " in name else name


def _unique_files(lessons: list) -> list:
    grouped: dict[str, tuple[str, int]] = {}
    for lesson in lessons:
        key = _key(lesson)
        name, count = grouped.get(key, (str(lesson["file_name"] or "الملف"), 0))
        grouped[key] = (name, count + 1)
    return [(key, name, count) for key, (name, count) in grouped.items()]


def _question_count(text: str) -> int:
    words, chars = len(str(text or "").split()), len(str(text or ""))
    if words < 120 or chars < 700: return 3
    if words < 250 or chars < 1500: return 5
    if words < 450 or chars < 2800: return 8
    if words < 750 or chars < 5000: return 12
    return 20


def _term_text(data: dict) -> str:
    blocks = []
    for raw in (data.get("english_terms") or [])[:12]:
        value = str(raw)
        if " — " in value:
            en, ar = value.split(" — ", 1)
        elif " - " in value:
            en, ar = value.split(" - ", 1)
        else:
            en, ar = value, "لم يُذكر معنى واضح لهذا المصطلح."
        blocks.append(f"🇬🇧 <b>{html.escape(en.strip())}</b>\n↳ {html.escape(ar.strip())}")
    return "\n\n".join(blocks) or "لا توجد مصطلحات إنجليزية واضحة."


@router.callback_query(F.data == "ai_section")
async def ai_section(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🧠 <b>قسم الذكاء الاصطناعي</b>\n\n"
        "📚 المكتبة ← الملف ← الدرس ← الصفحة.\n"
        "🧠 الشرح والاختبارات هنا فقط بواسطة الذكاء الاصطناعي.\n"
        "🐍 محرك Python الخاص بالبوت والأتمتة منفصل تمامًا.",
        reply_markup=section_menu("ai"),
    )


@router.callback_query(F.data == "ai_library")
async def ai_library(callback: CallbackQuery, db: Database):
    categories = _categories(_ai_lessons(db, callback.from_user.id))
    await callback.answer()
    if not categories:
        await callback.message.edit_text("📚 <b>مكتبة الذكاء الاصطناعي فارغة</b>\n\nأرسل ملف مادة الذكاء الاصطناعي أولًا.")
        return
    await callback.message.edit_text("🧠 <b>مكتبة الذكاء الاصطناعي</b>\n\nاختر القسم:", reply_markup=ai_categories_menu(categories))


@router.callback_query(F.data.startswith("ai_category:"))
async def ai_category(callback: CallbackQuery, db: Database):
    lessons = _ai_lessons(db, callback.from_user.id)
    value = callback.data.split(":", 1)[1]
    category = next((str(x["category"]) for x in _categories(lessons) if token(str(x["category"])) == value), None)
    await callback.answer()
    if not category:
        await callback.message.edit_text("❌ قسم الذكاء الاصطناعي غير موجود.")
        return
    await callback.message.edit_text(f"🧠 <b>{html.escape(category)}</b>\n\nاختر:", reply_markup=ai_category_menu(category))


@router.callback_query(F.data.startswith("ai_categoryfiles:"))
async def ai_categoryfiles(callback: CallbackQuery, db: Database):
    lessons = _ai_lessons(db, callback.from_user.id)
    value = callback.data.split(":", 1)[1]
    category = next((str(x["category"]) for x in _categories(lessons) if token(str(x["category"])) == value), None)
    await callback.answer()
    if not category:
        await callback.message.edit_text("❌ القسم غير موجود.")
        return
    selected = [x for x in lessons if str(x["category"] or "") == category]
    await callback.message.edit_text(f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:", reply_markup=ai_files_menu(_unique_files(selected), category))


@router.callback_query(F.data.startswith("ai_file:"))
async def ai_file(callback: CallbackQuery, db: Database):
    lessons = _ai_lessons(db, callback.from_user.id)
    key = find_file(lessons, callback.data.split(":", 1)[1])
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود في قسم الذكاء الاصطناعي.")
        return
    selected = file_lessons(lessons, key)
    await callback.message.edit_text(
        f"🧠 <b>قسم الذكاء الاصطناعي</b>\n📚 <b>{html.escape(str(selected[0]['category'] or '📂 مواد أخرى'))}</b>\n📘 <b>{html.escape(str(selected[0]['file_name']))}</b>\n\nاختر الدرس:",
        reply_markup=ai_lessons_menu(selected, key),
    )


@router.callback_query(F.data.startswith("ai_fileback:"))
async def ai_fileback(callback: CallbackQuery, db: Database):
    lessons = _ai_lessons(db, callback.from_user.id)
    key = find_file(lessons, callback.data.split(":", 1)[1])
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود.")
        return
    selected = file_lessons(lessons, key)
    category = str(selected[0]["category"] or "📂 مواد أخرى")
    category_lessons = [x for x in lessons if str(x["category"] or "") == category]
    await callback.message.edit_text(f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:", reply_markup=ai_files_menu(_unique_files(category_lessons), category))


@router.callback_query(F.data.startswith("ai_lesson:"))
async def ai_lesson(callback: CallbackQuery, db: Database):
    _, lesson_id, _ = callback.data.split(":", 2)
    lesson = db.get_lesson(int(lesson_id), callback.from_user.id)
    await callback.answer()
    if not lesson or not _is_ai_category(str(lesson["category"] or "")):
        await callback.message.edit_text("❌ هذا الدرس تابع لقسم آخر.")
        return
    lessons = file_lessons(_ai_lessons(db, callback.from_user.id), _key(lesson))
    number = next((i + 1 for i, row in enumerate(lessons) if int(row["id"]) == int(lesson_id)), 1)
    await callback.message.edit_text(
        f"📖 <b>{html.escape(_title(lesson))}</b>\n🔢 <b>الدرس {number} من {len(lessons)}</b>\n📚 <b>{html.escape(str(lesson['category'] or '📂 مواد أخرى'))}</b>\n\n"
        "🧠 <b>الشرح والاختبار: الذكاء الاصطناعي</b>\nاختر الوظيفة:",
        reply_markup=ai_lesson_menu(int(lesson_id), _key(lesson)),
    )


@router.callback_query(F.data.startswith("ai_lessonback:"))
async def ai_lessonback(callback: CallbackQuery, db: Database):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    await callback.answer()
    if not lesson:
        await callback.message.edit_text("❌ الدرس غير موجود.")
        return
    selected = file_lessons(_ai_lessons(db, callback.from_user.id), _key(lesson))
    await callback.message.edit_text(f"📘 <b>{html.escape(str(lesson['file_name']))}</b>\n\nاختر الدرس:", reply_markup=ai_lessons_menu(selected, _key(lesson)))


@router.callback_query(F.data.startswith("ai_explain:"))
async def ai_explain(callback: CallbackQuery, db: Database, ai_service: AIService):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    if not lesson or not _is_ai_category(str(lesson["category"] or "")):
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await callback.answer("🧠 جاري الشرح…")
    try:
        analysis = await ai_service.analyze_lesson(str(lesson["extracted_text"] or ""))
        await callback.message.edit_text(
            f"🧠 <b>شرح الدرس</b>\n📖 <b>{html.escape(_title(lesson))}</b>\n\n"
            f"{html.escape(str(analysis.get('summary') or 'لا يوجد شرح كافٍ.'))}\n\n"
            f"🇬🇧 <b>المصطلحات ومعانيها</b>\n{_term_text(analysis)}",
            reply_markup=ai_lesson_menu(int(lesson["id"]), _key(lesson)),
        )
    except Exception:
        logger.exception("AI lesson explanation failed")
        await callback.message.edit_text("⚠️ تعذر تشغيل الذكاء الاصطناعي لهذا الدرس.")


@router.callback_query(F.data.startswith("ai_quiz:"))
async def ai_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator):
    lesson = db.get_lesson(int(callback.data.split(":", 1)[1]), callback.from_user.id)
    if not lesson or not _is_ai_category(str(lesson["category"] or "")):
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    text = str(lesson["extracted_text"] or "").strip()
    if not text:
        await callback.answer("⚠️ لا يوجد محتوى كافٍ.", show_alert=True)
        return
    await callback.answer("🧠 جاري إنشاء الاختبار…")
    try:
        questions = await quiz_generator.create_smart(text, _question_count(text), "medium")
        if not questions:
            await callback.message.edit_text("⚠️ لم أجد معلومات كافية لإنشاء الاختبار.")
            return
        quiz_id = db.create_quiz(int(lesson["id"]), quiz_generator.serialize(questions), len(questions), "medium")
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=int(lesson["id"]), questions=questions, answers=[], group_mode=False, engine="ai", user_id=callback.from_user.id)
        await callback.message.edit_text(
            f"📝 <b>اختبار الدرس</b>\n🧠 <b>الذكاء الاصطناعي</b>\n🎯 <b>{len(questions)} سؤالًا</b>\n⏱️ <b>15 ثانية لكل سؤال</b>\n\nإذا انتهى الوقت ينتقل للسؤال التالي تلقائيًا."
        )
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        logger.exception("AI lesson quiz failed")
        await callback.message.edit_text("⚠️ تعذر إنشاء اختبار الذكاء الاصطناعي.")
