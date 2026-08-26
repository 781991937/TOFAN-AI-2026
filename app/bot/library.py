import base64
import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.handlers import QuizState, send_question
from app.bot.keyboards import category_menu, file_list_menu, library_menu, result_menu
from app.database import Database
from app.services import QuizGenerator

logger = logging.getLogger(__name__)
router = Router(name="library")


def _decode(value: str) -> str:
    return base64.urlsafe_b64decode(value.encode()).decode("utf-8")


def _encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def classify_lesson(lesson) -> str:
    name = str(lesson["file_name"] or "").lower()
    text = str(lesson["extracted_text"] or "")[:12000].lower()
    source = f"{name}\n{text}"
    rules = [
        ("🤖 مقدمة الذكاء الاصطناعي", ["artificial intelligence", "الذكاء الاصطناعي", "intelligent agent", "intelligent agents", "الوكلاء الأذكياء", "peas", "rational agent", "turing test", "اختبار تورينغ", "state space", "problem solving", "knowledge representation"]),
        ("🗣 مهارات الاتصال", ["communication skills", "مهارات الاتصال", "communication", "التواصل", "listening", "الاستماع", "presentation", "presentation skills", "verbal", "nonverbal", "الاتصال اللفظي", "الاتصال غير اللفظي"]),
        ("💻 البرمجة", ["python", "programming", "البرمجة", "algorithm", "الخوارزمية", "variable", "variables", "loop", "function", "functions", "code"]),
        ("🇬🇧 اللغة الإنجليزية", ["english", "grammar", "vocabulary", "present simple", "tense", "adjective", "verb", "noun"]),
        ("📐 الرياضيات", ["discrete mathematics", "discrete math", "رياضيات منفصلة", "logic", "truth table", "المجموعات", "set theory", "probability"]),
        ("🖥 مهارات الحاسوب", ["computer skills", "مهارات الحاسوب", "microsoft word", "excel", "powerpoint", "windows", "الحاسوب"]),
    ]
    scores = [(sum(source.count(k) for k in keys), category) for category, keys in rules]
    score, category = max(scores, key=lambda x: x[0])
    return category if score > 0 else "📂 مواد أخرى"


def prepare_categories(db: Database, user_id: int):
    lessons = db.get_lessons(user_id, 1000)
    for lesson in lessons:
        category = classify_lesson(lesson)
        current = str(lesson["category"] or "📂 مواد أخرى")
        if current != category:
            db.update_lesson_category(int(lesson["id"]), category)
    return db.get_categories(user_id)


@router.callback_query(F.data == "library")
async def library_home(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    categories = prepare_categories(db, callback.from_user.id)
    if not categories:
        await callback.message.answer("📚 المكتبة فارغة. أرسل أي ملف وسأكتشف مادته وأرتبه تلقائيًا.")
        return
    await callback.message.edit_text("📚 <b>مكتبتك الذكية</b>\n\nاختر المادة:", reply_markup=library_menu(categories))


@router.callback_query(F.data.startswith("category:"))
async def open_category(callback: CallbackQuery, db: Database) -> None:
    category = _decode(callback.data.split(":", 1)[1])
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    await callback.answer()
    if not lessons:
        await callback.message.answer("📚 لا توجد ملفات في هذا القسم.")
        return
    await callback.message.edit_text(
        f"📚 <b>{html.escape(category)}</b>\n\nاختر ملفًا أو أنشئ اختبارًا شاملًا للقسم:",
        reply_markup=category_menu(category, lessons),
    )


@router.callback_query(F.data.startswith("filequiz:"))
async def file_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    await callback.answer("🧠 تجهيز 20 سؤالًا...")
    if not lesson:
        await callback.message.answer("❌ الملف غير موجود.")
        return
    try:
        questions = await quiz_generator.create(lesson["extracted_text"], 20, "medium", fresh=True)
        if len(questions) < 20:
            # Generate from the same content again and combine different variants.
            extra = await quiz_generator.create(lesson["extracted_text"], 20, "medium", fresh=True)
            questions.extend(extra[:20-len(questions)])
        questions = questions[:20]
        quiz_id = db.create_quiz(lesson_id, quiz_generator.serialize(questions), 20, "medium")
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=lesson_id, questions=questions, answers=[], group_mode=False)
        await callback.message.edit_text(
            f"📝 <b>اختبار الملف</b>\n📚 {html.escape(str(lesson['file_name']))}\n\n"
            f"🎯 <b>20 سؤالًا متنوعًا</b>\nنبدأ الآن!",
        )
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        logger.exception("File quiz failed")
        await callback.message.answer("⚠️ تعذر إنشاء اختبار الملف حاليًا.")


@router.callback_query(F.data.startswith("categoryquiz:"))
async def category_quiz(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator) -> None:
    category = _decode(callback.data.split(":", 1)[1])
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    await callback.answer("🧠 تجهيز 50 سؤالًا من القسم...")
    if not lessons:
        await callback.message.answer("❌ لا توجد ملفات في هذا القسم.")
        return
    try:
        combined = "\n\n===== ملف جديد =====\n\n".join(str(x["extracted_text"] or "") for x in lessons)
        questions = await quiz_generator.create(combined, 50, "medium", fresh=True)
        # Local generation may have fewer than 50 source sentences. Try a second variant.
        if len(questions) < 50:
            extra = await quiz_generator.create(combined, 50, "medium", fresh=True)
            seen = {q.get("question") for q in questions}
            for q in extra:
                if q.get("question") not in seen:
                    questions.append(q)
                    seen.add(q.get("question"))
                if len(questions) >= 50:
                    break
        if len(questions) < 50:
            await callback.message.answer(f"⚠️ محتوى القسم لا يحتوي على معلومات كافية لإنشاء 50 سؤالًا مستقلًا. المتاح حاليًا: {len(questions)}.")
            return
        questions = questions[:50]
        lesson_id = int(lessons[0]["id"])
        quiz_id = db.create_quiz(lesson_id, quiz_generator.serialize(questions), 50, "medium")
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=lesson_id, questions=questions, answers=[], group_mode=False)
        await callback.message.edit_text(
            f"🎓 <b>الاختبار الشامل للقسم</b>\n📚 {html.escape(category)}\n\n"
            "🔥 <b>50 سؤالًا من جميع ملفات القسم</b>\nنبدأ الآن!",
        )
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        logger.exception("Category quiz failed")
        await callback.message.answer("⚠️ تعذر إنشاء اختبار القسم حاليًا.")


@router.callback_query(F.data.startswith("categoryfiles:"))
async def category_files(callback: CallbackQuery, db: Database) -> None:
    category = _decode(callback.data.split(":", 1)[1])
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    await callback.answer()
    await callback.message.edit_text(
        f"📚 <b>{html.escape(category)}</b>\n\nاختر الملف:",
        reply_markup=file_list_menu(lessons, category),
    )
