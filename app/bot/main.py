import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.bot.handlers import router
from app.bot.enhancements import router as enhancements_router
from app.bot.local_first import router as local_first_router
from app.bot.page_images import router as page_images_router
from app.bot.library import router as library_router
from app.bot.sections import router as sections_router
from app.config_gemini import Settings
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "TOFAN AI 2026"})


async def run_web_server(dp: Dispatcher, bot: Bot) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    external_url = (os.getenv("TELEGRAM_WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET") or None
    if not external_url:
        raise RuntimeError("TELEGRAM_WEBHOOK_URL or RENDER_EXTERNAL_URL is required in production.")
    webhook_path = "/telegram/webhook"
    webhook_url = f"{external_url}{webhook_path}"
    SimpleRequestHandler(dispatcher=dp, bot=bot, handle_in_background=True, secret_token=webhook_secret).register(app, path=webhook_path)
    await bot.set_webhook(url=webhook_url, secret_token=webhook_secret, drop_pending_updates=True, allowed_updates=dp.resolve_used_update_types())
    logging.info("Telegram webhook configured: %s", webhook_url)
    setup_application(app, dp, bot=bot)
    port = int(os.getenv("PORT", "10000"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info("Health/webhook server listening on port %s", port)
    return runner


async def main() -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    database_target = settings.database_url or str(settings.database_path)
    db = Database(database_target)
    extractor = FileExtractor()
    ai_service = AIService(settings.gemini_api_key, settings.gemini_model, settings.database_path)
    quiz_generator = QuizGenerator(ai_service, settings.database_path)
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp["extractor"] = extractor
    dp["ai_service"] = ai_service
    dp["quiz_generator"] = quiz_generator
    dp.include_router(page_images_router)
    dp.include_router(sections_router)
    dp.include_router(local_first_router)
    dp.include_router(enhancements_router)
    dp.include_router(router)
    dp.include_router(library_router)
    external_url = os.getenv("TELEGRAM_WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL")
    storage_mode = "PostgreSQL" if settings.database_url else "SQLite-local"
    logging.info("TOFAN AI 2026 started | storage=%s | Gemini=explicit-only", storage_mode)
    if bool(os.getenv("RENDER_SERVICE_ID") or os.getenv("RENDER_EXTERNAL_URL") or external_url):
        web_runner = await run_web_server(dp, bot)
        try:
            await asyncio.Event().wait()
        finally:
            await web_runner.cleanup()
            await bot.session.close()
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            await dp.start_polling(bot)
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
