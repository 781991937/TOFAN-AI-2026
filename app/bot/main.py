import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import router
from app.config import Settings
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


async def main() -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    db = Database(settings.database_path)
    extractor = FileExtractor()
    ai_service = AIService(settings.openai_api_key, settings.openai_model)
    quiz_generator = QuizGenerator(ai_service)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp["extractor"] = extractor
    dp["ai_service"] = ai_service
    dp["quiz_generator"] = quiz_generator
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("TOFAN AI 2026 is starting")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
