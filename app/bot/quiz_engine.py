import asyncio
import html
import json
import logging
import re
import time
import unicodedata

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.database import Database

logger = logging.getLogger(__name__)
router = Router(name="quiz_engine")

QUESTION_TIMEOUT = 15
MAX_MESSAGE_LENGTH = 3900
_timeout_tasks: dict[int, asyncio.Task] = {}


class QuizState(StatesGroup):
    active = State()


def answer_matches(question: dict, answer: str) -> bool:
    expected = str(question.get("answer", "")).strip().casefold()
    actual = str(answer or "").strip().casefold()
    if question.get("type") == "short":
        return bool(expected) and (expected == actual or expected in actual or actual in expected)
    return bool(expected) and actual == expected


_ALLOWED_HTML = re.compile(
    r"</?(?:b|strong|i|em|u|s|code|pre|blockquote)(?:\s[^>]*)?>",
    re.IGNORECASE,
)
_TAG_TOKEN = "__TOFAN_HTML_TAG_{:04d}__"


def _format_content(value: object) -> str:
    """Safely format lesson/AI text for Telegram HTML without breaking languages or formulas."""
    text = str(value or "")
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)

    # Page markers from extracted PDFs are implementation metadata, not study text.
    text = re.sub(r"\[\[PAGE:\s*\d+\]\]", "", text, flags=re.IGNORECASE)

    # Preserve only Telegram-safe HTML tags already produced by the AI.
    tags: list[str] = []

    def hold_tag(match: re.Match[str]) -> str:
        tags.append(match.group(0))
        return _TAG_TOKEN.format(len(tags) - 1)

    text = _ALLOWED_HTML.sub(hold_tag, text)
    text = html.escape(text, quote=False)

    # Also support common Markdown produced by models, while keeping formulas such as p < q safe.
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)

    for index, tag in enumerate(tags):
        text = text.replace(_TAG_TOKEN.format(index), tag)

    # Keep paragraphs readable without changing the actual language/content.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _safe(value: object) -> str:
    return _format_content(value)


def _cancel_timeout(user_id: int) -> None:
    task = _timeout_tasks.pop(user_id, None)
    if task and not task.done():
        task.cancel()


def _controls(paused: bool = False) -> list[InlineKeyboardButton]:
    if paused:
        return [
            InlineKeyboardButton(text="▶️ متابعة الاختبار", callback_data="quiz_resume"),
            InlineKeyboardButton(text="⏹️ إنهاء الاختبار", callback_data="quiz_end"),
        ]
    return [
        InlineKeyboardButton(text="⏸️ إيقاف مؤقت", callback_data="quiz_pause"),
        InlineKeyboardButton(text="⏹️ إنهاء الاختبار", callback_data="quiz_end"),
    ]


def question_keyboard(options: list[str], index: int, paused: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if not paused:
        for i, option in enumerate(options):
            label = _format_content(option).replace("<", "").replace(">", "")
            rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"ans:{index}:{i}")])
    rows.append(_controls(paused))
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _question_timeout(message: Message, state: FSMContext, quiz_id: int, questions: list[dict], index: int, db: Database) -> None:
    try:
        data = await state.get_data()
        deadline = float(data.get("deadline", time.monotonic() + QUESTION_TIMEOUT))
        await asyncio.sleep(max(0.0, deadline - time.monotonic()))
        data = await state.get_data()
        if data.get("quiz_id") != quiz_id or data.get("paused"):
            return
        answers = data.get("answers", [])
        if len(answers) != index or index >= len(questions):
            return
        answers.append("")
        await state.update_data(answers=answers, deadline=0.0)
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_question(message, state, quiz_id, questions, index + 1, answers, db)
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Quiz question timeout failed")
    finally:
        try:
            user_id = int((await state.get_data()).get("user_id", 0) or 0)
        except Exception:
            user_id = 0
        current = _timeout_tasks.get(user_id)
        if current is asyncio.current_task():
            _timeout_tasks.pop(user_id, None)


