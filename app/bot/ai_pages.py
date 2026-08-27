"""AI page navigation and page-level AI actions."""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.keyboards import ai_lesson_menu, page_keyboard
from app.bot.page_helpers import ai_page_text
from app.bot.quiz_engine import QuizState, send_question
from app.database import Database
from app.services.file_extractor import page_parts
from app.services import AIService, QuizGenerator

router = Router(name="ai_pages")


def _is_ai(lesson) -> bool:
    value = str(lesson["category"] or "").casefold()
    return "الذكاء الاصطناعي" in value or "artificial intelligence" in value or "intelligent agent" in value


def _pages(lesson):
    return page_parts(str(lesson["extracted_text"] or ""))


def _title(lesson):
    name = str(lesson["file_name"] or "الدرس")
    return name.split(" - ", 1)[-1]


def _count(text: str) -> int:
    words, chars = len(str(text or "").split()), len(str(text or ""))
    if words < 100 or chars < 600: return 3
    if words < 220 or chars < 1300: return 5
    return min(10, max(6, words // 120))


@router.callback_query(F.data.startswith("ai_pages:"))
async def open_ai_pages(callback: CallbackQuery, db: Database):
    lesson_id = int(callback.data.split(":", 1)[1])
    lesson = db.get_lesson(lesson_id, callback.from_user.id)
    if not lesson or not _is_ai(lesson):
        await callback.answer("❌ الدرس غير موجود في قسم الذكاء الاصطناعي.", show_alert=True)
        return
    pages = _pages(lesson)
    if not pages:
        await callback.answer("❌ لا توجد صفحات محفوظة لهذا الدرس.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(ai_page_text(lesson, pages, 0), reply_markup=page_keyboard(lesson_id, pages, 0))


@router.callback_query(F.data.startswith("ai_page:"))
async def open_ai_page(callback: CallbackQuery, db: Database):
    _, lesson_id, index = callback.data.split(":", 2)
    lesson = db.get_lesson(int(lesson_id), callback.from_user.id)
    if not lesson or not _is_ai(lesson):
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    pages = _pages(lesson)
    index = int(index)
    if not pages or index < 0 or index >= len(pages):
        await callback.answer("❌ الصفحة غير موجودة.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(ai_page_text(lesson, pages, index), reply_markup=page_keyboard(int(lesson_id), pages, index))


@router.callback_query(F.data.startswith("ai_page_explain:"))
async def explain_ai_page(callback: CallbackQuery, db: Database, ai_service: AIService):
    _, lesson_id, index = callback.data.split(":", 2)
    lesson = db.get_lesson(int(lesson_id), callback.from_user.id)
    if not lesson or not _is_ai(lesson):
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    pages = _pages(lesson)
    index = int(index)
    if not pages or index < 0 or index >= len(pages):
        await callback.answer("❌ الصفحة غير موجودة.", show_alert=True)
        return
    await callback.answer("🧠 جاري شرح الصفحة…")
    try:
        analysis = await ai_service.analyze_lesson(pages[index][1])
        text = (
            f"🧠 <b>شرح الصفحة</b>\n📖 <b>{html.escape(_title(lesson))}</b>\n"
            f"📄 <b>صفحة {pages[index][0]} من {len(pages)}</b>\n\n"
            f"{html.escape(str(analysis.get('summary') or 'لا يوجد شرح كافٍ.'))}"
        )
        await callback.message.edit_text(text[:3900], reply_markup=page_keyboard(int(lesson_id), pages, index))
    except Exception:
        await callback.answer("❌ تعذر شرح الصفحة.", show_alert=True)


@router.callback_query(F.data.startswith("ai_page_quiz:"))
async def quiz_ai_page(callback: CallbackQuery, state: FSMContext, db: Database, quiz_generator: QuizGenerator):
    _, lesson_id, index = callback.data.split(":", 2)
    lesson = db.get_lesson(int(lesson_id), callback.from_user.id)
    if not lesson or not _is_ai(lesson):
        await callback.answer("❌ الدرس غير موجود.", show_alert=True)
        return
    pages = _pages(lesson)
    index = int(index)
    if not pages or index < 0 or index >= len(pages):
        await callback.answer("❌ الصفحة غير موجودة.", show_alert=True)
        return
    await callback.answer("🧠 جاري إنشاء اختبار الصفحة…")
    try:
        text = pages[index][1]
        questions = await quiz_generator.create_smart(text, _count(text), "medium")
        if not questions:
            await callback.message.edit_text("⚠️ لم أجد معلومات كافية لإنشاء اختبار الصفحة.")
            return
        quiz_id = db.create_quiz(int(lesson_id), quiz_generator.serialize(questions), len(questions), "medium")
        await state.set_state(QuizState.active)
        await state.update_data(quiz_id=quiz_id, lesson_id=int(lesson_id), questions=questions, answers=[], group_mode=False, engine="ai", user_id=callback.from_user.id)
        await callback.message.edit_text(
            f"📝 <b>اختبار الصفحة {pages[index][0]}</b>\n🧠 <b>الذكاء الاصطناعي</b>\n"
            f"🎯 <b>{len(questions)} أسئلة</b>\n⏱️ <b>15 ثانية لكل سؤال</b>"
        )
        await send_question(callback.message, state, quiz_id, questions, 0, [], db)
    except Exception:
        await callback.message.edit_text("⚠️ تعذر إنشاء اختبار الصفحة.")
