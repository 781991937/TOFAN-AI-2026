import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import router
from app.bot.enhancements import router as enhancements_router
from app.config_gemini import Settings
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "TOFAN AI 2026"})


async def run_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Health server listening on port %s", port)
    return runner


async def main() -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    db = Database(settings.database_path)
    extractor = FileExtractor()
    ai_service = AIService(settings.gemini_api_key, settings.gemini_model, settings.database_path)
    quiz_generator = QuizGenerator(ai_service, settings.database_path)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp["extractor"] = extractor
    dp["ai_service"] = ai_service
    dp["quiz_generator"] = quiz_generator
    # Enhancement handlers must come first so their correction/delete callbacks
    # take precedence over the legacy handlers in app.bot.handlers.
    dp.include_router(enhancements_router)
    dp.include_router(router)

    health_runner = await run_health_server()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("TOFAN AI 2026 is starting with Gemini (SQLite cache + corrections enabled)")
    try:
        await dp.start_polling(bot)
    finally:
        await health_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