async def _start_question_timeout(message: Message, state: FSMContext, quiz_id: int, questions: list[dict], index: int, db: Database, remaining: float | None = None) -> None:
    data = await state.get_data()
    user_id = int(data.get("user_id", 0) or (message.from_user.id if message.from_user else message.chat.id))
    _cancel_timeout(user_id)
    seconds = max(0.1, float(remaining if remaining is not None else QUESTION_TIMEOUT))
    await state.update_data(deadline=time.monotonic() + seconds, paused=False)
    _timeout_tasks[user_id] = asyncio.create_task(_question_timeout(message, state, quiz_id, questions, index, db))


def _review_header(score: int, total: int, percentage: float) -> list[str]:
    return [
        "🏁 <b>انتهى الاختبار</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"🎯 <b>النتيجة:</b> {score} / {total}",
        f"📊 <b>النسبة:</b> {percentage}%",
        "━━━━━━━━━━━━━━━━━━",
    ]


def _build_review_lines(questions: list[dict], answers: list[str]) -> list[str]:
    lines = ["📋 <b>مراجعة الإجابات</b>"]
    wrong_count = 0

    for i, (question, answer) in enumerate(zip(questions, answers), 1):
        if answer_matches(question, answer):
            continue

        wrong_count += 1
        lines.extend(
            [
                "",
                f"❌ <b>السؤال {i}</b>",
                f"📝 <b>إجابتك:</b> {_safe(answer) or 'بدون إجابة'}",
                f"✅ <b>الصحيح:</b> {_safe(question.get('answer')) or 'غير محدد'}",
            ]
        )

        explanation = _safe(question.get("explanation"))
        if explanation:
            lines.extend(
                [
                    "💡 <b>الشرح:</b>",
                    f"<blockquote>{explanation}</blockquote>",
                ]
            )

        # Keep each error visually separated, regardless of Arabic, English, or mixed text.
        lines.append("──────────────────")

    if wrong_count == 0:
        lines.extend(["", "🎉 <b>ممتاز!</b> لم تسجل أي إجابة خاطئة."])
    else:
        lines.extend(["", f"📌 <b>عدد الأخطاء:</b> {wrong_count}"])

    return lines


