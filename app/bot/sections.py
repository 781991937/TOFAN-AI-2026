import hashlib
import html
import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.handlers import QuizState, send_question
from app.bot.keyboards import (
    ai_categories_menu,
    ai_category_menu,
    ai_files_menu,
    ai_lesson_menu,
    ai_lessons_menu,
    section_menu,
)
from app.bot.library import prepare_categories
from app.database import Database
from app.services import AIService, QuizGenerator

router = Router(name="sections")


def _token(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _decode_category(token: str, categories: list) -> str | None:
    for row in categories:
        category = str(row["category"])
        if _token(category) == token:
            return category
    return None


def _file_key(lesson) -> str:
    return str(lesson["file_id"] or lesson["file_path"] or lesson["file_name"])


def _files_in_category(lessons: list) -> list[tuple[str, str, int]]:
    grouped = {}
    for lesson in lessons:
        key = _file_key(lesson)
        if key not in grouped:
            name = str(lesson["file_name"] or "الملف")
            if " - " in name:
                name = name.split(" - ", 1)[0]
            grouped[key] = [name, 0]
        grouped[key][1] += 1
    result = []
    for key, (name, count) in grouped.items():
        if len(name) > 40:
            name = name[:37] + "..."
        result.append((key, name, count))
    return result


def _find_file(lessons: list, token: str):
    for lesson in lessons:
        key = _file_key(lesson)
        if _token(key) == token:
            return key
    return None


def _lesson_title(lesson) -> str:
    title = str(lesson["file_name"] or "الدرس")
    if " - " in title:
        title = title.split(" - ", 1)[1]
    return title


def _lesson_position(lesson, all_lessons: list) -> tuple[int, int]:
    same_file = [x for x in all_lessons if _file_key(x) == _file_key(lesson)]
    ids = [int(x["id"]) for x in same_file]
    try:
        return ids.index(int(lesson["id"])) + 1, len(ids)
    except ValueError:
        return 1, max(1, len(same_file))


def _adaptive_question_count(text: str) -> int:
    """Choose a useful quiz size without inventing repeated questions."""
    size = len(str(text or "").strip())
    if size < 700:
        return max(3, min(5, size // 130 or 3))
    if size < 1400:
        return max(5, min(8, size // 180))
    if size < 3000:
        return max(8, min(12, size // 250))
    if size < 6000:
        return max(12, min(16, size // 350))
    return 20


@router.callback_query(F.data == "ai_section")
async def ai_section(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "🧠 <b>قسم الذكاء الاصطناعي</b>\n\n"
        "نفس نظام مكتبة البوت ونفس التنقل، لكن عند الوصول إلى الدرس تصبح الشروحات والاختبارات من اختصاص الذكاء الاصطناعي.\n\n"
        "📚 المكتبة → المادة → الملف → الدرس\n"
        "🧠 الشرح الذكي والاختبار الذكي → الذكاء الاصطناعي\n"
        "⚙️ الملفات والصفحات والتنقل والتنزيل → نظام البوت",
        reply_markup=section_menu("ai"),
    )


@router.callback_query(F.data == "ai_library")
async def ai_library(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    categories = prepare_categories(db, callback.from_user.id)
    if not categories:
        await callback.message.edit_text(
            "📚 <b>المكتبة فارغة</b>\n\nأرسل ملفًا من قسم البوت أولًا.",
            reply_markup=section_menu("ai"),
        )
        return
    await callback.message.edit_text(
        "🧠 <b>مكتبة الذكاء الاصطناعي</b>\n\nاختر القسم:",
        reply_markup=ai_categories_menu(categories),
    )


@router.callback_query(F.data.startswith("ai_category:"))
async def ai_category(callback: CallbackQuery, db: Database) -> None:
    token = callback.data.split(":", 1)[1]
    categories = prepare_categories(db, callback.from_user.id)
    category = _decode_category(token, categories)
    await callback.answer()
    if not category:
        await callback.message.edit_text("❌ القسم غير موجود.", reply_markup=section_menu("ai"))
        return
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    if not lessons:
        await callback.message.edit_text("❌ لا توجد ملفات في هذا القسم.", reply_markup=section_menu("ai"))
        return
    await callback.message.edit_text(
        f"🧠 <b>{html.escape(category)}</b>\n\nاختر ما تريد:",
        reply_markup=ai_category_menu(category),
    )


@router.callback_query(F.data.startswith("ai_categoryfiles:"))
async def ai_category_files(callback: CallbackQuery, db: Database) -> None:
    token = callback.data.split(":", 1)[1]
    categories = prepare_categories(db, callback.from_user.id)
    category = _decode_category(token, categories)
    await callback.answer()
    if not category:
        await callback.message.edit_text("❌ القسم غير موجود.", reply_markup=section_menu("ai"))
        return
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    files = _files_in_category(lessons)
    await callback.message.edit_text(
        f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:",
        reply_markup=ai_files_menu(files, category),
    )


@router.callback_query(F.data.startswith("ai_categoryquiz:"))
async def ai_category_quiz(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    quiz_generator: QuizGenerator,
) -> None:
    token = callback.data.split(":", 1)[1]
    categories = prepare_categories(db, callback.from_user.id)
    category = _decode_category(token, categories)
    await callback.answer("🧠 جاري إعداد اختبار القسم...")
    if not category:
        await callback.message.edit_text("❌ القسم غير موجود.", reply_markup=section_menu("ai"))
        return
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    combined = "\n\n===== ملف جديد =====\n\n".join(str(x["extracted_text"] or "") for x in lessons)
    if len(combined.strip()) < 1000:
        await callback.message.edit_text("⚠️ محتوى القسم غير كافٍ لصناعة اختبار متنوع من 50 سؤالًا.")
        return
    try:
        questions = (await quiz_generator.create_smart(combined, 50, "medium"))[:50]
        if len(questions) < 50:
            await callback.message.edit_text(
                f"⚠️ الذكاء الاصطناعي استطاع إنشاء {len(questions)} سؤالًا مختلفًا فقط من محتوى القسم.\n\nلن أكرر الأسئلة فقط للوصول إلى 50."
            )
            return
        lesson_id = int(lessons[0]["id"])
        quiz_id = db.create_quiz(lesson_id, quiz_generator.serialize(questions), 50, "medium")
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=lesson_id, questions=questions, answers=[], group_mode=False)
        await callback.message.edit_text(
            f"🎓 <b>اختبار القسم كامل</b>\n📚 <b>{html.escape(category)}</b>\n\n"
            "🧠 <b>طريقة إنشاء الأسئلة: الذكاء الاصطناعي</b>\n"
            "📝 <b>50 سؤالًا متنوعًا من جميع ملفات القسم</b>\n\nنبدأ الآن!"
        )
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        await callback.message.edit_text("⚠️ تعذر إنشاء اختبار القسم حاليًا. حاول مرة أخرى.")


@router.callback_query(F.data.startswith("ai_file:"))
async def ai_file(callback: CallbackQuery, db: Database) -> None:
    token = callback.data.split(":", 1)[1]
    lessons = db.get_lessons(callback.from_user.id, 1000)
    key = _find_file(lessons, token)
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود.", reply_markup=section_menu("ai"))
        return
    selected = [lesson for lesson in lessons if _file_key(lesson) == key]
    category = str(selected[0]["category"] or "📂 مواد أخرى")
    await callback.message.edit_text(
        f"🧠 <b>قسم الذكاء الاصطناعي</b>\n"
        f"📚 <b>{html.escape(category)}</b>\n"
        f"📘 <b>{html.escape(_lesson_title(selected[0]))}</b>\n\n"
        "اختر الدرس:",
        reply_markup=ai_lessons_menu(selected, key),
    )


@router.callback_query(F.data.startswith("ai_fileback:"))
async def ai_file_back(callback: CallbackQuery, db: Database) -> None:
    token = callback.data.split(":", 1)[1]
    lessons = db.get_lessons(callback.from_user.id, 1000)
    key = _find_file(lessons, token)
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود.", reply_markup=section_menu("ai"))
        return
    selected = [lesson for lesson in lessons if _file_key(lesson) == key]
    category = str(selected[0]["category"] or "📂 مواد أخرى")
    await callback.message.edit_text(
        f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:",
        reply_markup=ai_files_menu(_files_in_category(db.get_lessons_by_category(callback.from_user.id, category)), category),
    )


@router.callback_query(F.data.startswith("ai_lesson:"))
async def ai_lesson(callback: CallbackQuery, db: Database) -> None:
    _, lesson_id_text, file_token = callback.data.split(":", 2)
    lesson_id = int(lesson_id_text)
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await callback.answer()
    all_lessons = db.get_lessons(callback.from_user.id, 1000)
    number, total = _lesson_position(lesson, all_lessons)
    title = _lesson_title(lesson)
    category = str(lesson["category"] or "📂 مواد أخرى")
    await callback.message.edit_text(
        f"📖 <b>{html.escape(title)}</b>\n"
        f"🔢 <b>الدرس {number} من {total}</b>\n"
        f"📚 <b>القسم:</b> {html.escape(category)}\n\n"
        "🧠 <b>طريقة الشرح والاختبار: الذكاء الاصطناعي</b>\n\n"
        "اختر ما تريد من أزرار الدرس:",
        reply_markup=ai_lesson_menu(lesson_id, _file_key(lesson)),
    )


@router.callback_query(F.data.startswith("ai_explain:"))
async def ai_explain(callback: CallbackQuery, db: Database, ai_service: AIService) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await callback.answer("🧠 جاري الشرح...")
    try:
        analysis = await ai_service.analyze_lesson(str(lesson["extracted_text"] or ""))
        summary = str(analysis.get("summary", "لم يتم إنشاء شرح.")).strip()
        concepts = analysis.get("concepts", [])[:12]
        db.update_lesson_analysis(
            lesson_id,
            summary,
            json.dumps(concepts, ensure_ascii=False),
            lesson["key_points"] or "",
        )
        title = _lesson_title(lesson)
        category = str(lesson["category"] or "📂 مواد أخرى")
        concepts_text = "\n".join(f"• {html.escape(str(item))}" for item in concepts) or "• لا توجد مفاهيم إضافية."
        await callback.message.edit_text(
            f"📖 <b>{html.escape(title)}</b>\n"
            f"📚 <b>القسم:</b> {html.escape(category)}\n\n"
            "🧠 <b>طريقة الشرح: الذكاء الاصطناعي</b>\n\n"
            f"{html.escape(summary[:3000])}\n\n"
            f"📌 <b>أهم المفاهيم</b>\n{concepts_text}",
            reply_markup=ai_lesson_menu(lesson_id, _file_key(lesson)),
        )
    except Exception:
        await callback.message.edit_text(
            "⚠️ <b>تعذر تشغيل الذكاء الاصطناعي الآن.</b>\n\nالملف محفوظ ولم يتأثر. حاول مرة أخرى."
        )


@router.callback_query(F.data.startswith("ai_quiz:"))
async def ai_quiz(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    quiz_generator: QuizGenerator,
) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    await callback.answer("🧠 جاري إعداد الاختبار...")
    try:
        text = str(lesson["extracted_text"] or "").strip()
        target = _adaptive_question_count(text)
        questions = (await quiz_generator.create_smart(text, target, "medium"))[:target]
        if not questions:
            await callback.message.edit_text("⚠️ المحتوى غير كافٍ لصناعة اختبار مفيد.")
            return
        quiz_id = db.create_quiz(lesson_id, quiz_generator.serialize(questions), len(questions), "medium")
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=lesson_id, questions=questions, answers=[], group_mode=False)
        await callback.message.edit_text(
            f"📝 <b>اختبار الدرس</b>\n📖 <b>{html.escape(_lesson_title(lesson))}</b>\n\n"
            f"🧠 <b>طريقة إنشاء الأسئلة: الذكاء الاصطناعي</b>\n"
            f"🎯 <b>{len(questions)} سؤالًا</b> — العدد متكيف مع حجم المحتوى\n\nنبدأ الآن!"
        )
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        await callback.message.edit_text("⚠️ تعذر إنشاء اختبار الدرس حاليًا. حاول مرة أخرى.")


@router.callback_query(F.data == "automation_section")
async def automation_section(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "🤖 <b>قسم البوت والأتمتة</b>\n\n"
        "نفس نظام المكتبة والتنقل، لكن وظائف هذا القسم تنفذها الأتمتة والبايثون فقط.\n\n"
        "📚 المكتبة → المادة → الملف → الدرس\n"
        "⚙️ استقبال الملفات وتنظيمها وتقسيمها وحفظها\n"
        "📖 الصفحات والتنقل والتنزيل → نظام البوت\n\n"
        "🧠 الشرح والاختبارات الذكية موجودة في قسم الذكاء الاصطناعي فقط.",
        reply_markup=section_menu("bot"),
    )


@router.callback_query(F.data == "file_management")
async def file_management(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "📥 <b>إدارة الملفات — الأتمتة</b>\n\n"
        "• 📥 استقبال PDF / DOCX / TXT\n"
        "• 🗂️ حفظ الملف ونسخة Telegram\n"
        "• 🗂️ اكتشاف المادة وتنظيم الملف داخل القسم\n"
        "• 📖 تقسيم الملف إلى دروس وصفحات\n"
        "• 📤 إمكانية تنزيل الملف لاحقًا حتى بعد حذفه من الهاتف\n\n"
        "⚙️ التنفيذ هنا بواسطة البوت وPython فقط، بدون استدعاء الذكاء الاصطناعي.",
        reply_markup=section_menu("bot"),
    )


@router.callback_query(F.data == "navigation_help")
async def navigation_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "🧭 <b>الصفحات والتنقل — الأتمتة</b>\n\n"
        "بعد اختيار المادة ثم الملف ثم الدرس ستجد:\n"
        "• 📖 صفحات الدرس\n"
        "• ⬅️ الصفحة السابقة / التالية ➡️\n"
        "• ⬅️ الدرس السابق / التالي ➡️\n"
        "• 📥 تنزيل الملف من Telegram\n\n"
        "⚙️ هذه الوظائف تعمل بواسطة البوت وPython ولا تعتمد على الذكاء الاصطناعي.",
        reply_markup=section_menu("bot"),
    )
