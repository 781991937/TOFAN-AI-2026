import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.brand import brand_header, digital_clock
from app.bot.keyboards import main_menu

_YEMEN = ZoneInfo("Asia/Aden")
_CLOCK_TASKS: dict[int, asyncio.Task] = {}


def clock_text() -> str:
    now = datetime.now(_YEMEN)
    return f"{brand_header()}\n\n{digital_clock()}\n\nاختر الخدمة من القائمة:" 


def stop_clock(chat_id: int | None) -> None:
    if chat_id is None: return
    task = _CLOCK_TASKS.pop(int(chat_id), None)
    if task and not task.done(): task.cancel()


def start_clock(message: Message) -> None:
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id is None: return
    stop_clock(chat_id)
    async def _run():
        try:
            while True:
                await asyncio.sleep(1)
                await message.edit_text(clock_text(), reply_markup=message.reply_markup)
        except (asyncio.CancelledError, Exception):
            return
    _CLOCK_TASKS[int(chat_id)] = asyncio.create_task(_run())


class ClockStopMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery) and event.data != "home":
            message = getattr(event, "message", None)
            stop_clock(getattr(getattr(message, "chat", None), "id", None))
        return await handler(event, data)


router = Router(name="clock")


@router.message(CommandStart())
async def clock_start(message: Message, db) -> None:
    db.ensure_user(message.from_user.id, message.from_user.first_name or "")
    sent = await message.answer(clock_text(), reply_markup=main_menu())
    start_clock(sent)


@router.callback_query(F.data == "home")
async def clock_home(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(clock_text(), reply_markup=main_menu())
    start_clock(callback.message)