def _message_chunks(lines: list[str], limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split on complete lines so Telegram never receives broken HTML tags."""
    chunks: list[str] = []
    current = ""

    for line in lines:
        candidate = line if not current else f"{current}\n{line}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = line
        else:
            # A single unbroken source line can still be very long. Split it safely at whitespace.
            while len(line) > limit:
                cut = line.rfind(" ", 0, limit)
                if cut <= 0:
                    cut = limit
                chunks.append(line[:cut])
                line = line[cut:].lstrip()
            current = line

    if current:
        chunks.append(current)
    return chunks or [""]


async def finish_quiz(message: Message, state: FSMContext, quiz_id: int, lesson_id: int, questions: list[dict], answers: list[str], db: Database, group_mode: bool = False) -> None:
    data = await state.get_data()
    user_id = int(data.get("user_id", 0) or (message.from_user.id if message.from_user else message.chat.id))
    _cancel_timeout(user_id)
    answers = list(answers)
    while len(answers) < len(questions):
        answers.append("")
    score = sum(answer_matches(q, a) for q, a in zip(questions, answers))
    total = len(questions)
    percentage = round(score / total * 100, 1) if total else 0
    db.save_result(message.from_user.id, quiz_id, score, total, percentage, json.dumps(answers, ensure_ascii=False))

    lines = _review_header(score, total, percentage)
    if group_mode:
        lines.extend(["", "👥 <b>لوحة المتصدرين</b>", "أضيفت نتيجتك إلى لوحة المتصدرين."])
    else:
        lines.extend(["", *_build_review_lines(questions, answers)])

    from app.bot.keyboards import result_menu

    bot_mode = data.get("engine") == "local"
    chunks = _message_chunks(lines)
    for index, chunk in enumerate(chunks):
        markup = result_menu(lesson_id, group=group_mode, bot=bot_mode) if index == len(chunks) - 1 else None
        await message.answer(chunk, reply_markup=markup)

    await state.clear()


async def send_question(message: Message, state: FSMContext, quiz_id: int, questions: list[dict], index: int, answers: list[str], db: Database, remaining: float | None = None) -> None:
    data = await state.get_data()
    lesson_id = int(data.get("lesson_id", 0))
    group_mode = bool(data.get("group_mode", False))
    if index >= len(questions):
        await finish_quiz(message, state, quiz_id, lesson_id, questions, answers, db, group_mode)
        return

    q = questions[index]
    q_type = str(q.get("type", "mcq"))
    text = (
        f"❓ <b>السؤال {index + 1} من {len(questions)}</b>\n"
        f"⏱️ <b>الوقت:</b> {QUESTION_TIMEOUT} ثانية\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{_safe(q.get('question'))}"
    )
    if q_type == "short":
        await message.answer(text + "\n\n✍️ <b>اكتب إجابتك ثم أرسلها.</b>", reply_markup=question_keyboard([], index))
    else:
        options = [str(x) for x in (q.get("options") or [])]
        await message.answer(text, reply_markup=question_keyboard(options, index))
    await _start_question_timeout(message, state, quiz_id, questions, index, db, remaining=remaining)


@router.callback_query(F.data == "quiz_pause")
async def quiz_pause(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    if not quiz_id or data.get("paused"):
        await callback.answer("الاختبار متوقف مؤقتًا بالفعل.")
        return
    deadline = float(data.get("deadline", time.monotonic()))
    remaining = max(0.0, deadline - time.monotonic())
    _cancel_timeout(callback.from_user.id)
    await state.update_data(paused=True, remaining=remaining)
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=question_keyboard([], len(data.get("answers", [])), paused=True))
        except Exception:
            pass
    await callback.answer(f"⏸️ تم إيقاف الاختبار. المتبقي: {max(1, int(remaining + 0.999))} ثانية")


@router.callback_query(F.data == "quiz_resume")
async def quiz_resume(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    if not quiz_id or not data.get("paused"):
        await callback.answer("الاختبار يعمل بالفعل.")
        return
    index = len(answers)
    if index >= len(questions):
        await callback.answer("انتهى الاختبار.")
        return
    remaining = max(0.1, float(data.get("remaining", QUESTION_TIMEOUT)))
    await state.update_data(paused=False, remaining=0.0)
    _cancel_timeout(callback.from_user.id)
    q = questions[index]
    if callback.message:
        markup = question_keyboard([str(x) for x in (q.get("options") or [])], index) if q.get("type") != "short" else question_keyboard([], index)
        try:
            await callback.message.edit_reply_markup(reply_markup=markup)
        except Exception:
            pass
    await _start_question_timeout(callback.message, state, quiz_id, questions, index, db, remaining=remaining)
    await callback.answer("▶️ استؤنف الاختبار.")


@router.callback_query(F.data == "quiz_end")
async def quiz_end(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    if not quiz_id:
        await callback.answer("لا يوجد اختبار نشط.", show_alert=True)
        return
    await callback.answer("⏹️ تم إنهاء الاختبار.")
    if callback.message:
        await finish_quiz(callback.message, state, int(quiz_id), int(data.get("lesson_id", 0)), questions, answers, db, bool(data.get("group_mode", False)))


@router.callback_query(F.data.startswith("ans:"))
async def quiz_answer(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    questions = data.get("questions", [])
    answers = data.get("answers", [])
    if not quiz_id:
        await callback.answer("لا يوجد اختبار نشط.", show_alert=True)
        return
    if data.get("paused"):
        await callback.answer("⏸️ الاختبار متوقف مؤقتًا. اضغط متابعة أولًا.")
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

    _cancel_timeout(callback.from_user.id)
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
    if not quiz_id or data.get("paused"):
        return
    index = len(answers)
    if index >= len(questions) or questions[index].get("type") != "short":
        return
    _cancel_timeout(message.from_user.id)
    answers.append(message.text.strip())
    await state.update_data(answers=answers)
    await send_question(message, state, quiz_id, questions, index + 1, answers, db)
