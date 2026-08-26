import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

_YEMEN = ZoneInfo("Asia/Aden")
_DAYS = {
    0: "الاثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد",
}
_CLOCK_TASKS: dict[int, asyncio.Task] = {}


def clock_text() -> str:
    now = datetime.now(_YEMEN)
    hour = now.hour % 12 or 12
    period = "ص" if now.hour < 12 else "م"
    return (
        "🌟 <b>أهلًا بك في TOFAN AI 2026!</b>\n\n"
        f"🕐 <b>{hour:02d}:{now.minute:02d}:{now.second:02d} {period}</b>\n"
        f"📅 <b>{_DAYS[now.weekday()]} — {now.day:02d}/{now.month:02d}/{now.year}</b>\n\n"
        "اختر الخدمة التي تريدها من القائمة:"
    )


def stop_clock(chat_id: int | None) -> None:
    if chat_id is None:
        return
    task = _CLOCK_TASKS.pop(int(chat_id), None)
    if task and not task.done():
        task.cancel()


def start_clock(message) -> None:
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id is None:
        return
    stop_clock(chat_id)

    async def _run() -> None:
        try:
            while True:
                await asyncio.sleep(1)
                await message.edit_text(clock_text(), reply_markup=message.reply_markup)
        except asyncio.CancelledError:
            raise
        except Exception:
            # The menu may have been replaced/deleted; stop quietly.
            return

    _CLOCK_TASKS[int(chat_id)] = asyncio.create_task(_run())


class ClockStopMiddleware(BaseMiddleware):
    """Stop the live home clock as soon as the user leaves the main menu."""

    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery) and event.data != "home":
            message = getattr(event, "message", None)
            chat = getattr(message, "chat", None)
            stop_clock(getattr(chat, "id", None))
        return await handler(event, data)
