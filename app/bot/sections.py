import hashlib
import html
import json
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.handlers import QuizState, send_question
from app.bot.keyboards import (
    ai_actions_menu,
    ai_categories_menu,
    ai_files_menu,
    ai_lessons_menu,
    main_menu,
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


@router.callback_query(F.data == "ai_section")
async def ai_section(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "🧠 <b>قسم الذكاء</b>\n\n"
        "هنا كل ما يحتاج الذكاء الاصطناعي فقط:\n\n"
        "• 🧠 شرح ذكي: فهم وتحليل الدرس.\n"
        "• 📝 اختبار ذكي: إنشاء اختبار من المحتوى.\n"
        "• 💡 فكرة عملية: تحويل ما تعلمته إلى تطبيق واقعي.\n\n"
        "📌 اختيار المادة والملف والدرس مجرد تنقّل؛ الذكاء يبدأ عند تنفيذ الوظيفة.",
        reply_markup=ai_actions_menu(),
    )


@router.callback_query(F.data.startswith("ai_pick:"))
async def ai_pick(callback: CallbackQuery, db: Database) -> None:
    action = callback.data.split(":", 1)[1]
    categories = prepare_categories(db, callback.from_user.id)
    await callback.answer()
    if not categories:
        await callback.message.edit_text(
            "🧠 <b>لا توجد دروس بعد.</b>\n\nأرسل ملفًا أولًا من قسم البوت.",
            reply_markup=ai_actions_menu(),
        )
        return
    labels = {
        "explain": "الشرح الذكي",
        "quiz": "الاختبار الذكي",
        "practical": "الفكرة العملية الذكية",
    }
    label = labels.get(action, "وظيفة الذكاء")
    await callback.message.edit_text(
        f"🧠 <b>{label}</b>\n\nاختر المادة:",
        reply_markup=ai_categories_menu(categories, action),
    )


@router.callback_query(F.data.startswith("ai_category:"))
async def ai_category(callback: CallbackQuery, db: Database) -> None:
    _, action, token = callback.data.split(":", 2)
    categories = prepare_categories(db, callback.from_user.id)
    category = _decode_category(token, categories)
    await callback.answer()
    if not category:
        await callback.message.edit_text("❌ القسم غير موجود.", reply_markup=ai_actions_menu())
        return
    lessons = db.get_lessons_by_category(callback.from_user.id, category)
    files = _files_in_category(lessons)
    if not files:
        await callback.message.edit_text("❌ لا توجد ملفات في هذا القسم.", reply_markup=ai_actions_menu())
        return
    labels = {"explain": "الشرح الذكي", "quiz": "الاختبار الذكي", "practical": "الفكرة العملية الذكية"}
    await callback.message.edit_text(
        f"🧠 <b>{labels.get(action, 'وظيفة الذكاء')}</b>\n📚 <b>{html.escape(category)}</b>\n\nاختر الملف:",
        reply_markup=ai_files_menu(files, action),
    )


@router.callback_query(F.data.startswith("ai_file:"))
async def ai_file(callback: CallbackQuery, db: Database) -> None:
    _, action, token = callback.data.split(":", 2)
    lessons = db.get_lessons(callback.from_user.id, 1000)
    key = _find_file(lessons, token)
    await callback.answer()
    if not key:
        await callback.message.edit_text("❌ الملف غير موجود.", reply_markup=ai_actions_menu())
        return
    selected = [lesson for lesson in lessons if _file_key(lesson) == key]
    name = str(selected[0]["file_name"] or "الملف")
    if " - " in name:
        name = name.split(" - ", 1)[0]
    labels = {"explain": "الشرح الذكي", "quiz": "الاختبار الذكي", "practical": "الفكرة العملية الذكية"}
    await callback.message.edit_text(
        f"🧠 <b>{labels.get(action, 'وظيفة الذكاء')}</b>\n"
        f"📘 <b>{html.escape(name)}</b>\n\nاختر الدرس:",
        reply_markup=ai_lessons_menu(selected, action),
    )


@router.callback_query(F.data.startswith("ai_lesson:"))
async def ai_lesson(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    ai_service: AIService,
    quiz_generator: QuizGenerator,
) -> None:
    _, action, lesson_id_text = callback.data.split(":", 2)
    lesson_id = int(lesson_id_text)
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return

    await callback.answer("🧠 جاري التنفيذ...")
    title = _lesson_title(lesson)

    if action == "explain":
        try:
            analysis = await ai_service.analyze_lesson(lesson["extracted_text"])
            summary = analysis.get("summary", "لم يتم إنشاء شرح.")
            concepts = analysis.get("concepts", [])[:12]
            db.update_lesson_analysis(
                lesson_id,
                summary,
                json.dumps(concepts, ensure_ascii=False),
                lesson["key_points"] or "",
            )
            concepts_text = "\n".join(f"• {html.escape(str(item))}" for item in concepts) or "• لا توجد مفاهيم إضافية."
            await callback.message.edit_text(
                f"🧠 <b>{html.escape(title)}</b>\n"
                f"📚 <b>القسم:</b> {html.escape(str(lesson['category'] or 'مواد أخرى'))}\n\n"
                "🧠 <b>طريقة الشرح: الذكاء الاصطناعي</b>\n\n"
                f"{html.escape(str(summary)[:3000])}\n\n"
                f"📌 <b>أهم المفاهيم</b>\n{concepts_text}",
            )
        except Exception:
            await callback.message.edit_text(
                "⚠️ <b>تعذر تشغيل الذكاء الاصطناعي الآن.</b>\n\n"
                "الملف محفوظ ولم يتأثر. حاول مرة أخرى من قسم الذكاء."
            )
        return

    if action == "practical":
        try:
            result = await ai_service.generate_practical_idea(lesson["extracted_text"])
            idea = html.escape(str(result.get("idea", "فكرة عملية")))
            why = html.escape(str(result.get("why", "مرتبطة مباشرة بمحتوى الدرس.")))
            example = html.escape(str(result.get("example", "لا يوجد مثال إضافي.")))
            steps = result.get("steps", [])
            steps_text = "\n".join(f"{i}. {html.escape(str(step))}" for i, step in enumerate(steps[:6], 1)) or "1. راجع الدرس ثم طبّق الفكرة على مثال من واقعك."
            await callback.message.edit_text(
                f"💡 <b>{idea}</b>\n"
                f"📖 <b>الدرس:</b> {html.escape(title)}\n"
                f"📚 <b>القسم:</b> {html.escape(str(lesson['category'] or 'مواد أخرى'))}\n\n"
                "🧠 <b>طريقة التنفيذ: الذكاء الاصطناعي</b>\n\n"
                f"🎯 <b>لماذا؟</b>\n{why}\n\n"
                f"🛠️ <b>خطوات التطبيق</b>\n{steps_text}\n\n"
                f"🌍 <b>مثال واقعي</b>\n{example}",
            )
        except Exception:
            await callback.message.edit_text(
                "⚠️ <b>تعذر إنشاء الفكرة العملية الآن.</b>\n\n"
                "الملف محفوظ. حاول مرة أخرى من قسم الذكاء."
            )
        return

    try:
        user = db.get_user(callback.from_user.id)
        questions = await quiz_generator.create_smart(
            lesson["extracted_text"],
            user["question_count"],
            user["difficulty"],
        )
        if not questions:
            await callback.message.edit_text("⚠️ لم أجد محتوى كافيًا لصناعة اختبار ذكي.")
            return
        quiz_id = db.create_quiz(
            lesson_id,
            quiz_generator.serialize(questions),
            len(questions),
            user["difficulty"],
        )
        await state.set_state(QuizState.active)
        await state.update_data(
            quiz_id=quiz_id,
            lesson_id=lesson_id,
            questions=questions,
            answers=[],
            group_mode=False,
        )
        await callback.message.edit_text(
            f"🧠 <b>اختبار ذكي</b>\n📖 <b>{html.escape(title)}</b>\n\n"
            f"📝 <b>{len(questions)} سؤالًا</b>\n"
            "🧠 <b>طريقة الاختبار: الذكاء الاصطناعي</b>\n\nنبدأ الآن!"
        )
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        await callback.message.edit_text("⚠️ تعذر إنشاء الاختبار الذكي الآن. حاول مرة أخرى.")


@router.callback_query(F.data == "automation_section")
async def automation_section(callback: CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 المكتبة", callback_data="library"), InlineKeyboardButton(text="📥 إدارة الملفات", callback_data="file_management")],
        [InlineKeyboardButton(text="🧭 الصفحات والتنقل", callback_data="navigation_help"), InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])
    await callback.message.edit_text(
        "🤖 <b>قسم البوت</b>\n\n"
        "هنا وظائف البوت والأتمتة فقط، بدون تشغيل الذكاء الاصطناعي تلقائيًا.\n\n"
        "📚 المكتبة: المواد ← الملفات ← الدروس.\n"
        "📄 الصفحات: استخراج وتنقل وحفظ محلي بواسطة نظام البوت.\n"
        "💾 الملفات: نسخة Telegram تبقى قابلة للتنزيل حتى بعد حذف الملف من الهاتف.\n\n"
        "📎 لإضافة ملف: أرسل PDF أو DOCX أو TXT إلى البوت.",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "file_management")
async def file_management(callback: CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 فتح المكتبة", callback_data="library"), InlineKeyboardButton(text="⬅️ قسم البوت", callback_data="automation_section")],
    ])
    await callback.message.edit_text(
        "📥 <b>إدارة الملفات — نظام البوت</b>\n\n"
        "• 📥 استقبال PDF / DOCX / TXT\n"
        "• 🗂️ حفظ الملف ونسخة Telegram\n"
        "• 🗂️ تنظيمه داخل المادة المناسبة\n"
        "• 📖 تقسيمه إلى دروس وصفحات\n"
        "• 📤 إعادة إرسال الملف للتنزيل لاحقًا\n\n"
        "🧠 لا يتم تشغيل الذكاء الاصطناعي في هذه الخطوة.",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "navigation_help")
async def navigation_help(callback: CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 فتح المكتبة", callback_data="library"), InlineKeyboardButton(text="⬅️ قسم البوت", callback_data="automation_section")],
    ])
    await callback.message.edit_text(
        "🧭 <b>الصفحات والتنقل — نظام البوت</b>\n\n"
        "بعد اختيار المادة ثم الملف ثم الدرس ستجد:\n"
        "• 📖 صفحات الدرس\n"
        "• ⬅️ الصفحة السابقة / التالية ➡️\n"
        "• ⬅️ الدرس السابق / التالي ➡️\n"
        "• 📥 تنزيل الملف من Telegram\n\n"
        "⚙️ هذه الوظائف تعمل بواسطة البوت ولا تعتمد على الذكاء الاصطناعي.",
        reply_markup=keyboard,
    )
