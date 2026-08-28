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
_CLOCK_GENERATIONS: dict[int, int] = {}


def clock_text() -> str:
    return f"{brand_header()}\n\n{digital_clock()}\n\nاختر الخدمة من القائمة:"


def stop_clock(chat_id: int | None) -> None:
    if chat_id is None:
        return
    chat_id = int(chat_id)
    _CLOCK_GENERATIONS[chat_id] = _CLOCK_GENERATIONS.get(chat_id, 0) + 1
    task = _CLOCK_TASKS.pop(chat_id, None)
    if task and not task.done():
        task.cancel()


def start_clock(message: Message) -> None:
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id is None:
        return
    chat_id = int(chat_id)
    stop_clock(chat_id)
    generation = _CLOCK_GENERATIONS[chat_id]
    # Keep the original main-menu keyboard. Never capture a section keyboard.
    keyboard = main_menu()

    async def _run():
        try:
            while True:
                await asyncio.sleep(1)
                if _CLOCK_GENERATIONS.get(chat_id) != generation or _CLOCK_TASKS.get(chat_id) is not asyncio.current_task():
                    return
                try:
                    await message.edit_text(clock_text(), reply_markup=keyboard)
                except Exception:
                    # A newer screen may have replaced this message. The task must die
                    # instead of putting the old main menu/clock back over it.
                    return
        except asyncio.CancelledError:
            return
        finally:
            if _CLOCK_TASKS.get(chat_id) is asyncio.current_task():
                _CLOCK_TASKS.pop(chat_id, None)

    _CLOCK_TASKS[chat_id] = asyncio.create_task(_run())


class ClockStopMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery):
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
