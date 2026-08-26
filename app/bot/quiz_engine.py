import html
import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.database import Database

logger = logging.getLogger(__name__)
router = Router(name="quiz_engine")


class QuizState(StatesGroup):
    active = State()


def answer_matches(question: dict, answer: str) -> bool:
    expected = str(question.get("answer", "")).strip().casefold()
    actual = str(answer or "").strip().casefold()
    if question.get("type") == "short":
        return bool(expected) and (expected == actual or expected in actual or actual in expected)
    return bool(expected) and actual == expected


def question_keyboard(options: list[str], index: int) -> InlineKeyboardMarkup:
    rows = []
    for i, option in enumerate(options):
        rows.append([InlineKeyboardButton(text=str(option)[:60], callback_data=f"ans:{index}:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _safe(value: object) -> str:
    return html.escape(str(value or ""))


async def finish_quiz(
    message: Message,
    state: FSMContext,
    quiz_id: int,
    lesson_id: int,
    questions: list[dict],
    answers: list[str],
    db: Database,
    group_mode: bool = False,
) -> None:
    score = sum(answer_matches(q, a) for q, a in zip(questions, answers))
    total = len(questions)
    percentage = round(score / total * 100, 1) if total else 0
    db.save_result(message.from_user.id, quiz_id, score, total, percentage, json.dumps(answers, ensure_ascii=False))

    lines = ["🏁 <b>انتهى الاختبار!</b>", "", f"✅ النتيجة: <b>{score}/{total}</b>", f"📊 النسبة: <b>{percentage}%</b>"]
    if group_mode:
        lines.append("\n👥 أضيفت نتيجتك إلى لوحة المتصدرين.")
    else:
        lines.append("\n📋 <b>مراجعة الأخطاء</b>")
        for i, (q, answer) in enumerate(zip(questions, answers), 1):
            if answer_matches(q, answer):
                lines.append(f"\n✅ {i}. صحيحة")
            else:
                lines.append(f"\n❌ {i}. إجابتك: {_safe(answer) or 'بدون إجابة'}")
                lines.append(f"   الصحيح: {_safe(q.get('answer'))}")
                explanation = _safe(q.get("explanation"))
                if explanation:
                    lines.append(f"   💡 {explanation}")

    from app.bot.keyboards import result_menu
    data = await state.get_data()
    bot_mode = data.get("engine") == "local"
    await message.answer("\n".join(lines)[:3900], reply_markup=result_menu(lesson_id, group=group_mode, bot=bot_mode))
    await state.clear()


async def send_question(
    message: Message,
    state: FSMContext,
    quiz_id: int,
    questions: list[dict],
    index: int,
    answers: list[str],
    db: Database,
) -> None:
    data = await state.get_data()
    lesson_id = int(data.get("lesson_id", 0))
    group_mode = bool(data.get("group_mode", False))
    if index >= len(questions):
        await finish_quiz(message, state, quiz_id, lesson_id, questions, answers, db, group_mode)
        return

    q = questions[index]
    q_type = str(q.get("type", "mcq"))
    text = (
        f"❓ <b>السؤال {index + 1} من {len(questions)}</b>\n\n"
        f"{_safe(q.get('question'))}"
    )
    if q_type == "short":
        await message.answer(text + "\n\n✍️ اكتب إجابتك وأرسلها.")
    else:
        options = [str(x) for x in (q.get("options") or [])]
        await message.answer(text, reply_markup=question_keyboard(options, index))


@router.callback_query(F.data.startswith("ans:"))
async def quiz_answer(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    if not quiz_id:
        await callback.answer("لا يوجد اختبار نشط.", show_alert=True)
        return
    try:
        _, index_text, option_text = callback.data.split(":", 2)
        index, option_index = int(index_text), int(option_text)
    except (ValueError, AttributeError):
        await callback.answer("إجابة غير صالحة.")
        return
    if index != len(answers) or index >= len(questions):
        await callback.answer("هذا السؤال لم يعد نشطًا.")
        return
    options = questions[index].get("options") or []
    if option_index >= len(options):
        await callback.answer("الخيار غير موجود.")
        return
    answer = str(options[option_index])
    answers.append(answer)
    await state.update_data(answers=answers)
    await callback.answer("تم تسجيل الإجابة ✅")
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_question(callback.message, state, quiz_id, questions, index + 1, answers, db)


@router.message(QuizState.active, F.text)
async def short_answer(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    index = len(answers)
    if not quiz_id or index >= len(questions) or questions[index].get("type") != "short":
        return
    answers.append(message.text.strip())
    await state.update_data(answers=answers)
    await send_question(message, state, quiz_id, questions, index + 1, answers, db)
